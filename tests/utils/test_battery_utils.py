"""Tests for the battery_utils module."""

from datetime import datetime, timedelta

import pytest

from rpi_weather_display.constants import (
    ABNORMAL_DISCHARGE_FACTOR,
    BATTERY_EMPTY_THRESHOLD,
    BATTERY_FULL_THRESHOLD,
    BATTERY_HIGH_THRESHOLD,
    BATTERY_LOW_THRESHOLD,
    MOCK_BATTERY_CURRENT,
    MOCK_BATTERY_LEVEL,
    MOCK_BATTERY_TEMPERATURE,
    MOCK_BATTERY_VOLTAGE,
)
from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils import (
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
        level=MOCK_BATTERY_LEVEL,
        voltage=MOCK_BATTERY_VOLTAGE,
        current=-MOCK_BATTERY_CURRENT,  # Negative for discharging
        temperature=MOCK_BATTERY_TEMPERATURE,
        state=BatteryState.DISCHARGING,
        time_remaining=300,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def low_battery() -> BatteryStatus:
    """Create a low battery status for testing."""
    return BatteryStatus(
        level=15,
        voltage=MOCK_BATTERY_VOLTAGE - 0.2,  # 3.5V
        current=-MOCK_BATTERY_CURRENT,  # -150mA
        temperature=MOCK_BATTERY_TEMPERATURE + 6.0,  # 28.0°C
        state=BatteryState.DISCHARGING,
        time_remaining=90,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def critical_battery() -> BatteryStatus:
    """Create a critical battery status for testing."""
    return BatteryStatus(
        level=5,
        voltage=MOCK_BATTERY_VOLTAGE - 0.5,  # 3.2V
        current=-180.0,
        temperature=MOCK_BATTERY_TEMPERATURE + 8.0,  # 30.0°C
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
        temperature=MOCK_BATTERY_TEMPERATURE + 10.0,  # 32.0°C
        state=BatteryState.CHARGING,
        time_remaining=None,
        timestamp=datetime.now(),
    )


@pytest.fixture()
def full_battery() -> BatteryStatus:
    """Create a full battery status for testing."""
    return BatteryStatus(
        level=BATTERY_FULL_THRESHOLD,
        voltage=4.2,
        current=0.0,
        temperature=MOCK_BATTERY_TEMPERATURE + 3.0,  # 25.0°C
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
    normal_battery: BatteryStatus, low_battery: BatteryStatus, critical_battery: BatteryStatus,
    charging_battery: BatteryStatus
) -> None:
    """Test is_battery_critical function."""
    # Normal battery should not be critical
    assert is_battery_critical(normal_battery, BATTERY_EMPTY_THRESHOLD) is False

    # Low battery should not be critical with threshold of 10
    assert is_battery_critical(low_battery, BATTERY_EMPTY_THRESHOLD) is False

    # Low battery should be critical with threshold of 20
    assert is_battery_critical(low_battery, BATTERY_LOW_THRESHOLD) is True

    # Critical battery should be critical with threshold of 10
    assert is_battery_critical(critical_battery, BATTERY_EMPTY_THRESHOLD) is True
    
    # Charging battery with low level should not be critical
    low_charging = charging_battery.model_copy(update={"level": 5})
    assert is_battery_critical(low_charging, BATTERY_EMPTY_THRESHOLD) is False


def test_is_battery_low(
    normal_battery: BatteryStatus, low_battery: BatteryStatus, critical_battery: BatteryStatus,
    charging_battery: BatteryStatus
) -> None:
    """Test is_battery_low function."""
    # Normal battery should not be low
    assert is_battery_low(normal_battery, BATTERY_LOW_THRESHOLD) is False

    # Low battery (15%) should be low with threshold of 30
    assert is_battery_low(low_battery, BATTERY_LOW_THRESHOLD) is True

    # Critical battery should be low
    assert is_battery_low(critical_battery, BATTERY_LOW_THRESHOLD) is True
    
    # Charging battery with low level should not be considered low
    low_charging = charging_battery.model_copy(update={"level": 15})
    assert is_battery_low(low_charging, BATTERY_LOW_THRESHOLD) is False


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
    # Test battery icon for normal battery (75% = high)
    assert get_battery_icon(normal_battery) == "battery-high-bold"

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
    assert get_battery_text_description(normal_battery) == f"Battery: {MOCK_BATTERY_LEVEL}%"

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

    # Slightly above expected (not abnormal with default factor ABNORMAL_DISCHARGE_FACTOR)
    assert is_discharge_rate_abnormal(6.0, 5.0) is False
    assert is_discharge_rate_abnormal(7.0, 5.0) is False

    # Abnormal rate (exactly at threshold with ABNORMAL_DISCHARGE_FACTOR = 1.5)
    assert is_discharge_rate_abnormal(5.0 * ABNORMAL_DISCHARGE_FACTOR, 5.0) is True

    # Highly abnormal rate
    assert is_discharge_rate_abnormal(10.0, 5.0) is True

    # Custom factor
    assert is_discharge_rate_abnormal(6.0, 5.0, factor=1.2) is True  # 20% higher threshold
    assert is_discharge_rate_abnormal(6.0, 5.0, factor=2.0) is False  # 100% higher threshold

    # Invalid input cases
    assert is_discharge_rate_abnormal(0, 5.0) is False
    assert is_discharge_rate_abnormal(5.0, 0) is False
    assert is_discharge_rate_abnormal(-1.0, 5.0) is False


def test_get_battery_icon_high_battery(normal_battery: BatteryStatus) -> None:
    """Test get_battery_icon for high battery levels (75-90%)."""
    # Test battery at 85% (high but not full)
    high_battery = normal_battery.model_copy(update={"level": 85})
    assert get_battery_icon(high_battery) == "battery-high-bold"
    
    # Test battery at just above high threshold
    high_battery = normal_battery.model_copy(update={"level": BATTERY_HIGH_THRESHOLD + 1})
    assert get_battery_icon(high_battery) == "battery-high-bold"


def test_estimate_remaining_time(
    normal_battery: BatteryStatus,
    charging_battery: BatteryStatus,
    full_battery: BatteryStatus,
) -> None:
    """Test estimate_remaining_time function."""
    # Normal discharging battery should return time remaining
    assert estimate_remaining_time(normal_battery) == 300
    
    # Charging battery should return None
    assert estimate_remaining_time(charging_battery) is None
    
    # Full battery should return None
    assert estimate_remaining_time(full_battery) is None
    
    # Discharging battery with no time estimate should return None
    no_time_battery = normal_battery.model_copy(update={"time_remaining": None})
    assert estimate_remaining_time(no_time_battery) is None
    
    # Unknown state with time should return the time
    unknown_battery = normal_battery.model_copy(update={"state": BatteryState.UNKNOWN})
    assert estimate_remaining_time(unknown_battery) == 300


def test_calculate_drain_rate_edge_cases(battery_history: list[BatteryStatus]) -> None:
    """Test calculate_drain_rate with additional edge cases."""
    # Test with history where first reading has no timestamp
    no_timestamp_history = battery_history.copy()
    no_timestamp_history[-1].timestamp = None  # Oldest reading has no timestamp
    assert calculate_drain_rate(no_timestamp_history) is None
    
    # Test with zero time difference (same timestamp)
    same_time_history = battery_history.copy()
    same_time_history[0].timestamp = same_time_history[-1].timestamp
    assert calculate_drain_rate(same_time_history) is None
    
    # Test with only one discharging reading followed by charging
    mixed_history = [
        battery_history[0],  # Discharging
        battery_history[1].model_copy(update={"state": BatteryState.CHARGING}),  # Charging
        battery_history[2],  # Discharging
    ]
    # Should only use the first discharging reading, which is insufficient
    assert calculate_drain_rate(mixed_history) is None
    
    # Test with negative time difference (timestamps in wrong order)
    wrong_order_history = battery_history.copy()
    # Make sure all have timestamps first
    base_time = datetime.now()
    wrong_order_history[0].timestamp = base_time - timedelta(hours=3)  # Older than oldest
    wrong_order_history[1].timestamp = base_time - timedelta(hours=1)
    wrong_order_history[2].timestamp = base_time - timedelta(hours=2)
    assert calculate_drain_rate(wrong_order_history) is None
