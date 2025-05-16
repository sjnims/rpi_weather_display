"""Tests for the PowerStateManager class."""

# ruff: noqa: S101, A002, PLR2004
# pyright: reportPrivateUsage=false

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    LoggingConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils import PowerState, PowerStateManager


@pytest.fixture()
def default_config() -> AppConfig:
    """Create a default app config for testing."""
    return AppConfig(
        weather=WeatherConfig(
            api_key="test_key",
            location={"lat": 0.0, "lon": 0.0},
            update_interval_minutes=30,
        ),
        display=DisplayConfig(refresh_interval_minutes=30),
        power=PowerConfig(
            quiet_hours_start="23:00",
            quiet_hours_end="06:00",
            low_battery_threshold=20,
            critical_battery_threshold=10,
            wake_up_interval_minutes=60,
        ),
        server=ServerConfig(url="http://localhost"),
        logging=LoggingConfig(),
        debug=False,
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
def power_manager(default_config: AppConfig) -> PowerStateManager:
    """Create a PowerStateManager with the default config."""
    return PowerStateManager(default_config)


class TestPowerStateManager:
    """Tests for the PowerStateManager class."""

    def test_init(self, default_config: AppConfig) -> None:
        """Test initialization of the power state manager."""
        manager = PowerStateManager(default_config)
        assert manager.config == default_config
        assert manager.get_internal_state_for_testing() == PowerState.NORMAL
        assert not manager.get_initialization_status_for_testing()
        assert manager.get_last_refresh_for_testing() is None
        assert manager.get_last_update_for_testing() is None

    def test_get_battery_status_mock(self, power_manager: PowerStateManager) -> None:
        """Test that get_battery_status returns a mock when not initialized."""
        status = power_manager.get_battery_status()
        assert status.level == 75
        assert status.state == BatteryState.DISCHARGING
        assert status.timestamp is not None

    def test_get_current_state(self, power_manager: PowerStateManager) -> None:
        """Test get_current_state updates the power state before returning."""
        with patch.object(power_manager, "_update_power_state") as mock_update:
            state = power_manager.get_current_state()
            mock_update.assert_called_once()
            assert state == PowerState.NORMAL

    def test_update_power_state_charging(
        self, power_manager: PowerStateManager, charging_battery: BatteryStatus
    ) -> None:
        """Test _update_power_state with a charging battery."""
        with patch.object(power_manager, "get_battery_status", return_value=charging_battery):
            power_manager._update_power_state()
            assert power_manager.get_internal_state_for_testing() == PowerState.CHARGING

    def test_update_power_state_critical(
        self, power_manager: PowerStateManager, critical_battery: BatteryStatus
    ) -> None:
        """Test _update_power_state with a critical battery."""
        with (
            patch.object(power_manager, "get_battery_status", return_value=critical_battery),
            patch("rpi_weather_display.utils.power_manager.is_quiet_hours", return_value=False),
        ):
            power_manager._update_power_state()
            assert power_manager.get_internal_state_for_testing() == PowerState.CRITICAL

    def test_update_power_state_conserving(
        self, power_manager: PowerStateManager, low_battery: BatteryStatus
    ) -> None:
        """Test _update_power_state with a low battery."""
        with (
            patch.object(power_manager, "get_battery_status", return_value=low_battery),
            patch("rpi_weather_display.utils.power_manager.is_quiet_hours", return_value=False),
            patch(
                "rpi_weather_display.utils.power_manager.should_conserve_power", return_value=True
            ),
        ):
            power_manager._update_power_state()
            assert power_manager.get_internal_state_for_testing() == PowerState.CONSERVING

    def test_update_power_state_quiet_hours(
        self, power_manager: PowerStateManager, normal_battery: BatteryStatus
    ) -> None:
        """Test _update_power_state during quiet hours."""
        with (
            patch.object(power_manager, "get_battery_status", return_value=normal_battery),
            patch("rpi_weather_display.utils.power_manager.is_quiet_hours", return_value=True),
        ):
            power_manager._update_power_state()
            assert power_manager.get_internal_state_for_testing() == PowerState.QUIET_HOURS

    def test_state_change_notification(self, power_manager: PowerStateManager) -> None:
        """Test state change notification mechanism."""
        callback = MagicMock()
        power_manager.register_state_change_callback(callback)

        # Force a state change
        old_state = power_manager.get_internal_state_for_testing()
        new_state = PowerState.CONSERVING
        # We need to call _notify_state_change directly to test it
        power_manager._notify_state_change(old_state, new_state)

        callback.assert_called_once_with(old_state, new_state)

    def test_should_refresh_display(self, power_manager: PowerStateManager) -> None:
        """Test should_refresh_display under different conditions."""
        # Critical state - should not refresh
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CRITICAL):
            assert not power_manager.should_refresh_display()

        # Quiet hours without charging - should not refresh
        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS),
            patch.object(power_manager, "get_battery_status") as mock_battery,
        ):
            mock_battery.return_value = BatteryStatus(
                level=50,
                voltage=3.7,
                current=-100.0,
                temperature=25.0,
                state=BatteryState.DISCHARGING,
            )
            assert not power_manager.should_refresh_display()

        # Quiet hours with charging - should refresh
        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS),
            patch.object(power_manager, "get_battery_status") as mock_battery,
        ):
            mock_battery.return_value = BatteryStatus(
                level=50, voltage=3.7, current=500.0, temperature=25.0, state=BatteryState.CHARGING
            )
            # First refresh - should refresh
            assert power_manager.should_refresh_display()

    def test_should_refresh_display_intervals(self, power_manager: PowerStateManager) -> None:
        """Test refresh interval behavior in different states."""
        # First refresh - no previous refresh time
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert power_manager.should_refresh_display()

        # Set last refresh time to now
        now = datetime.now()
        power_manager.set_last_refresh_for_testing(now)

        # Not enough time has passed in normal state
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert not power_manager.should_refresh_display()

        # Enough time has passed in normal state
        power_manager.set_last_refresh_for_testing(now - timedelta(minutes=31))
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert power_manager.should_refresh_display()

        # Not enough time has passed in conserving state (doubled interval)
        power_manager.set_last_refresh_for_testing(now - timedelta(minutes=31))
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING):
            assert not power_manager.should_refresh_display()

        # Enough time has passed in conserving state (doubled interval)
        power_manager.set_last_refresh_for_testing(now - timedelta(minutes=61))
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING):
            assert power_manager.should_refresh_display()

    def test_schedule_wakeup(self, power_manager: PowerStateManager) -> None:
        """Test schedule_wakeup function."""
        # Not initialized - should return mock result
        assert power_manager.schedule_wakeup(30)

    def test_can_perform_operation(self, power_manager: PowerStateManager) -> None:
        """Test can_perform_operation in different power states."""
        # Normal state allows all operations
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert power_manager.can_perform_operation("display", 2.0)
            assert power_manager.can_perform_operation("network", 3.0)

        # Charging state allows all operations
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CHARGING):
            assert power_manager.can_perform_operation("display", 2.0)
            assert power_manager.can_perform_operation("network", 3.0)

        # Critical state only allows very low-cost operations
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CRITICAL):
            assert not power_manager.can_perform_operation("display", 1.0)
            assert power_manager.can_perform_operation("display", 0.4)

        # Conserving state restricts expensive operations
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING):
            assert not power_manager.can_perform_operation("display", 1.5)
            assert power_manager.can_perform_operation("display", 1.0)

        # Quiet hours restrict certain operation types
        with patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS):
            assert not power_manager.can_perform_operation("network", 0.6)
            assert not power_manager.can_perform_operation("display", 0.3)
            assert power_manager.can_perform_operation("network", 0.4)
            assert power_manager.can_perform_operation("display", 0.1)

    def test_enter_low_power_mode(self, power_manager: PowerStateManager) -> None:
        """Test enter_low_power_mode forces state to conserving."""
        with patch.object(power_manager, "_notify_state_change") as mock_notify:
            power_manager.enter_low_power_mode()
            assert power_manager.get_internal_state_for_testing() == PowerState.CONSERVING
            mock_notify.assert_called_once()
