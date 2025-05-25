"""Time and date formatting utilities for weather display.

Provides consistent formatting of timestamps, dates, and times
according to user configuration.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rpi_weather_display.models.config import DisplayConfig


class TimeFormatter:
    """Formats times and dates for display.
    
    This class centralizes all time and date formatting logic,
    supporting various formats based on user configuration.
    """
    
    def __init__(self, display_config: "DisplayConfig") -> None:
        """Initialize the time formatter.
        
        Args:
            display_config: Display configuration with format settings
        """
        self.display_config = display_config
        
    def format_datetime(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a datetime object or Unix timestamp.
        
        Args:
            dt: Datetime object or Unix timestamp
            format_str: Format string (uses config default if None)
            
        Returns:
            Formatted datetime string
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)
            
        if format_str is None:
            format_str = self.display_config.timestamp_format
            
        return dt.strftime(format_str)
    
    def format_time(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a time for display.
        
        Uses AM/PM format without leading zeros by default,
        or the specified format from config.
        
        Args:
            dt: Datetime object or Unix timestamp
            format_str: Format string (uses config default if None)
            
        Returns:
            Formatted time string
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)
            
        if format_str is None:
            # Check for time_format in config
            if hasattr(self.display_config, "time_format") and self.display_config.time_format:
                return dt.strftime(self.display_config.time_format)
            else:
                # Default: 12-hour format without leading zeros
                hour = dt.hour % 12
                if hour == 0:
                    hour = 12  # 12-hour clock shows 12 for noon/midnight
                return f"{hour}:{dt.minute:02d} {dt.strftime('%p')}"
        else:
            return dt.strftime(format_str)
    
    def format_datetime_display(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a datetime for prominent display.
        
        Args:
            dt: Datetime object or Unix timestamp
            format_str: Optional format string to override config
            
        Returns:
            Formatted datetime string
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)
            
        # Use provided format, config format, or default
        if format_str is not None:
            return dt.strftime(format_str)
            
        if (hasattr(self.display_config, "display_datetime_format") 
            and self.display_config.display_datetime_format):
            return dt.strftime(self.display_config.display_datetime_format)
            
        # Default: MM/DD/YYYY HH:MM AM/PM without leading zeros
        month = dt.month
        day = dt.day
        year = dt.year
        hour = dt.hour % 12
        if hour == 0:
            hour = 12
        minute = dt.minute
        am_pm = dt.strftime("%p")
        
        return f"{month}/{day}/{year} {hour}:{minute:02d} {am_pm}"
    
    def format_timestamp_if_exists(
        self, obj: object, attr: str, time_format: str | None = None
    ) -> str:
        """Format a timestamp attribute if it exists on an object.
        
        Args:
            obj: Object that may have the timestamp attribute
            attr: Name of the timestamp attribute
            time_format: Optional time format string
            
        Returns:
            Formatted time string or empty string if attribute doesn't exist
        """
        if hasattr(obj, attr):
            timestamp = getattr(obj, attr)
            if timestamp:
                return self.format_time(timestamp, time_format)
        return ""
    
    def get_weekday_short(self, timestamp: int) -> str:
        """Get short weekday name from timestamp.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Short weekday name (e.g., "Mon", "Tue")
        """
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%a")