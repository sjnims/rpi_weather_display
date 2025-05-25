"""Template filter management for Jinja2 templates.

Centralizes the registration and management of custom filters
and global functions for weather display templates.
"""

from typing import TYPE_CHECKING

import jinja2

from rpi_weather_display.models.weather import CurrentWeather, HourlyWeather, WeatherCondition
from rpi_weather_display.server.moon_phase_helper import MoonPhaseHelper
from rpi_weather_display.server.wind_helper import WindHelper

if TYPE_CHECKING:
    from rpi_weather_display.server.weather_icon_mapper import WeatherIconMapper


class TemplateFilterManager:
    """Manages custom filters and globals for Jinja2 templates.
    
    This class centralizes all template filter logic, making it easier
    to maintain and test template functions separately from the renderer.
    """
    
    def __init__(self, jinja_env: jinja2.Environment, icon_mapper: "WeatherIconMapper") -> None:
        """Initialize the filter manager.
        
        Args:
            jinja_env: Jinja2 environment to register filters on
            icon_mapper: Weather icon mapper instance
        """
        self.jinja_env = jinja_env
        self.icon_mapper = icon_mapper
        
    def register_all_filters(self) -> None:
        """Register all custom filters and globals."""
        self._register_weather_filters()
        self._register_moon_filters()
        self._register_wind_filters()
        self._register_precipitation_filters()
        
    def _register_weather_filters(self) -> None:
        """Register weather-related filters."""
        def weather_icon_filter(weather_item: WeatherCondition) -> str:
            """Convert weather condition to icon."""
            return self.icon_mapper.get_icon_for_condition(weather_item)
            
        self.jinja_env.filters["weather_icon"] = weather_icon_filter
        
    def _register_moon_filters(self) -> None:
        """Register moon phase filters."""
        self.jinja_env.filters["moon_phase_icon"] = MoonPhaseHelper.get_moon_phase_icon
        self.jinja_env.filters["moon_phase_label"] = MoonPhaseHelper.get_moon_phase_label
        
    def _register_wind_filters(self) -> None:
        """Register wind-related filters."""
        # Wrapped functions for proper typing
        def wind_direction_angle(degrees: float) -> float:
            """Calculate wind direction angle for display."""
            return WindHelper.get_wind_direction_angle(degrees)
            
        def wind_direction_cardinal(degrees: float) -> str:
            """Get cardinal wind direction."""
            return WindHelper.get_wind_direction_cardinal(degrees)
            
        # Type ignore needed due to Jinja2's filter typing
        self.jinja_env.filters["wind_direction_angle"] = wind_direction_angle  # type: ignore[assignment]
        self.jinja_env.filters["wind_direction_cardinal"] = wind_direction_cardinal  # type: ignore[assignment]
        
    def _register_precipitation_filters(self) -> None:
        """Register precipitation-related filters."""
        def get_precipitation_amount(weather_item: CurrentWeather | HourlyWeather) -> float | None:
            """Extract precipitation amount from weather item.
            
            The API returns rain/snow as dicts with "1h" key for current/hourly data.
            
            Args:
                weather_item: Weather data object
                
            Returns:
                Precipitation amount in mm/inches or None
            """
            if hasattr(weather_item, "rain") and weather_item.rain:
                return weather_item.rain.get("1h", 0.0)
            if hasattr(weather_item, "snow") and weather_item.snow:
                return weather_item.snow.get("1h", 0.0)
            return None
            
        def get_hourly_precipitation(hour: HourlyWeather) -> str:
            """Get formatted precipitation for hourly forecast.
            
            Args:
                hour: Hourly weather data
                
            Returns:
                Formatted precipitation amount or probability
            """
            # Try actual precipitation amount first
            amount = get_precipitation_amount(hour)
            if amount is not None:
                return f"{amount:.1f}"
                
            # Fall back to probability of precipitation
            if hasattr(hour, "pop"):
                return f"{int(hour.pop * 100)}%"
                
            return "0"
            
        # Register as both filters and globals
        # Type ignore needed due to Jinja2's typing limitations
        self.jinja_env.filters["get_precipitation_amount"] = get_precipitation_amount  # type: ignore[assignment]
        self.jinja_env.filters["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore[assignment]
        
        self.jinja_env.globals["get_precipitation_amount"] = get_precipitation_amount  # type: ignore[assignment]
        self.jinja_env.globals["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore[assignment]