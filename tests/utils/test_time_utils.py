"""Tests for the time_utils module."""

from freezegun import freeze_time

from rpi_weather_display.utils import is_quiet_hours


@freeze_time("2023-01-01 00:00:00")  # Midnight
def test_is_quiet_hours_midnight() -> None:
    """Test is_quiet_hours at midnight."""
    # Default quiet hours are 23:00-06:00, so midnight should be quiet
    assert is_quiet_hours("23:00", "06:00") is True


@freeze_time("2023-01-01 12:00:00")  # Noon
def test_is_quiet_hours_noon() -> None:
    """Test is_quiet_hours at noon."""
    # Noon is not in quiet hours
    assert is_quiet_hours("23:00", "06:00") is False


@freeze_time("2023-01-01 23:30:00")  # Late night
def test_is_quiet_hours_late() -> None:
    """Test is_quiet_hours late at night."""
    # 23:30 is in quiet hours
    assert is_quiet_hours("23:00", "06:00") is True


@freeze_time("2023-01-01 05:30:00")  # Early morning
def test_is_quiet_hours_early() -> None:
    """Test is_quiet_hours early in the morning."""
    # 5:30 is in quiet hours
    assert is_quiet_hours("23:00", "06:00") is True


def test_is_quiet_hours_invalid_format() -> None:
    """Test is_quiet_hours with invalid time format."""
    # Should return False on invalid format
    assert is_quiet_hours("invalid", "format") is False


def test_is_quiet_hours_daytime_span() -> None:
    """Test is_quiet_hours with daytime span (no overnight)."""
    # Set quiet hours to a daytime span
    with freeze_time("2023-01-01 12:00:00"):  # Noon
        assert is_quiet_hours("09:00", "17:00") is True

    with freeze_time("2023-01-01 20:00:00"):  # Evening
        assert is_quiet_hours("09:00", "17:00") is False
