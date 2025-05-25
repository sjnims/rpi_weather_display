"""Tests for the TimeFormatter class."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from rpi_weather_display.server.time_formatter import TimeFormatter


@pytest.fixture()
def display_config() -> Mock:
    """Create a mock display configuration."""
    config = Mock()
    config.timestamp_format = "%Y-%m-%d %H:%M:%S"
    config.time_format = "%I:%M %p"
    config.display_datetime_format = "%m/%d/%Y %I:%M %p"
    return config


@pytest.fixture()
def formatter(display_config: Mock) -> TimeFormatter:
    """Create a TimeFormatter instance."""
    return TimeFormatter(display_config)


class TestTimeFormatter:
    """Tests for TimeFormatter."""

    def test_init(self, display_config: Mock) -> None:
        """Test initialization."""
        formatter = TimeFormatter(display_config)
        assert formatter.display_config is display_config

    def test_format_datetime_with_datetime_object(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting a datetime object."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime(dt)
        assert result == "2024-01-15 14:30:45"

    def test_format_datetime_with_unix_timestamp(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting a Unix timestamp."""
        # Unix timestamp for 2024-01-15 14:30:45 UTC
        timestamp = 1705330245
        result = formatter.format_datetime(timestamp)
        # Result depends on local timezone
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_datetime_with_custom_format(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting with custom format string."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime(dt, "%Y/%m/%d")
        assert result == "2024/01/15"

    def test_format_time_with_datetime_object(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting time from datetime object."""
        # Test with config time_format
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_time(dt)
        assert result == "02:30 PM"

    def test_format_time_with_unix_timestamp(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting time from Unix timestamp."""
        # Unix timestamp
        timestamp = 1705330245
        result = formatter.format_time(timestamp)
        assert isinstance(result, str)
        assert ":" in result

    def test_format_time_without_config_time_format(
        self, display_config: Mock
    ) -> None:
        """Test formatting time without time_format in config."""
        # Remove time_format from config
        display_config.time_format = None
        formatter = TimeFormatter(display_config)
        
        # Test various times
        # Noon
        dt = datetime(2024, 1, 15, 12, 30, 45)
        result = formatter.format_time(dt)
        assert result == "12:30 PM"
        
        # Midnight
        dt = datetime(2024, 1, 15, 0, 15, 0)
        result = formatter.format_time(dt)
        assert result == "12:15 AM"
        
        # Morning
        dt = datetime(2024, 1, 15, 9, 5, 0)
        result = formatter.format_time(dt)
        assert result == "9:05 AM"
        
        # Evening
        dt = datetime(2024, 1, 15, 21, 45, 0)
        result = formatter.format_time(dt)
        assert result == "9:45 PM"

    def test_format_time_no_time_format_attribute(
        self, display_config: Mock
    ) -> None:
        """Test formatting time when config has no time_format attribute."""
        # Remove time_format attribute entirely
        delattr(display_config, "time_format")
        formatter = TimeFormatter(display_config)
        
        dt = datetime(2024, 1, 15, 14, 30, 0)
        result = formatter.format_time(dt)
        assert result == "2:30 PM"

    def test_format_time_with_custom_format(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting time with custom format string."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_time(dt, "%H:%M")
        assert result == "14:30"

    def test_format_datetime_display_with_datetime(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting datetime for display."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime_display(dt)
        assert result == "01/15/2024 02:30 PM"

    def test_format_datetime_display_with_timestamp(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting Unix timestamp for display."""
        timestamp = 1705330245
        result = formatter.format_datetime_display(timestamp)
        assert isinstance(result, str)
        assert "/" in result

    def test_format_datetime_display_with_custom_format(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting datetime display with custom format."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime_display(dt, "%Y-%m-%d")
        assert result == "2024-01-15"

    def test_format_datetime_display_without_config_format(
        self, display_config: Mock
    ) -> None:
        """Test datetime display without display_datetime_format in config."""
        # Remove display_datetime_format
        display_config.display_datetime_format = None
        formatter = TimeFormatter(display_config)
        
        # Test various dates and times
        # Regular afternoon
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime_display(dt)
        assert result == "1/15/2024 2:30 PM"
        
        # Noon
        dt = datetime(2024, 12, 25, 12, 0, 0)
        result = formatter.format_datetime_display(dt)
        assert result == "12/25/2024 12:00 PM"
        
        # Midnight
        dt = datetime(2024, 1, 1, 0, 0, 0)
        result = formatter.format_datetime_display(dt)
        assert result == "1/1/2024 12:00 AM"

    def test_format_datetime_display_no_attribute(
        self, display_config: Mock
    ) -> None:
        """Test datetime display when config has no display_datetime_format attribute."""
        # Remove attribute entirely
        delattr(display_config, "display_datetime_format")
        formatter = TimeFormatter(display_config)
        
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = formatter.format_datetime_display(dt)
        assert result == "1/15/2024 2:30 PM"

    def test_format_timestamp_if_exists_with_timestamp(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting timestamp attribute that exists."""
        obj = Mock()
        obj.sunrise = 1705330245
        
        result = formatter.format_timestamp_if_exists(obj, "sunrise")
        assert isinstance(result, str)
        assert ":" in result

    def test_format_timestamp_if_exists_no_attribute(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting when attribute doesn't exist."""
        obj = Mock(spec=[])  # No attributes
        
        result = formatter.format_timestamp_if_exists(obj, "sunrise")
        assert result == ""

    def test_format_timestamp_if_exists_none_value(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting when attribute exists but is None."""
        obj = Mock()
        obj.sunrise = None
        
        result = formatter.format_timestamp_if_exists(obj, "sunrise")
        assert result == ""

    def test_format_timestamp_if_exists_zero_value(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting when attribute exists but is 0."""
        obj = Mock()
        obj.sunrise = 0
        
        result = formatter.format_timestamp_if_exists(obj, "sunrise")
        assert result == ""

    def test_format_timestamp_if_exists_with_custom_format(
        self, formatter: TimeFormatter
    ) -> None:
        """Test formatting timestamp with custom format."""
        obj = Mock()
        obj.sunset = 1705330245
        
        result = formatter.format_timestamp_if_exists(obj, "sunset", "%H:%M")
        assert isinstance(result, str)
        assert ":" in result

    def test_get_weekday_short(self, formatter: TimeFormatter) -> None:
        """Test getting short weekday names."""
        # Monday, January 15, 2024
        timestamp = 1705305600
        result = formatter.get_weekday_short(timestamp)
        assert result in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        # Test a known date - Unix epoch (January 1, 1970)
        # Note: The actual day depends on timezone
        timestamp = 0
        result = formatter.get_weekday_short(timestamp)
        assert result in ["Wed", "Thu"]  # Could be Wed or Thu depending on timezone

    def test_edge_cases_midnight_noon(self, formatter: TimeFormatter) -> None:
        """Test edge cases for midnight and noon formatting."""
        # Remove config formats to test default behavior
        formatter.display_config.time_format = None
        
        # Test midnight (00:00)
        dt = datetime(2024, 1, 15, 0, 0, 0)
        result = formatter.format_time(dt)
        assert result == "12:00 AM"
        
        # Test noon (12:00)
        dt = datetime(2024, 1, 15, 12, 0, 0)
        result = formatter.format_time(dt)
        assert result == "12:00 PM"
        
        # Test 1 AM
        dt = datetime(2024, 1, 15, 1, 0, 0)
        result = formatter.format_time(dt)
        assert result == "1:00 AM"
        
        # Test 1 PM
        dt = datetime(2024, 1, 15, 13, 0, 0)
        result = formatter.format_time(dt)
        assert result == "1:00 PM"

    def test_format_datetime_display_edge_cases(
        self, display_config: Mock
    ) -> None:
        """Test edge cases for datetime display formatting."""
        # Remove config format
        display_config.display_datetime_format = None
        formatter = TimeFormatter(display_config)
        
        # Test single digit month and day
        dt = datetime(2024, 1, 5, 9, 5, 0)
        result = formatter.format_datetime_display(dt)
        assert result == "1/5/2024 9:05 AM"
        
        # Test double digit month and day
        dt = datetime(2024, 12, 31, 23, 59, 0)
        result = formatter.format_datetime_display(dt)
        assert result == "12/31/2024 11:59 PM"

    def test_timestamp_conversions(self, formatter: TimeFormatter) -> None:
        """Test various timestamp conversions."""
        # Test negative timestamp (before Unix epoch)
        negative_timestamp = -86400  # 1 day before epoch
        result = formatter.format_datetime(negative_timestamp)
        assert isinstance(result, str)
        
        # Test very large timestamp (far future)
        future_timestamp = 2147483647  # Max 32-bit timestamp
        result = formatter.format_datetime(future_timestamp)
        assert isinstance(result, str)
        
        # Test timestamp for display
        result = formatter.format_datetime_display(future_timestamp)
        assert isinstance(result, str)