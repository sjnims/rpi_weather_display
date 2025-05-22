"""Tests for the battery_utils module."""

from datetime import datetime, timedelta

import pytest

from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils import (
    calculate_drain_rate,
    get_battery_icon,
    get_battery_text_description,
    is_battery_critical,
    is_battery_low,
    is_charging,
    is_discharge_rate_abnormal,
    should_conserve_power,
    should_double_intervals,
)


@pytest.fixture()
def power_config() -> PowerConfig:
    """Create a power configuration for testing."""
    return PowerConfig(
        quiet_hours_start="23:00",
        quiet_hours_end="06:00",
        low_battery_threshold=20,
        critical_battery_threshold=10,
        wake_up_interval_minutes=60,
        wifi_timeout_seconds=30,
    )


@pytest.fixture()
def normal_battery() -> BatteryStatus:
    """Create a normal battery status for testing."""
    return BatteryStatus(
        level=50,
        voltage=3.7,
        current=-100.0,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
        time_remaining=300,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def low_battery() -> BatteryStatus:
    """Create a low battery status for testing."""
    return BatteryStatus(
        level=15,
        voltage=3.5,
        current=-150.0,
        temperature=28.0,
        state=BatteryState.DISCHARGING,
        time_remaining=90,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def critical_battery() -> BatteryStatus:
    """Create a critical battery status for testing."""
    return BatteryStatus(
        level=5,
        voltage=3.2,
        current=-180.0,
        temperature=30.0,
        state=BatteryState.DISCHARGING,
        time_remaining=30,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def charging_battery() -> BatteryStatus:
    """Create a charging battery status for testing."""
    return BatteryStatus(
        level=25,
        voltage=4.1,
        current=500.0,
        temperature=32.0,
        state=BatteryState.CHARGING,
        time_remaining=None,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def full_battery() -> BatteryStatus:
    """Create a full battery status for testing."""
    return BatteryStatus(
        level=100,
        voltage=4.2,
        current=0.0,
        temperature=25.0,
        state=BatteryState.FULL,
        time_remaining=None,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def battery_history() -> list[BatteryStatus]:
    """Create a history of battery readings for testing."""
    base_time = datetime.now()
    return [
        # Most recent first
        BatteryStatus(
            level=70,
            voltage=3.9,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=base_time,
        ),
        BatteryStatus(
            level=75,
            voltage=3.95,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=base_time - timedelta(hours=1),
        ),
        BatteryStatus(
            level=80,
            voltage=4.0,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=base_time - timedelta(hours=2),
        ),
    ]


def test_is_battery_critical(
    normal_battery: BatteryStatus, low_battery: BatteryStatus, critical_battery: BatteryStatus
) -> None:
    """Test is_battery_critical function."""
    # Normal battery should not be critical
    assert is_battery_critical(normal_battery, 10) is False

    # Low battery should not be critical with threshold of 10
    assert is_battery_critical(low_battery, 10) is False

    # Low battery should be critical with threshold of 20
    assert is_battery_critical(low_battery, 20) is True

    # Critical battery should be critical with threshold of 10
    assert is_battery_critical(critical_battery, 10) is True


def test_is_battery_low(
    normal_battery: BatteryStatus, low_battery: BatteryStatus, critical_battery: BatteryStatus
) -> None:
    """Test is_battery_low function."""
    # Normal battery should not be low
    assert is_battery_low(normal_battery, 20) is False

    # Low battery (15%) should be low with threshold of 20
    assert is_battery_low(low_battery, 20) is True

    # Critical battery should be low
    assert is_battery_low(critical_battery, 20) is True


def test_is_charging(normal_battery: BatteryStatus, charging_battery: BatteryStatus) -> None:
    """Test is_charging function."""
    # Normal battery is not charging
    assert is_charging(normal_battery) is False

    # Charging battery is charging
    assert is_charging(charging_battery) is True


def test_should_conserve_power(
    normal_battery: BatteryStatus,
    low_battery: BatteryStatus,
    critical_battery: BatteryStatus,
    charging_battery: BatteryStatus,
    power_config: PowerConfig,
) -> None:
    """Test should_conserve_power function."""
    # Normal battery should not require conservation
    assert should_conserve_power(normal_battery, power_config) is False

    # Low battery should require conservation
    assert should_conserve_power(low_battery, power_config) is True

    # Critical battery should require conservation
    assert should_conserve_power(critical_battery, power_config) is True

    # Even if battery level is low, if charging, don't conserve power
    charging_battery.level = 15  # Low but charging
    assert should_conserve_power(charging_battery, power_config) is False


def test_should_double_intervals(
    normal_battery: BatteryStatus,
    low_battery: BatteryStatus,
    charging_battery: BatteryStatus,
    power_config: PowerConfig,
) -> None:
    """Test should_double_intervals function."""
    # Normal battery should not double intervals
    assert should_double_intervals(normal_battery, power_config) is False

    # Low battery should double intervals
    assert should_double_intervals(low_battery, power_config) is True

    # Low battery during quiet hours should not double intervals
    assert should_double_intervals(low_battery, power_config, in_quiet_hours=True) is False

    # Even if battery level is low, if charging, don't double intervals
    charging_battery.level = 15  # Low but charging
    assert should_double_intervals(charging_battery, power_config) is False


def test_get_battery_icon(
    normal_battery: BatteryStatus,
    low_battery: BatteryStatus,
    critical_battery: BatteryStatus,
    charging_battery: BatteryStatus,
    full_battery: BatteryStatus,
) -> None:
    """Test get_battery_icon function."""
    # Test battery icon for normal battery
    assert get_battery_icon(normal_battery) == "battery-medium-bold"

    # Test battery icon for low battery
    assert get_battery_icon(low_battery) == "battery-low-bold"

    # Test battery icon for critical battery
    assert get_battery_icon(critical_battery) == "battery-empty-bold"

    # Test battery icon for charging battery
    assert get_battery_icon(charging_battery) == "battery-charging-bold"

    # Test battery icon for full battery
    assert get_battery_icon(full_battery) == "battery-full-bold"

    # Test battery icon for empty battery
    empty_battery = normal_battery.model_copy(update={"level": 0})
    assert get_battery_icon(empty_battery) == "battery-empty-bold"


def test_get_battery_text_description(
    normal_battery: BatteryStatus,
    low_battery: BatteryStatus,
    critical_battery: BatteryStatus,
    charging_battery: BatteryStatus,
    full_battery: BatteryStatus,
) -> None:
    """Test get_battery_text_description function."""
    # Normal battery description
    assert get_battery_text_description(normal_battery) == "Battery: 50%"

    # Low battery description
    assert get_battery_text_description(low_battery) == "Low (15%)"

    # Critical battery description
    assert get_battery_text_description(critical_battery) == "Critical (5%)"

    # Charging battery description
    assert get_battery_text_description(charging_battery) == "Charging (25%)"

    # Full battery description
    assert get_battery_text_description(full_battery) == "Fully Charged"


def test_calculate_drain_rate(battery_history: list[BatteryStatus]) -> None:
    """Test calculate_drain_rate function."""
    # Test with normal history (5% per hour drain rate)
    rate = calculate_drain_rate(battery_history)
    assert rate is not None
    assert 4.5 < rate < 5.5, f"Expected ~5% per hour, got {rate}%"

    # Test with insufficient history
    assert calculate_drain_rate(battery_history[:1]) is None

    # Test with mixed states
    mixed_history = battery_history.copy()
    mixed_history[1].state = BatteryState.CHARGING
    assert calculate_drain_rate(mixed_history) is None

    # Test with invalid timestamps
    invalid_history = battery_history.copy()
    invalid_history[0].timestamp = None
    assert calculate_drain_rate(invalid_history) is None

    # Test with timestamps in wrong order
    wrong_order = battery_history.copy()
    wrong_order[0].timestamp = battery_history[2].timestamp
    assert calculate_drain_rate(wrong_order) is None


def test_is_discharge_rate_abnormal() -> None:
    """Test is_discharge_rate_abnormal function."""
    # Normal rate (5% per hour with expected 5%)
    assert is_discharge_rate_abnormal(5.0, 5.0) is False

    # Slightly above expected (not abnormal with default factor 1.5)
    assert is_discharge_rate_abnormal(6.0, 5.0) is False
    assert is_discharge_rate_abnormal(7.0, 5.0) is False

    # Abnormal rate (50% higher with default factor 1.5)
    assert is_discharge_rate_abnormal(7.5, 5.0) is True

    # Highly abnormal rate
    assert is_discharge_rate_abnormal(10.0, 5.0) is True

    # Custom factor
    assert is_discharge_rate_abnormal(6.0, 5.0, factor=1.2) is True  # 20% higher threshold
    assert is_discharge_rate_abnormal(6.0, 5.0, factor=2.0) is False  # 100% higher threshold

    # Invalid input cases
    assert is_discharge_rate_abnormal(0, 5.0) is False
    assert is_discharge_rate_abnormal(5.0, 0) is False
    assert is_discharge_rate_abnormal(-1.0, 5.0) is False
