"""Weather API client for interacting with OpenWeatherMap services.

Provides functionality to fetch weather data, forecasts, and air quality information
from OpenWeatherMap APIs with appropriate caching mechanisms.
"""

import logging
from datetime import datetime, timedelta

import httpx

from rpi_weather_display.constants import (
    API_LOCATION_LIMIT,
    OWM_AIR_POLLUTION_URL,
    OWM_GEOCODING_URL,
    OWM_ONECALL_URL,
)
from rpi_weather_display.models.config import WeatherConfig
from rpi_weather_display.models.weather import (
    AirPollutionData,
    CurrentWeather,
    DailyWeather,
    HourlyWeather,
    WeatherData,
)
from rpi_weather_display.utils.error_utils import get_error_location


class WeatherAPIClient:
    """Client for the OpenWeatherMap API."""

    BASE_URL = OWM_ONECALL_URL
    AIR_POLLUTION_URL = OWM_AIR_POLLUTION_URL
    GEOCODING_URL = OWM_GEOCODING_URL

    def __init__(self, config: WeatherConfig) -> None:
        """Initialize the API client.

        Args:
            config: Weather API configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._last_forecast: WeatherData | None = None
        self._last_update: datetime | None = None

    async def get_coordinates(self) -> tuple[float, float]:
        """Get latitude and longitude from city name if needed.

        Returns:
            Tuple of (latitude, longitude).
        """
        # If coordinates are already configured, use them
        if self.config.location.get("lat") and self.config.location.get("lon"):
            return (self.config.location["lat"], self.config.location["lon"])

        # If no city name, can't proceed
        if not self.config.city_name:
            raise ValueError("No location coordinates or city name provided in configuration")

        # Format city name properly for the API
        # The API expects formats like "London" or "London,GB" without spaces around the comma
        city_query = self.config.city_name
        if "," in city_query:
            # Split by comma and rejoin without spaces around the comma
            parts = [part.strip() for part in city_query.split(",")]

            # Check if this is a US city with state abbreviation (e.g., "Smyrna, GA")
            # If so, add the US country code
            if len(parts) == 2 and len(parts[1]) == 2 and parts[1].isupper():
                parts.append("US")

            city_query = ",".join(parts)
            self.logger.info(f"Formatted city query: {city_query}")

        # Use geocoding API to get coordinates
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "q": city_query,
                    "limit": API_LOCATION_LIMIT,
                    "appid": self.config.api_key,
                }

                response = await client.get(self.GEOCODING_URL, params=params)
                response.raise_for_status()

                locations = response.json()
                if not locations:
                    raise ValueError(
                        f"Could not find location for city name: {self.config.city_name}"
                    )

                lat = locations[0]["lat"]
                lon = locations[0]["lon"]

                return (lat, lon)
        except httpx.HTTPError as e:
            error_location = get_error_location()
            self.logger.error(f"HTTP error during geocoding [{error_location}]: {e}")
            raise
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error during geocoding [{error_location}]: {e}")
            raise

    async def get_weather_data(self, force_refresh: bool = False) -> WeatherData:
        """Get weather data from the OpenWeatherMap API.

        Args:
            force_refresh: Force a refresh regardless of cache state.

        Returns:
            WeatherData object with current weather and forecast.
        """
        # Check if we have recently updated data
        if (
            not force_refresh
            and self._last_forecast is not None
            and self._last_update is not None
            and datetime.now() - self._last_update < timedelta(minutes=15)
        ):
            self.logger.info("Using cached weather data")
            return self._last_forecast

        try:
            # Get coordinates
            lat, lon = await self.get_coordinates()

            # Get weather data from the API
            async with httpx.AsyncClient() as client:
                # Fetch weather forecast
                weather_params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": self.config.api_key,
                    "units": self.config.units,
                    "lang": self.config.language,
                    "exclude": "minutely,alerts",
                }

                weather_response = await client.get(self.BASE_URL, params=weather_params)
                weather_response.raise_for_status()
                weather_data = weather_response.json()

                # Fetch air pollution data
                air_params = {"lat": lat, "lon": lon, "appid": self.config.api_key}

                air_response = await client.get(self.AIR_POLLUTION_URL, params=air_params)
                air_response.raise_for_status()
                air_data = air_response.json()

                # Combine the data
                weather_data["air_pollution"] = air_data["list"][0] if air_data["list"] else None

                # Parse the data into our model
                weather = WeatherData(
                    lat=weather_data["lat"],
                    lon=weather_data["lon"],
                    timezone=weather_data["timezone"],
                    timezone_offset=weather_data["timezone_offset"],
                    current=CurrentWeather(**weather_data["current"]),
                    hourly=[
                        HourlyWeather(**hour) for hour in weather_data["hourly"][:24]
                    ],  # 24 hours
                    daily=[
                        DailyWeather(**day)
                        for day in weather_data["daily"][: self.config.forecast_days]
                    ],
                    air_pollution=AirPollutionData(
                        dt=weather_data["air_pollution"]["dt"],
                        main=weather_data["air_pollution"]["main"],
                        components=weather_data["air_pollution"]["components"],
                    )
                    if weather_data["air_pollution"]
                    else None,
                    last_updated=datetime.now(),
                )

                # Cache the data
                self._last_forecast = weather
                self._last_update = datetime.now()

                self.logger.info("Weather data updated successfully")
                return weather
        except httpx.HTTPError as e:
            error_location = get_error_location()
            self.logger.error(f"HTTP error during weather data fetch [{error_location}]: {e}")
            # If we have cached data, return it as a fallback
            if self._last_forecast is not None:
                self.logger.warning("Using cached weather data due to API error")
                return self._last_forecast
            raise
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error fetching weather data [{error_location}]: {e}")
            # If we have cached data, return it as a fallback
            if self._last_forecast is not None:
                self.logger.warning("Using cached weather data due to error")
                return self._last_forecast
            raise

    async def get_icon_mapping(self, icon_code: str) -> str:
        """Get the corresponding sprite icon ID for an OpenWeatherMap icon code.

        Args:
            icon_code: OpenWeatherMap icon code (e.g., "01d").

        Returns:
            Icon ID from the sprite file.
        """
        # Map of OpenWeatherMap icon codes to sprite icon IDs
        # This would normally be loaded from a CSV file
        icon_map = {
            "01d": "sun-bold",  # Clear sky (day)
            "01n": "moon-bold",  # Clear sky (night)
            "02d": "sun-cloud-bold",  # Few clouds (day)
            "02n": "moon-cloud-bold",  # Few clouds (night)
            "03d": "cloud-bold",  # Scattered clouds
            "03n": "cloud-bold",
            "04d": "clouds-bold",  # Broken clouds
            "04n": "clouds-bold",
            "09d": "cloud-drizzle-bold",  # Shower rain
            "09n": "cloud-drizzle-bold",
            "10d": "sun-cloud-rain-bold",  # Rain (day)
            "10n": "moon-cloud-rain-bold",  # Rain (night)
            "11d": "cloud-lightning-bold",  # Thunderstorm
            "11n": "cloud-lightning-bold",
            "13d": "cloud-snow-bold",  # Snow
            "13n": "cloud-snow-bold",
            "50d": "cloud-fog-bold",  # Mist
            "50n": "cloud-fog-bold",
        }

        return icon_map.get(icon_code, "cloud-bold")  # Default to cloud if icon not found

    def set_forecast_for_testing(
        self, forecast: WeatherData, update_time: datetime | None = None
    ) -> None:
        """Set forecast data for testing purposes.

        Args:
            forecast: Weather forecast data
            update_time: Time of the update, defaults to current time
        """
        self._last_forecast = forecast
        self._last_update = update_time or datetime.now()
