"""Weather-related calculations and data processing.

Handles calculations for daylight hours, UV index, pressure conversions,
and other weather metrics.
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from rpi_weather_display.constants import (
    HPA_TO_INHG,
    HPA_TO_MMHG,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    UVI_CACHE_FILENAME,
)
from rpi_weather_display.utils import file_utils, path_resolver

if TYPE_CHECKING:
    from rpi_weather_display.models.weather import WeatherData

logger = logging.getLogger(__name__)


class WeatherCalculator:
    """Performs weather-related calculations.
    
    This class handles various weather metric calculations including:
    - Daylight duration
    - UV index tracking
    - Pressure unit conversions
    """
    
    def calculate_daylight_hours(self, sunrise: int, sunset: int) -> str:
        """Calculate daylight duration from sunrise and sunset timestamps.
        
        Args:
            sunrise: Sunrise timestamp (Unix time)
            sunset: Sunset timestamp (Unix time)
            
        Returns:
            Formatted daylight duration (e.g., "12h 30m")
        """
        try:
            daylight_seconds = sunset - sunrise
            daylight_hours = daylight_seconds // SECONDS_PER_HOUR
            daylight_minutes = (daylight_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
            return f"{daylight_hours}h {daylight_minutes}m"
        except Exception:
            return "12h 30m"  # Fallback value
    
    def convert_pressure(self, pressure_hpa: float, target_units: str) -> float:
        """Convert pressure from hPa to target units.
        
        Args:
            pressure_hpa: Pressure in hectopascals (hPa)
            target_units: Target units ("hPa", "mmHg", or "inHg")
            
        Returns:
            Converted pressure value
        """
        if target_units == "mmHg":
            return pressure_hpa * HPA_TO_MMHG
        if target_units == "inHg":
            return pressure_hpa * HPA_TO_INHG
        # hPa
        return pressure_hpa
    
    def get_daily_max_uvi(self, weather_data: "WeatherData", now: datetime) -> tuple[float, int]:
        """Calculate the max UVI for today with caching.
        
        Finds the maximum UV index value from hourly forecasts for the current day
        and persists it in a cache file to maintain the max value between API calls.
        
        Args:
            weather_data: Weather data containing current and hourly forecasts
            now: Current datetime
            
        Returns:
            Tuple of (max_uvi, max_uvi_timestamp)
        """
        cache_file = path_resolver.get_cache_file(UVI_CACHE_FILENAME)
        today = now.date()
        
        # Calculate current max from API data
        max_uvi, max_uvi_timestamp = self._calculate_current_max_uvi(weather_data, now)
        
        # Check cache for higher value
        cached_uvi, cached_timestamp = self._read_uvi_cache(cache_file, today)
        
        # Use cached value if higher
        if cached_uvi is not None and cached_uvi > max_uvi:
            return cached_uvi, cached_timestamp or 0
        
        # Save new max value
        if max_uvi > 0:
            self._write_uvi_cache(cache_file, today, max_uvi, max_uvi_timestamp)
        
        return max_uvi, max_uvi_timestamp
    
    def _calculate_current_max_uvi(
        self, weather_data: "WeatherData", now: datetime
    ) -> tuple[float, int]:
        """Calculate maximum UVI from current and hourly forecast data.
        
        Args:
            weather_data: Weather data containing current and hourly forecasts
            now: Current datetime
            
        Returns:
            Tuple of (max_uvi, timestamp) for today
        """
        # Initialize with current API data
        max_uvi = 0.0
        max_uvi_timestamp = 0
        
        if hasattr(weather_data.current, "uvi"):
            max_uvi = weather_data.current.uvi
            max_uvi_timestamp = int(now.timestamp())
        
        # Get today's date range
        today = now.date()
        today_start_dt = datetime.combine(today, datetime.min.time())
        today_end_dt = datetime.combine(
            today + timedelta(days=1), datetime.min.time()
        ) - timedelta(seconds=1)
        today_start = int(today_start_dt.timestamp())
        today_end = int(today_end_dt.timestamp())
        
        # Check hourly forecast for today's max UVI
        for hour in weather_data.hourly:
            if (today_start <= hour.dt <= today_end 
                and hasattr(hour, "uvi") 
                and hour.uvi > max_uvi):
                max_uvi = hour.uvi
                max_uvi_timestamp = hour.dt
                
        return max_uvi, max_uvi_timestamp
    
    def _read_uvi_cache(self, cache_file: Path, today: date) -> tuple[float | None, int | None]:
        """Read UVI cache file and return values if valid for today.
        
        Args:
            cache_file: Path to the cache file
            today: Today's date for validation
            
        Returns:
            Tuple of (cached_uvi, cached_timestamp) or (None, None) if invalid
        """
        if not file_utils.file_exists(cache_file):
            return None, None
            
        try:
            cache_data = file_utils.read_json(cache_file)
            
            # Validate cache structure
            if not isinstance(cache_data, dict):
                return None, None
                
            # Check date
            date_str = cache_data.get("date")
            if not isinstance(date_str, str):
                return None, None
                
            cache_date = datetime.fromisoformat(date_str).date()
            if cache_date != today:
                return None, None
                
            # Extract and validate values
            max_uvi_value = cache_data.get("max_uvi")
            timestamp_value = cache_data.get("timestamp")
            
            if isinstance(max_uvi_value, int | float) and isinstance(timestamp_value, int):
                return float(max_uvi_value), timestamp_value
                
        except Exception as e:
            logger.debug(f"Error reading UVI cache: {e}")
            
        return None, None
    
    def _write_uvi_cache(
        self, cache_file: Path, today: date, max_uvi: float, timestamp: int
    ) -> None:
        """Write UVI values to cache file.
        
        Args:
            cache_file: Path to the cache file
            today: Today's date
            max_uvi: Maximum UVI value to cache
            timestamp: Timestamp of the maximum UVI
        """
        try:
            cache_data = {
                "date": today.isoformat(),
                "max_uvi": max_uvi,
                "timestamp": timestamp,
            }
            file_utils.write_json(cache_file, cache_data)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning(f"Failed to cache max UVI: {e}")