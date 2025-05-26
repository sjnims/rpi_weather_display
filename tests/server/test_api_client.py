"""Tests for the API client."""

# File-level directive to ignore protected usage warnings
# pyright: reportPrivateUsage=false

from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

# No need for additional typing imports
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from httpx import Request, Response

from rpi_weather_display.exceptions import (
    InvalidAPIResponseError,
    MissingConfigError,
    WeatherAPIError,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.weather import WeatherData
from rpi_weather_display.server.api import WeatherAPIClient
from rpi_weather_display.utils.file_utils import JsonData, read_json
from rpi_weather_display.utils.path_utils import path_resolver


@pytest.fixture()
def mock_weather_data() -> JsonData:
    """Load mock weather data from file."""
    # Use path_resolver to locate the test data file relative to the current file
    data_file = path_resolver.normalize_path(
        Path(__file__).parent.parent / "data" / "mock_weather_response.json"
    )
    # Use file_utils to read and parse JSON in one operation
    return read_json(data_file)


# Define a recursive type for JSON data
JSONType = dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None


def create_mock_response(status_code: int = 200, json_data: JSONType | None = None) -> Response:
    """Create a mock Response object with properly set request property."""
    # Create a response with the specified status code and JSON data
    response = Response(status_code, json=json_data)

    # Create a request and attach it to the response
    request = Request("GET", "https://example.com")

    # Setting _request attribute (needed for raise_for_status to work properly)
    response._request = request

    return response


@pytest.fixture()
def mock_httpx_client() -> Generator[AsyncMock, None, None]:
    """Mock httpx.AsyncClient to avoid actual HTTP requests."""
    # Create a patch for the entire AsyncClient class
    with patch("httpx.AsyncClient") as mock:
        mock_client = AsyncMock()
        mock.return_value.__aenter__.return_value = mock_client
        mock.return_value.__aexit__.return_value = None
        yield mock_client


@pytest.mark.asyncio()
async def test_api_client_init(app_config: AppConfig) -> None:
    """Test API client initialization."""
    client = WeatherAPIClient(app_config.weather)
    assert client is not None
    assert client.config == app_config.weather


@pytest.mark.asyncio()
async def test_get_coordinates_from_config(app_config: AppConfig) -> None:
    """Test getting coordinates directly from config."""
    # Update config to include lat/lon
    app_config.weather.location = {"lat": 35.123, "lon": -85.456}

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Get coordinates
    lat, lon = await api_client.get_coordinates()

    # Check that coordinates match config
    assert lat == 35.123
    assert lon == -85.456


@pytest.mark.asyncio()
async def test_get_coordinates_no_location(app_config: AppConfig) -> None:
    """Test error when no location info is provided."""
    # Remove both lat/lon and city name
    app_config.weather.location = {}
    app_config.weather.city_name = None

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Should raise MissingConfigError
    with pytest.raises(MissingConfigError, match="No location coordinates or city name provided"):
        await api_client.get_coordinates()


@pytest.mark.asyncio()
async def test_get_coordinates_geocoding(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test getting coordinates via geocoding API."""
    # Set up the mock response
    mock_response = create_mock_response(
        200, [{"name": "New York", "lat": 40.7128, "lon": -74.0060, "country": "US"}]
    )
    mock_httpx_client.get.return_value = mock_response

    # Configure app to use city name instead of coordinates
    app_config.weather.location = {}
    app_config.weather.city_name = "New York"

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Get coordinates
    lat, lon = await api_client.get_coordinates()

    # Check that coordinates match the mock response
    assert lat == 40.7128
    assert lon == -74.0060

    # Verify the API call was made correctly
    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert args[0] == api_client.GEOCODING_URL
    assert kwargs["params"]["q"] == "New York"
    assert kwargs["params"]["appid"] == app_config.weather.api_key


@pytest.mark.asyncio()
async def test_get_coordinates_geocoding_empty_response(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test error handling when geocoding returns empty results."""
    # Set up the mock response with empty results
    mock_response = create_mock_response(200, [])
    mock_httpx_client.get.return_value = mock_response

    # Configure app to use city name
    app_config.weather.location = {}
    app_config.weather.city_name = "NonexistentCity"

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Should raise InvalidAPIResponseError
    with pytest.raises(
        InvalidAPIResponseError, match="Could not find location for city name: NonexistentCity"
    ) as exc_info:
        await api_client.get_coordinates()

    # Check exception details
    assert exc_info.value.details["city_name"] == "NonexistentCity"
    assert exc_info.value.status_code == 200


@pytest.mark.asyncio()
async def test_get_coordinates_http_error(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of HTTP errors in geocoding."""
    # Set up the mock to raise an HTTP error
    # Create a mock request and response for HTTPStatusError
    mock_request = Mock(spec=httpx.Request)
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_httpx_client.get.side_effect = httpx.HTTPStatusError(
        "HTTP Error", request=mock_request, response=mock_response
    )

    # Configure app to use city name
    app_config.weather.location = {}
    app_config.weather.city_name = "New York"

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Should re-raise as WeatherAPIError
    with pytest.raises(WeatherAPIError) as exc_info:
        await api_client.get_coordinates()

    # Check that the original exception is preserved
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.asyncio()
async def test_get_weather_data_cached(app_config: AppConfig, mock_weather_data: JsonData) -> None:
    """Test that cached weather data is returned when available."""
    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Create a weather data instance for the mock
    weather = WeatherData.model_validate(mock_weather_data)

    # Mock the get_coordinates to return test coordinates
    with patch.object(api_client, "get_coordinates", return_value=(51.5074, -0.1278)):
        # Generate the cache key that would be used
        lat, lon = 51.5074, -0.1278
        cache_key = f"weather_{lat}_{lon}_{api_client.config.units}_{api_client.config.language}"

        # Put the weather data in the cache (estimate size as 10KB for test)
        api_client._cache.put(cache_key, weather, size_bytes=10 * 1024)

        # Call without force refresh
        result = await api_client.get_weather_data(force_refresh=False)

        # Verify cached data is returned
        assert result == weather


@pytest.mark.asyncio()
async def test_get_weather_data_force_refresh(
    app_config: AppConfig, mock_weather_data: JsonData, mock_httpx_client: AsyncMock
) -> None:
    """Test getting weather data with force refresh."""
    # Set up mock responses
    weather_response = create_mock_response(200, mock_weather_data)
    air_response = create_mock_response(
        200,
        {
            "list": [
                {
                    "dt": 1609459200,
                    "main": {"aqi": 1},
                    "components": {
                        "co": 201.94053649902344,
                        "no": 0.01877197064459324,
                        "no2": 0.7711350917816162,
                        "o3": 68.66455078125,
                        "so2": 0.6407499313354492,
                        "pm2_5": 0.5,
                        "pm10": 0.540438711643219,
                        "nh3": 0.12369127571582794,
                    },
                }
            ]
        },
    )

    mock_httpx_client.get.side_effect = [weather_response, air_response]

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Set up initial cached data
    old_weather = WeatherData.model_validate(mock_weather_data)
    api_client.set_forecast_for_testing(old_weather)

    # Call with force refresh
    result = await api_client.get_weather_data(force_refresh=True)

    # Verify API calls were made
    assert mock_httpx_client.get.call_count == 2

    weather_call_args = mock_httpx_client.get.call_args_list[0]
    assert weather_call_args[0][0] == api_client.BASE_URL
    assert weather_call_args[1]["params"]["lat"] == 40.7128
    assert weather_call_args[1]["params"]["lon"] == -74.0060

    air_call_args = mock_httpx_client.get.call_args_list[1]
    assert air_call_args[0][0] == api_client.AIR_POLLUTION_URL

    # Verify result is not the same as the old cached data
    assert result is not old_weather


@pytest.mark.asyncio()
async def test_get_weather_data_http_error(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of HTTP errors when fetching weather data."""
    # Set up the mock to raise an HTTP error
    # Create a mock request and response for HTTPStatusError
    mock_request = Mock(spec=httpx.Request)
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_httpx_client.get.side_effect = httpx.HTTPStatusError(
        "HTTP Error", request=mock_request, response=mock_response
    )

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Call should re-raise as WeatherAPIError without cached data
    with pytest.raises(WeatherAPIError) as exc_info:
        await api_client.get_weather_data(force_refresh=True)

    # Check that the original exception is preserved
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.asyncio()
async def test_get_weather_data_http_error_with_cache(
    app_config: AppConfig, mock_weather_data: JsonData, mock_httpx_client: AsyncMock
) -> None:
    """Test that cached data is returned when API call fails but cache is available."""
    # Set up the mock to raise an HTTP error
    # Create a mock request and response for HTTPStatusError
    mock_request = Mock(spec=httpx.Request)
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_httpx_client.get.side_effect = httpx.HTTPStatusError(
        "HTTP Error", request=mock_request, response=mock_response
    )

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Set up cached data
    weather = WeatherData.model_validate(mock_weather_data)

    # Generate the cache key that would be used
    lat, lon = 40.7128, -74.0060
    cache_key = f"weather_{lat}_{lon}_{api_client.config.units}_{api_client.config.language}"

    # Put the weather data in the cache
    api_client._cache.put(cache_key, weather, size_bytes=10 * 1024)

    # Call should return cached data despite HTTP error
    result = await api_client.get_weather_data(force_refresh=True)
    assert result == weather


@pytest.mark.asyncio()
async def test_get_weather_data_cache_expired(
    app_config: AppConfig, mock_weather_data: JsonData, mock_httpx_client: AsyncMock
) -> None:
    """Test that new data is fetched when cache is expired."""
    # Set up mock responses
    weather_response = create_mock_response(200, mock_weather_data)
    air_response = create_mock_response(
        200,
        {
            "list": [
                {
                    "dt": 1609459200,
                    "main": {"aqi": 1},
                    "components": {
                        "co": 201.94053649902344,
                        "no": 0.01877197064459324,
                        "no2": 0.7711350917816162,
                        "o3": 68.66455078125,
                        "so2": 0.6407499313354492,
                        "pm2_5": 0.5,
                        "pm10": 0.540438711643219,
                        "nh3": 0.12369127571582794,
                    },
                }
            ]
        },
    )

    mock_httpx_client.get.side_effect = [weather_response, air_response]

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Set up initial cached data with old timestamp
    old_weather = WeatherData.model_validate(mock_weather_data)
    old_timestamp = datetime.now() - timedelta(minutes=30)  # 30 minutes old
    api_client.set_forecast_for_testing(old_weather, old_timestamp)

    # Call without force refresh, but cache is old
    result = await api_client.get_weather_data(force_refresh=False)

    # Verify API calls were made because cache was expired
    assert mock_httpx_client.get.call_count == 2

    # Verify result is not None
    assert result is not None


@pytest.mark.asyncio()
async def test_get_icon_mapping(app_config: AppConfig) -> None:
    """Test mapping of weather icon codes to sprite icon IDs."""
    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Test day icons
    assert await api_client.get_icon_mapping("01d") == "sun-bold"  # Clear sky (day)
    assert await api_client.get_icon_mapping("02d") == "sun-cloud-bold"  # Few clouds (day)
    assert await api_client.get_icon_mapping("10d") == "sun-cloud-rain-bold"  # Rain (day)

    # Test night icons
    assert await api_client.get_icon_mapping("01n") == "moon-bold"  # Clear sky (night)
    assert await api_client.get_icon_mapping("02n") == "moon-cloud-bold"  # Few clouds (night)

    # Test non-time-specific icons
    assert await api_client.get_icon_mapping("13d") == await api_client.get_icon_mapping(
        "13n"
    )  # Snow

    # Test fallback for unknown icon
    assert await api_client.get_icon_mapping("unknown") == "cloud-bold"


@pytest.mark.asyncio()
async def test_get_coordinates_city_name_with_state(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test city name formatting for US cities with state abbreviations."""
    # Set up the mock response
    mock_response = create_mock_response(
        200, [{"name": "Atlanta", "lat": 33.7490, "lon": -84.3880, "country": "US"}]
    )
    mock_httpx_client.get.return_value = mock_response

    # Configure app to use city name with state
    app_config.weather.location = {}
    app_config.weather.city_name = "Atlanta, GA"  # City with state abbreviation

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Get coordinates
    lat, lon = await api_client.get_coordinates()

    # Check that coordinates match the mock response
    assert lat == 33.7490
    assert lon == -84.3880

    # Verify the API call was made with properly formatted query (should add US)
    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert args[0] == api_client.GEOCODING_URL
    assert kwargs["params"]["q"] == "Atlanta,GA,US"  # No spaces, with US added


@pytest.mark.asyncio()
async def test_get_coordinates_city_name_with_country(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test city name formatting with country code."""
    # Set up the mock response
    mock_response = create_mock_response(
        200, [{"name": "London", "lat": 51.5074, "lon": -0.1278, "country": "GB"}]
    )
    mock_httpx_client.get.return_value = mock_response

    # Configure app to use city name with country
    app_config.weather.location = {}
    app_config.weather.city_name = "London, GB"  # City with country code

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Get coordinates
    lat, lon = await api_client.get_coordinates()

    # Check that coordinates match the mock response
    assert lat == 51.5074
    assert lon == -0.1278

    # Verify the API call was made with properly formatted query
    # Note: The code adds 'US' to any 2-character country code
    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert args[0] == api_client.GEOCODING_URL
    assert kwargs["params"]["q"] == "London,GB,US"  # With 'US' added


@pytest.mark.asyncio()
async def test_get_coordinates_general_exception(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of general exceptions in geocoding."""
    # Set up the mock to raise a general exception
    mock_httpx_client.get.side_effect = ValueError("Invalid query")

    # Configure app to use city name
    app_config.weather.location = {}
    app_config.weather.city_name = "New York"

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Should wrap the general exception in WeatherAPIError
    with pytest.raises(WeatherAPIError, match="Failed to geocode location: New York") as exc_info:
        await api_client.get_coordinates()

    # Check that the original exception is preserved
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "Invalid query"


@pytest.mark.asyncio()
async def test_get_weather_data_empty_air_data(
    app_config: AppConfig, mock_weather_data: JsonData, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of empty air pollution data."""
    # Set up mock responses
    weather_response = create_mock_response(200, mock_weather_data)
    air_response = create_mock_response(200, {"list": []})  # Empty air pollution data

    mock_httpx_client.get.side_effect = [weather_response, air_response]

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Call with force refresh
    result = await api_client.get_weather_data(force_refresh=True)

    # Verify air pollution data is None
    assert result.air_pollution is None

    # Verify API calls were made
    assert mock_httpx_client.get.call_count == 2


@pytest.mark.asyncio()
async def test_get_weather_data_general_exception(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of general exceptions when fetching weather data."""
    # Set up the mock to raise a general exception
    mock_httpx_client.get.side_effect = ValueError("Invalid data")

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Call should propagate the original exception without cached data
    with pytest.raises(ValueError, match="Invalid data"):
        await api_client.get_weather_data(force_refresh=True)


@pytest.mark.asyncio()
async def test_get_weather_data_general_exception_with_cache(
    app_config: AppConfig, mock_weather_data: JsonData, mock_httpx_client: AsyncMock
) -> None:
    """Test that cached data is returned when general exception occurs but cache is available."""
    # Set up the mock to raise a general exception
    mock_httpx_client.get.side_effect = ValueError("Invalid data")

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Set up cached data
    weather = WeatherData.model_validate(mock_weather_data)

    # Generate the cache key that would be used
    lat, lon = 40.7128, -74.0060
    cache_key = f"weather_{lat}_{lon}_{api_client.config.units}_{api_client.config.language}"

    # Put the weather data in the cache
    api_client._cache.put(cache_key, weather, size_bytes=10 * 1024)

    # Call should return cached data despite general exception
    result = await api_client.get_weather_data(force_refresh=True)
    assert result == weather


@pytest.mark.asyncio()
async def test_get_icon_mapping_comprehensive(app_config: AppConfig) -> None:
    """Test mapping of all weather icon codes to sprite icon IDs."""
    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Define all expected icon mappings
    expected_mappings = {
        "01d": "sun-bold",
        "01n": "moon-bold",
        "02d": "sun-cloud-bold",
        "02n": "moon-cloud-bold",
        "03d": "cloud-bold",
        "03n": "cloud-bold",
        "04d": "clouds-bold",
        "04n": "clouds-bold",
        "09d": "cloud-drizzle-bold",
        "09n": "cloud-drizzle-bold",
        "10d": "sun-cloud-rain-bold",
        "10n": "moon-cloud-rain-bold",
        "11d": "cloud-lightning-bold",
        "11n": "cloud-lightning-bold",
        "13d": "cloud-snow-bold",
        "13n": "cloud-snow-bold",
        "50d": "cloud-fog-bold",
        "50n": "cloud-fog-bold",
    }

    # Test all icon mappings
    for icon_code, expected_icon in expected_mappings.items():
        actual_icon = await api_client.get_icon_mapping(icon_code)
        assert actual_icon == expected_icon, f"Icon mapping failed for {icon_code}"


@pytest.mark.asyncio()
async def test_get_coordinates_city_name_non_state_abbreviation(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test city name formatting with comma but non-state abbreviation."""
    # Set up the mock response
    mock_response = create_mock_response(
        200, [{"name": "Paris", "lat": 48.8566, "lon": 2.3522, "country": "FR"}]
    )
    mock_httpx_client.get.return_value = mock_response

    # Configure app to use city name with country, but not in state abbreviation format
    app_config.weather.location = {}
    app_config.weather.city_name = "Paris, France"  # Not a 2-letter uppercase code

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Get coordinates
    lat, lon = await api_client.get_coordinates()

    # Check that coordinates match the mock response
    assert lat == 48.8566
    assert lon == 2.3522

    # Verify the API call was made with properly formatted query
    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert args[0] == api_client.GEOCODING_URL
    assert kwargs["params"]["q"] == "Paris,France"  # With spaces removed, but no US added
