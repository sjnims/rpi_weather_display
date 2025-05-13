"""Tests for the API client."""
# ruff: noqa: S101, RUF009
# ^ Ignores "Use of assert detected" and "protected-access" in test files, which are common in tests

import json
import os
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import Request, Response

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.weather import WeatherData
from rpi_weather_display.server.api import WeatherAPIClient

# File-level directive to ignore protected usage warnings
# pyright: reportPrivateUsage=false


@pytest.fixture()
def mock_weather_data() -> dict[str, Any]:
    """Load mock weather data from file."""
    data_file = (
        Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "mock_weather_response.json"
    )
    with open(data_file) as f:
        return json.load(f)


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

    # Should raise ValueError
    with pytest.raises(ValueError, match="No location coordinates or city name provided"):
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

    # Should raise ValueError
    with pytest.raises(ValueError, match="Could not find location for city name"):
        await api_client.get_coordinates()


@pytest.mark.asyncio()
async def test_get_coordinates_http_error(
    app_config: AppConfig, mock_httpx_client: AsyncMock
) -> None:
    """Test handling of HTTP errors in geocoding."""
    # Set up the mock to raise an HTTP error
    mock_httpx_client.get.side_effect = httpx.HTTPError("HTTP Error")

    # Configure app to use city name
    app_config.weather.location = {}
    app_config.weather.city_name = "New York"

    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Should propagate the HTTP error
    with pytest.raises(httpx.HTTPError):
        await api_client.get_coordinates()


@pytest.mark.asyncio()
async def test_get_weather_data_cached(
    app_config: AppConfig, mock_weather_data: dict[str, Any]
) -> None:
    """Test that cached weather data is returned when available."""
    # Create API client
    api_client = WeatherAPIClient(app_config.weather)

    # Create a weather data instance for the mock
    weather = WeatherData.model_validate(mock_weather_data)

    # Set up the cached data using the test method
    api_client.set_forecast_for_testing(weather)

    # Call without force refresh
    result = await api_client.get_weather_data(force_refresh=False)

    # Verify cached data is returned
    assert result is weather


@pytest.mark.asyncio()
async def test_get_weather_data_force_refresh(
    app_config: AppConfig, mock_weather_data: dict[str, Any], mock_httpx_client: AsyncMock
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
    mock_httpx_client.get.side_effect = httpx.HTTPError("HTTP Error")

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Call should raise without cached data
    with pytest.raises(httpx.HTTPError):
        await api_client.get_weather_data(force_refresh=True)


@pytest.mark.asyncio()
async def test_get_weather_data_http_error_with_cache(
    app_config: AppConfig, mock_weather_data: dict[str, Any], mock_httpx_client: AsyncMock
) -> None:
    """Test that cached data is returned when API call fails but cache is available."""
    # Set up the mock to raise an HTTP error
    mock_httpx_client.get.side_effect = httpx.HTTPError("HTTP Error")

    # Create API client with location
    app_config.weather.location = {"lat": 40.7128, "lon": -74.0060}
    api_client = WeatherAPIClient(app_config.weather)

    # Set up cached data
    weather = WeatherData.model_validate(mock_weather_data)
    api_client.set_forecast_for_testing(weather)

    # Call should return cached data despite HTTP error
    result = await api_client.get_weather_data(force_refresh=True)
    assert result is weather


@pytest.mark.asyncio()
async def test_get_weather_data_cache_expired(
    app_config: AppConfig, mock_weather_data: dict[str, Any], mock_httpx_client: AsyncMock
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
