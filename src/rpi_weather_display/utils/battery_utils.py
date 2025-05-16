"""Battery utility functions for the Raspberry Pi weather display.

Provides common battery state and power management utilities used across the application.
"""

from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus


def is_battery_critical(status: BatteryStatus, threshold: int) -> bool:
    """Check if the battery is at a critical level.

    Args:
        status: Current battery status
        threshold: Critical battery threshold percentage

    Returns:
        True if the battery is at critical level and not charging
    """
    return status.level < threshold and status.state != BatteryState.CHARGING


def is_battery_low(status: BatteryStatus, threshold: int) -> bool:
    """Check if the battery is at a low level.

    Args:
        status: Current battery status
        threshold: Low battery threshold percentage

    Returns:
        True if the battery is at low level and not charging
    """
    return status.level < threshold and status.state != BatteryState.CHARGING


def is_charging(status: BatteryStatus) -> bool:
    """Check if the battery is currently charging.

    Args:
        status: Current battery status

    Returns:
        True if the battery is charging
    """
    return status.state == BatteryState.CHARGING


def should_conserve_power(status: BatteryStatus, config: PowerConfig) -> bool:
    """Check if power conservation measures should be activated.

    Args:
        status: Current battery status
        config: Power configuration

    Returns:
        True if power conservation should be activated
    """
    # Conserve power when battery is low or critical and not charging
    return (status.level < config.low_battery_threshold) and status.state != BatteryState.CHARGING


def should_double_intervals(
    status: BatteryStatus, config: PowerConfig, in_quiet_hours: bool = False
) -> bool:
    """Check if refresh/update intervals should be doubled to conserve power.

    Args:
        status: Current battery status
        config: Power configuration
        in_quiet_hours: Whether currently in quiet hours

    Returns:
        True if intervals should be doubled
    """
    # Don't double intervals during quiet hours regardless of battery status
    if in_quiet_hours:
        return False

    # Double intervals when battery is low and not charging
    return (status.level < config.low_battery_threshold) and status.state != BatteryState.CHARGING


def get_battery_icon(status: BatteryStatus) -> str:
    """Get the appropriate battery icon ID from sprite.

    Args:
        status: Current battery status

    Returns:
        Icon ID from the sprite
    """
    if status.state == BatteryState.CHARGING:
        return "battery-charging-bold"
    elif status.level == 0:
        return "battery-empty-bold"
    elif status.level > 80:
        return "battery-full-bold"
    elif status.level > 30:
        return "battery-high-bold"
    else:
        return "battery-low-bold"


def get_battery_text_description(status: BatteryStatus) -> str:
    """Get a human-readable description of the battery status.

    Args:
        status: Current battery status

    Returns:
        Text description of battery status
    """
    if status.state == BatteryState.CHARGING:
        return f"Charging ({status.level}%)"
    elif status.state == BatteryState.FULL:
        return "Fully Charged"
    elif status.level < 10:
        return f"Critical ({status.level}%)"
    elif status.level < 20:
        return f"Low ({status.level}%)"
    else:
        return f"Battery: {status.level}%"


def estimate_remaining_time(status: BatteryStatus) -> int | None:
    """Estimate remaining battery time in minutes.

    Args:
        status: Current battery status

    Returns:
        Estimated battery time in minutes, or None if charging or unknown
    """
    return status.time_remaining


def calculate_drain_rate(status_history: list[BatteryStatus]) -> float | None:
    """Calculate battery drain rate in percent per hour.

    Args:
        status_history: List of battery status readings, most recent first
                        Each status should have a timestamp

    Returns:
        Drain rate in percent per hour, or None if insufficient data
    """
    if len(status_history) < 2:
        return None

    # Only use consecutive discharging readings
    discharging_readings: list[BatteryStatus] = []
    for status in status_history:
        if status.state != BatteryState.DISCHARGING:
            break
        discharging_readings.append(status)

    if len(discharging_readings) < 2:
        return None

    # Calculate drain rate from first and last discharging readings
    first = discharging_readings[-1]  # Oldest
    last = discharging_readings[0]  # Newest

    # Skip if any timestamps are missing
    if not first.timestamp or not last.timestamp:
        return None

    # Calculate time difference in hours
    time_diff = (last.timestamp - first.timestamp).total_seconds() / 3600
    if time_diff <= 0:
        return None

    # Calculate level difference (positive means draining)
    level_diff = first.level - last.level
    return level_diff / time_diff  # % per hour


def is_discharge_rate_abnormal(
    drain_rate: float, expected_rate: float, tolerance: float = 0.3
) -> bool:
    """Check if the discharge rate is abnormally high.

    Args:
        drain_rate: Current drain rate in percent per hour
        expected_rate: Expected drain rate in percent per hour
        tolerance: Tolerance factor (e.g., 0.3 means 30% above expected is abnormal)

    Returns:
        True if discharge rate is abnormally high
    """
    if drain_rate <= 0 or expected_rate <= 0:
        return False

    # Consider abnormal if rate exceeds expected rate by the tolerance percentage
    return drain_rate >= (expected_rate * (1 + tolerance))
