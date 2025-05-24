"""Battery utility functions for the Raspberry Pi weather display.

Provides common battery state and power management utilities used across the application.
"""

from rpi_weather_display.constants import (
    ABNORMAL_DISCHARGE_FACTOR,
    BATTERY_EMPTY_THRESHOLD,
    BATTERY_FULL_THRESHOLD,
    BATTERY_HIGH_THRESHOLD,
    BATTERY_LOW_THRESHOLD,
    SECONDS_PER_HOUR,
)
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
    match status.state:
        case BatteryState.CHARGING:
            return True
        case _:
            return False


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
    elif status.level >= BATTERY_FULL_THRESHOLD:
        return "battery-full-bold"
    elif status.level > BATTERY_HIGH_THRESHOLD:
        return "battery-high-bold"
    elif status.level > BATTERY_LOW_THRESHOLD:
        return "battery-medium-bold"
    elif status.level > BATTERY_EMPTY_THRESHOLD:
        return "battery-low-bold"
    else:
        return "battery-empty-bold"


def get_battery_text_description(status: BatteryStatus) -> str:
    """Get a human-readable description of the battery status.

    Args:
        status: Current battery status

    Returns:
        Text description of battery status
    """
    match (status.state, status.level):
        case (BatteryState.CHARGING, level):
            return f"Charging ({level}%)"
        case (BatteryState.FULL, _):
            return "Fully Charged"
        case (_, level) if level < BATTERY_EMPTY_THRESHOLD:
            return f"Critical ({level}%)"
        case (_, level) if level < BATTERY_LOW_THRESHOLD:
            return f"Low ({level}%)"
        case (_, level):
            return f"Battery: {level}%"


def estimate_remaining_time(status: BatteryStatus) -> int | None:
    """Estimate remaining battery time in minutes.

    Uses the time_remaining property from the BatteryStatus object,
    which is typically calculated based on battery capacity and 
    current discharge rate.

    Args:
        status: Current battery status containing time_remaining data

    Returns:
        int: Estimated battery time in minutes
        None: If battery is charging or if time cannot be estimated
    """
    match (status.state, status.time_remaining):
        case (BatteryState.CHARGING | BatteryState.FULL, _):
            return None  # No time estimate when charging or full
        case (_, None):
            return None  # No estimate available
        case (_, time):
            return time


def calculate_drain_rate(status_history: list[BatteryStatus]) -> float | None:
    """Calculate battery drain rate in percent per hour.

    Analyzes the battery level changes over time to determine the rate at which
    the battery is discharging. This is used for power management decisions and
    to estimate remaining battery life.

    Args:
        status_history: List of battery status readings, most recent first.
                        Each status must have a valid timestamp property set.
                        The list should contain at least 2 BatteryStatus objects
                        with consecutive DISCHARGING state for valid calculation.

    Returns:
        float: Drain rate in percent per hour (positive value)
        None: If insufficient data or if timestamps are missing/invalid
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
    time_diff = (last.timestamp - first.timestamp).total_seconds() / SECONDS_PER_HOUR
    if time_diff <= 0:
        return None

    # Calculate level difference (positive means draining)
    level_diff = first.level - last.level
    return level_diff / time_diff  # % per hour


def is_discharge_rate_abnormal(
    drain_rate: float, expected_rate: float, factor: float = ABNORMAL_DISCHARGE_FACTOR
) -> bool:
    """Check if the discharge rate is abnormally high.

    Args:
        drain_rate: Current drain rate in percent per hour
        expected_rate: Expected drain rate in percent per hour
        factor: Factor to determine abnormal discharge 
            (e.g., 1.5 means 50% higher than expected is abnormal)

    Returns:
        True if discharge rate is abnormally high
    """
    if drain_rate <= 0 or expected_rate <= 0:
        return False

    # Consider abnormal if rate exceeds expected rate by the factor
    return drain_rate >= (expected_rate * factor)
