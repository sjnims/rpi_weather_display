"""Module initialization."""

from rpi_weather_display.utils.battery_utils import (
    calculate_drain_rate,
    estimate_remaining_time,
    get_battery_icon,
    get_battery_text_description,
    is_battery_critical,
    is_battery_low,
    is_charging,
    is_discharge_rate_abnormal,
    should_conserve_power,
    should_double_intervals,
)
from rpi_weather_display.utils.power_manager import (
    PowerState,
    PowerStateCallback,
    PowerStateManager,
)
from rpi_weather_display.utils.time_utils import is_quiet_hours

__all__ = [
    # Time utilities
    "is_quiet_hours",
    # Battery utilities
    "is_battery_critical",
    "is_battery_low",
    "is_charging",
    "should_conserve_power",
    "should_double_intervals",
    "get_battery_icon",
    "get_battery_text_description",
    "estimate_remaining_time",
    "calculate_drain_rate",
    "is_discharge_rate_abnormal",
    # Power manager
    "PowerState",
    "PowerStateCallback",
    "PowerStateManager",
]
