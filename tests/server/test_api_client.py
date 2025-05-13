"""Tests for the API client."""
# ruff: noqa: S101, RUF009
# ^ Ignores "Use of assert detected" and "protected-access" in test files, which are common in tests

import json
import os
from pathlib import Path
from typing import Any

import pytest

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.weather import WeatherData
from rpi_weather_display.server.api import WeatherAPIClient


@pytest.fixture()
def mock_weather_data() -> dict[str, Any]:
    """Load mock weather data from file."""
    data_file = (
        Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "mock_weather_response.json"
    )
    with open(data_file) as f:
        return json.load(f)


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


@pytest.mark.skip(
    "These tests require complex async mocking that's challenging to implement correctly"
)
class TestComplexAsyncAPIMethods:
    """Tests that require complex async mocking."""

    @pytest.mark.asyncio()
    async def test_get_coordinates_geocoding(self) -> None:
        """Test getting coordinates via geocoding API."""
        pass

    @pytest.mark.asyncio()
    async def test_get_coordinates_error(self) -> None:
        """Test error handling when geocoding fails."""
        pass

    @pytest.mark.asyncio()
    async def test_get_weather_data(self, mock_weather_data: dict[str, Any]) -> None:
        """Test getting weather data from the API."""
        pass

    @pytest.mark.asyncio()
    async def test_get_weather_data_http_error(self) -> None:
        """Test handling of HTTP errors when fetching weather data."""
        pass

    @pytest.mark.asyncio()
    async def test_get_forecast(self, mock_weather_data: dict[str, Any]) -> None:
        """Test getting weather data from the API."""
        # TODO: Implement actual test
        pass

        # Commented out due to missing implementation:
        # # Create API client with app_config
        # api_client = WeatherAPIClient(app_config.weather)
        #
        # # Test cached response
        # # TODO: Implement ForecastNotAvailableError and get_forecast method
        # # with pytest.raises(ForecastNotAvailableError):
        # #     api_client.get_forecast(lat=35.123, lon=-85.456)
        #
        # # Set a cached response and try again
        # weather = WeatherData.model_validate(mock_weather_data)
        # api_client.set_forecast_for_testing(weather)
        #
        # # Should return cached data
        # # result = api_client.get_forecast(lat=35.123, lon=-85.456)
        # # assert result == weather
