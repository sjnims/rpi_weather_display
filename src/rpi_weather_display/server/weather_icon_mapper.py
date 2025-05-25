"""Weather icon mapping functionality.

Maps OpenWeatherMap weather condition IDs and icon codes to 
Weather Icons font class names for display.
"""

import csv
import logging
from io import StringIO
from typing import TYPE_CHECKING

from rpi_weather_display.utils import file_utils, path_resolver

if TYPE_CHECKING:
    from rpi_weather_display.models.weather import WeatherCondition

logger = logging.getLogger(__name__)


class WeatherIconMapper:
    """Maps weather conditions to display icons.
    
    This class handles the mapping of OpenWeatherMap weather condition IDs
    and icon codes to Weather Icons font class names. It supports:
    - Loading custom mappings from CSV
    - Day/night icon variants
    - Fallback mappings for unmapped conditions
    """
    
    def __init__(self) -> None:
        """Initialize the weather icon mapper."""
        self._weather_icon_map: dict[str, str] = {}
        self._weather_id_to_icon: dict[str, str] = {}
        self._loaded = False
        
    def _ensure_mappings_loaded(self) -> None:
        """Load weather icon mappings from CSV file if not already loaded."""
        if self._loaded:
            return
            
        try:
            # Use path_resolver to find the CSV file
            csv_path = path_resolver.get_data_file("owm_icon_map.csv")
            
            if not file_utils.file_exists(csv_path):
                logger.warning("Could not find owm_icon_map.csv file, using defaults")
                self._loaded = True
                return
                
            # Read and parse the CSV file
            csv_content = file_utils.read_text(csv_path)
            reader = csv.DictReader(StringIO(csv_content))
            
            for row in reader:
                weather_id = row["API response: id"].strip()
                icon_code = row["API response: icon"].strip()
                weather_icon_class = row["Weather Icons Class"].strip()
                
                # Store by ID + icon code
                key = f"{weather_id}_{icon_code}"
                self._weather_icon_map[key] = weather_icon_class
                
                # Store by ID only for fallback
                self._weather_id_to_icon[weather_id] = weather_icon_class
                
            logger.debug(f"Loaded {len(self._weather_icon_map)} icon mappings")
            
        except Exception as e:
            logger.error(f"Error loading weather icon mappings: {e}")
        finally:
            self._loaded = True
    
    def get_icon_for_condition(self, weather_condition: "WeatherCondition") -> str:
        """Get icon for a weather condition object.
        
        Args:
            weather_condition: Weather condition with id and icon attributes
            
        Returns:
            Weather Icons class name
        """
        self._ensure_mappings_loaded()
        
        if not hasattr(weather_condition, "id") or not hasattr(weather_condition, "icon"):
            return "wi-cloud"  # Default fallback
            
        weather_id = str(weather_condition.id)
        icon_code = weather_condition.icon
        
        # Handle day/night variants for clear/cloudy conditions (800-804)
        if weather_id in ["800", "801", "802", "803", "804"]:
            is_day = icon_code.endswith("d")
            variant = "d" if is_day else "n"
            key = f"{weather_id}_{weather_id[0:2]}{variant}"
            if key in self._weather_icon_map:
                return self._weather_icon_map[key]
        
        # Try exact match (ID + icon code)
        key = f"{weather_id}_{icon_code}"
        if key in self._weather_icon_map:
            return self._weather_icon_map[key]
            
        # Fallback to ID only
        if weather_id in self._weather_id_to_icon:
            return self._weather_id_to_icon[weather_id]
            
        # Last resort: use icon code with default mapping
        return self.get_icon_for_code(icon_code)
    
    def get_icon_for_code(self, icon_code: str) -> str:
        """Get icon for an OpenWeatherMap icon code.
        
        Args:
            icon_code: OpenWeatherMap icon code (e.g., "01d")
            
        Returns:
            Weather Icons class name
        """
        # Default mapping for common weather conditions
        default_mapping = {
            "01d": "wi-day-sunny",      # Clear sky (day)
            "01n": "wi-night-clear",    # Clear sky (night)
            "02d": "wi-day-cloudy",     # Few clouds (day)
            "02n": "wi-night-cloudy",   # Few clouds (night)
            "03d": "wi-cloud",          # Scattered clouds
            "03n": "wi-cloud",
            "04d": "wi-cloudy",         # Broken clouds
            "04n": "wi-cloudy",
            "09d": "wi-showers",        # Shower rain
            "09n": "wi-showers",
            "10d": "wi-day-rain",       # Rain (day)
            "10n": "wi-night-rain",     # Rain (night)
            "11d": "wi-thunderstorm",   # Thunderstorm
            "11n": "wi-thunderstorm",
            "13d": "wi-snow",           # Snow
            "13n": "wi-snow",
            "50d": "wi-fog",            # Mist
            "50n": "wi-fog",
        }
        
        return default_mapping.get(icon_code, "wi-cloud")