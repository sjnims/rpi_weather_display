"""Weather API client for interacting with OpenWeatherMap services.

Provides functionality to fetch weather data, forecasts, and air quality information
from OpenWeatherMap APIs with appropriate caching mechanisms. This module handles
all external API communication for the weather display system.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from rpi_weather_display.constants import (
    API_LOCATION_LIMIT,
    OWM_AIR_POLLUTION_URL,
    OWM_GEOCODING_URL,
    OWM_ONECALL_URL,
    SECONDS_PER_MINUTE,
    WEATHER_API_CACHE_SIZE_MB,
)
from rpi_weather_display.exceptions import (
    APIAuthenticationError,
    APIRateLimitError,
    APITimeoutError,
    InvalidAPIResponseError,
    MissingConfigError,
    WeatherAPIError,
    chain_exception,
)
from rpi_weather_display.models.config import WeatherConfig
from rpi_weather_display.models.weather import (
    AirPollutionData,
    CurrentWeather,
    DailyWeather,
    HourlyWeather,
    WeatherData,
)
from rpi_weather_display.utils.cache_manager import MemoryAwareCache
from rpi_weather_display.utils.error_utils import get_error_location


class WeatherAPIClient:
    """Client for the OpenWeatherMap API.

    Handles communication with OpenWeatherMap services, including
    weather data fetching, geocoding, and air quality information.
    Provides caching mechanisms to reduce API calls and manages
    error handling for network operations.

    Attributes:
        config: Weather API configuration including API key and preferences
        logger: Logger instance for tracking API operations
        _last_forecast: Cached weather forecast data
        _last_update: Timestamp of last successful API update
        BASE_URL: One Call API endpoint for comprehensive weather data
        AIR_POLLUTION_URL: API endpoint for air quality data
        GEOCODING_URL: API endpoint for converting city names to coordinates
    """

    BASE_URL = OWM_ONECALL_URL
    AIR_POLLUTION_URL = OWM_AIR_POLLUTION_URL
    GEOCODING_URL = OWM_GEOCODING_URL

    def __init__(self, config: WeatherConfig) -> None:
        """Initialize the API client.

        Args:
            config: Weather API configuration including API key, location,
                units preference, language, and update intervals.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Initialize memory-aware cache
        self._cache = MemoryAwareCache[WeatherData](
            max_size_mb=WEATHER_API_CACHE_SIZE_MB,
            ttl_seconds=int(config.update_interval_minutes * SECONDS_PER_MINUTE),
        )

    async def get_coordinates(self) -> tuple[float, float]:
        """Get latitude and longitude from city name if needed.

        Attempts to use configured coordinates first. If not available,
        uses the geocoding API to resolve a city name to coordinates.

        Returns:
            Tuple of (latitude, longitude).

        Raises:
            MissingConfigError: If neither coordinates nor city name are provided.
            WeatherAPIError: If the geocoding API request fails.
        """
        # Try to get coordinates from config first
        config_coords = self._get_configured_coordinates()
        if config_coords:
            return config_coords

        # Validate we have a city name to geocode
        self._validate_city_name()

        # Get coordinates from geocoding API
        return await self._geocode_city()
    
    def _get_configured_coordinates(self) -> tuple[float, float] | None:
        """Get coordinates from configuration if available.
        
        Returns:
            Tuple of (latitude, longitude) if configured, None otherwise.
        """
        lat = self.config.location.get("lat")
        lon = self.config.location.get("lon")
        
        if lat and lon:
            return (lat, lon)
        return None
    
    def _validate_city_name(self) -> None:
        """Validate that a city name is configured.
        
        Raises:
            MissingConfigError: If no city name is provided.
        """
        if not self.config.city_name:
            raise MissingConfigError(
                "No location coordinates or city name provided in configuration",
                {"field": "city_name", "config_section": "weather.location"}
            )
    
    def _format_city_query(self) -> str:
        """Format city name for geocoding API.
        
        The API expects formats like "London" or "London,GB" without spaces around commas.
        Special handling for US cities with state abbreviations.
        
        Returns:
            Formatted city query string.
        """
        city_query = self.config.city_name or ""
        
        if "," not in city_query:
            return city_query
            
        # Split by comma and clean up spaces
        parts = [part.strip() for part in city_query.split(",")]

        # Check if this is a US city with state abbreviation (e.g., "Smyrna, GA")
        if self._is_us_state_format(parts):
            parts.append("US")

        city_query = ",".join(parts)
        self.logger.info(f"Formatted city query: {city_query}")
        return city_query
    
    @staticmethod
    def _is_us_state_format(parts: list[str]) -> bool:
        """Check if parts represent a US city with state abbreviation.
        
        Args:
            parts: List of city name parts split by comma.
            
        Returns:
            True if this appears to be a US state abbreviation format.
        """
        return len(parts) == 2 and len(parts[1]) == 2 and parts[1].isupper()
    
    async def _geocode_city(self) -> tuple[float, float]:
        """Get coordinates for city name using geocoding API.
        
        Returns:
            Tuple of (latitude, longitude).
            
        Raises:
            WeatherAPIError: If the geocoding API request fails.
            InvalidAPIResponseError: If the city cannot be found.
        """
        city_query = self._format_city_query()
        
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
                    raise InvalidAPIResponseError(
                        f"Could not find location for city name: {self.config.city_name}",
                        {
                            "city_name": self.config.city_name,
                            "query": city_query,
                            "expected_fields": ["lat", "lon"],
                            "received": []
                        },
                        status_code=200,
                        response_body=str(locations)
                    )

                return (locations[0]["lat"], locations[0]["lon"])
                
        except httpx.HTTPStatusError as e:
            error_location = get_error_location()
            self.logger.error(f"HTTP error during geocoding [{error_location}]: {e}")
            if e.response.status_code == 401:
                raise chain_exception(
                    APIAuthenticationError(
                        "Invalid API key for geocoding",
                        {
                            "api_key_prefix": self.config.api_key[:8] + "...",
                            "endpoint": self.GEOCODING_URL
                        },
                        status_code=401,
                        response_body=e.response.text
                    ),
                    e
                ) from e
            else:
                raise chain_exception(
                    WeatherAPIError(
                        "Geocoding API request failed",
                        {"endpoint": self.GEOCODING_URL, "city": self.config.city_name},
                        status_code=e.response.status_code,
                        response_body=e.response.text
                    ),
                    e
                ) from e
        except httpx.TimeoutException as e:
            error_location = get_error_location()
            self.logger.error(f"Timeout during geocoding [{error_location}]: {e}")
            raise chain_exception(
                APITimeoutError(
                    "Geocoding API request timed out",
                    {"endpoint": self.GEOCODING_URL, "city": self.config.city_name, "timeout": 30}
                ),
                e
            ) from e
        except InvalidAPIResponseError:
            # Re-raise our custom exceptions as-is
            raise
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error during geocoding [{error_location}]: {e}")
            raise chain_exception(
                WeatherAPIError(
                    f"Failed to geocode location: {self.config.city_name}",
                    {"city": self.config.city_name, "error": str(e)}
                ),
                e
            ) from e

    async def get_weather_data(self, force_refresh: bool = False) -> WeatherData:
        """Get weather data from the OpenWeatherMap API.

        Fetches current weather conditions, hourly forecast, daily forecast,
        and air quality data. Implements memory-aware caching to reduce API calls.

        Args:
            force_refresh: Force a refresh regardless of cache state.

        Returns:
            WeatherData object with current weather and forecast.

        Raises:
            WeatherAPIError: If API requests fail and no cached data is available.
            MissingConfigError: If required location information is missing.
        """
        # Get location and cache key
        lat, lon = await self.get_coordinates()
        cache_key = self._generate_cache_key(lat, lon)

        # Try to get cached data if not forcing refresh
        if not force_refresh:
            cached_data = self._get_cached_weather(cache_key)
            if cached_data:
                return cached_data

        try:
            # Fetch fresh weather data
            weather = await self._fetch_weather_data(lat, lon)
            
            # Cache the result
            self._cache_weather_data(cache_key, weather)
            
            self.logger.info("Weather data updated successfully")
            return weather
            
        except (httpx.HTTPError, Exception) as e:
            return self._handle_weather_fetch_error(e, cache_key)
    
    def _generate_cache_key(self, lat: float, lon: float) -> str:
        """Generate cache key for weather data.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Cache key string
        """
        return f"weather_{lat}_{lon}_{self.config.units}_{self.config.language}"
    
    def _get_cached_weather(self, cache_key: str) -> WeatherData | None:
        """Get weather data from cache if available.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached WeatherData or None if not found
        """
        cached_data = self._cache.get(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached weather data")
        return cached_data
    
    async def _fetch_weather_data(self, lat: float, lon: float) -> WeatherData:
        """Fetch weather data from OpenWeatherMap APIs.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            WeatherData object with all weather information
            
        Raises:
            WeatherAPIError: If API request fails
        """
        async with httpx.AsyncClient() as client:
            # Fetch both weather and air pollution data
            weather_data = await self._fetch_weather_forecast(client, lat, lon)
            air_data = await self._fetch_air_pollution(client, lat, lon)
            
            # Combine air pollution data with weather data
            weather_data["air_pollution"] = air_data["list"][0] if air_data["list"] else None
            
            # Parse into WeatherData model
            return self._parse_weather_response(weather_data)
    
    async def _fetch_weather_forecast(
        self, client: httpx.AsyncClient, lat: float, lon: float
    ) -> dict[str, Any]:
        """Fetch weather forecast data.
        
        Args:
            client: HTTP client
            lat: Latitude 
            lon: Longitude
            
        Returns:
            Weather forecast data dictionary
            
        Raises:
            WeatherAPIError: If API request fails
        """
        weather_params = {
            "lat": lat,
            "lon": lon,
            "appid": self.config.api_key,
            "units": self.config.units,
            "lang": self.config.language,
            "exclude": "minutely,alerts",
        }
        
        try:
            response = await client.get(self.BASE_URL, params=weather_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise chain_exception(
                    APIAuthenticationError(
                        "Invalid API key for weather data",
                        {
                            "api_key_prefix": self.config.api_key[:8] + "...",
                            "endpoint": self.BASE_URL
                        },
                        status_code=401,
                        response_body=e.response.text
                    ),
                    e
                ) from e
            elif e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "3600")
                raise chain_exception(
                    APIRateLimitError(
                        "Weather API rate limit exceeded",
                        {"endpoint": self.BASE_URL, "retry_after": int(retry_after)},
                        status_code=429,
                        response_body=e.response.text
                    ),
                    e
                ) from e
            else:
                raise chain_exception(
                    WeatherAPIError(
                        "Weather API request failed",
                        {"endpoint": self.BASE_URL, "lat": lat, "lon": lon},
                        status_code=e.response.status_code,
                        response_body=e.response.text
                    ),
                    e
                ) from e
        except httpx.TimeoutException as e:
            raise chain_exception(
                APITimeoutError(
                    "Weather API request timed out",
                    {"endpoint": self.BASE_URL, "lat": lat, "lon": lon, "timeout": 30}
                ),
                e
            ) from e
    
    async def _fetch_air_pollution(
        self, client: httpx.AsyncClient, lat: float, lon: float
    ) -> dict[str, Any]:
        """Fetch air pollution data.
        
        Args:
            client: HTTP client
            lat: Latitude
            lon: Longitude
            
        Returns:
            Air pollution data dictionary
            
        Raises:
            WeatherAPIError: If API request fails
        """
        air_params = {
            "lat": lat,
            "lon": lon,
            "appid": self.config.api_key
        }
        
        try:
            response = await client.get(self.AIR_POLLUTION_URL, params=air_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise chain_exception(
                    APIAuthenticationError(
                        "Invalid API key for air pollution data",
                        {
                            "api_key_prefix": self.config.api_key[:8] + "...",
                            "endpoint": self.AIR_POLLUTION_URL
                        },
                        status_code=401,
                        response_body=e.response.text
                    ),
                    e
                ) from e
            else:
                raise chain_exception(
                    WeatherAPIError(
                        "Air pollution API request failed",
                        {"endpoint": self.AIR_POLLUTION_URL, "lat": lat, "lon": lon},
                        status_code=e.response.status_code,
                        response_body=e.response.text
                    ),
                    e
                ) from e
        except httpx.TimeoutException as e:
            raise chain_exception(
                APITimeoutError(
                    "Air pollution API request timed out",
                    {"endpoint": self.AIR_POLLUTION_URL, "lat": lat, "lon": lon, "timeout": 30}
                ),
                e
            ) from e
    
    def _parse_weather_response(self, weather_data: dict[str, Any]) -> WeatherData:
        """Parse API response into WeatherData model.
        
        Args:
            weather_data: Raw weather data from API
            
        Returns:
            WeatherData model instance
        """
        return WeatherData(
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
            air_pollution=self._parse_air_pollution(weather_data.get("air_pollution")),
            last_updated=datetime.now(),
        )
    
    def _parse_air_pollution(self, air_data: dict[str, Any] | None) -> AirPollutionData | None:
        """Parse air pollution data if available.
        
        Args:
            air_data: Raw air pollution data or None
            
        Returns:
            AirPollutionData model or None
        """
        if not air_data:
            return None
            
        return AirPollutionData(
            dt=air_data["dt"],
            main=air_data["main"],
            components=air_data["components"],
        )
    
    def _cache_weather_data(self, cache_key: str, weather: WeatherData) -> None:
        """Cache weather data with size estimate.
        
        Args:
            cache_key: Cache key
            weather: Weather data to cache
        """
        # Estimate data size for memory-aware caching
        # Use model_dump_json for proper datetime serialization
        data_json = weather.model_dump_json()
        data_size = len(data_json.encode("utf-8"))
        self._cache.put(cache_key, weather, data_size)
    
    def _handle_weather_fetch_error(self, error: Exception, cache_key: str) -> WeatherData:
        """Handle errors during weather fetch with fallback to cache.
        
        Args:
            error: The exception that occurred
            cache_key: Cache key for fallback lookup
            
        Returns:
            Cached weather data if available
            
        Raises:
            The original exception if no cached data available
        """
        error_location = get_error_location()
        self.logger.error(f"Error during weather data fetch [{error_location}]: {error}")
        
        # Try to return cached data as fallback
        cached_data = self._cache.get(cache_key)
        if cached_data is not None:
            self.logger.warning("Using cached weather data due to error")
            return cached_data
            
        # Re-raise if no cached data available
        raise error

    async def get_icon_mapping(self, icon_code: str) -> str:
        """Get the corresponding sprite icon ID for an OpenWeatherMap icon code.

        Maps OpenWeatherMap icon codes (like "01d" for clear sky day) to
        icon IDs in the sprite file used by the weather display. This provides
        a consistent interface for icon lookups regardless of the source.

        Args:
            icon_code: OpenWeatherMap icon code (e.g., "01d").

        Returns:
            Icon ID from the sprite file (e.g., "sun-bold" for "01d"),
            or "cloud-bold" if the icon code is not recognized.
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

        Allows test code to inject mock forecast data into the client
        without making actual API calls. This method should only be used
        in testing environments and not in production code.

        Args:
            forecast: Weather forecast data to use for testing.
            update_time: Time of the update, defaults to current time.
                         Used to simulate specific cache timing scenarios
                         for testing cache expiration behavior.

        Warning:
            This method is intended only for testing purposes. Using it in
            production code may lead to stale or incorrect weather data
            being displayed to users.
        """
        self._last_forecast = forecast
        self._last_update = update_time or datetime.now()
