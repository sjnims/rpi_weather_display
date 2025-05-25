"""Tests for the PowerStateController module."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.models.config import AppConfig, DisplayConfig, PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils.battery_monitor import BatteryMonitor
from rpi_weather_display.utils.pijuice_adapter import PiJuiceAdapter
from rpi_weather_display.utils.power_state_controller import (
    PowerState,
    PowerStateCallback,
    PowerStateController,
)

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.test_helpers.power_manager_test_helpers import PowerStateControllerTestHelper


@pytest.fixture()
def mock_config() -> AppConfig:
    """Create a mock configuration for testing."""
    config = MagicMock(spec=AppConfig)
    config.development_mode = False

    # Mock power config
    config.power = MagicMock(spec=PowerConfig)
    config.power.quiet_hours_start = "23:00"
    config.power.quiet_hours_end = "06:00"
    config.power.low_battery_threshold = 20
    config.power.critical_battery_threshold = 10
    config.power.wake_up_interval_minutes = 60

    # Mock display config
    config.display = MagicMock(spec=DisplayConfig)
    config.display.refresh_interval_minutes = 30

    return config


@pytest.fixture()
def mock_battery_monitor() -> MagicMock:
    """Create a mock battery monitor."""
    monitor = MagicMock(spec=BatteryMonitor)
    monitor.get_battery_status.return_value = BatteryStatus(
        level=75,
        voltage=3.7,
        current=-100.0,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
        timestamp=datetime.now(),
    )
    monitor.is_battery_critical.return_value = False
    monitor.should_conserve_power.return_value = False
    monitor.is_discharge_rate_abnormal.return_value = False
    return monitor


@pytest.fixture()
def mock_pijuice() -> MagicMock:
    """Create a mock PiJuice adapter."""
    adapter = MagicMock(spec=PiJuiceAdapter)
    adapter.is_initialized.return_value = True
    adapter.configure_event.return_value = True
    return adapter


@pytest.mark.usefixtures("mock_normal_hours_time")
class TestPowerStateController:
    """Test cases for PowerStateController class."""

    def test_init(self, mock_config: AppConfig, mock_battery_monitor: MagicMock) -> None:
        """Test PowerStateController initialization."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        assert controller.config == mock_config
        assert controller.battery_monitor == mock_battery_monitor
        assert controller.pijuice is None
        assert controller._current_state == PowerState.NORMAL
        assert not controller._initialized

    def test_initialize_without_pijuice(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test initialization without PiJuice."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        result = controller.initialize()
        assert result is True
        assert controller._initialized is True

    def test_initialize_with_pijuice(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock, mock_pijuice: MagicMock
    ) -> None:
        """Test initialization with PiJuice."""
        controller = PowerStateController(mock_config, mock_battery_monitor, mock_pijuice)
        result = controller.initialize()
        assert result is True
        assert controller._initialized is True
        # Should configure events
        assert mock_pijuice.configure_event.called

    def test_get_current_state(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test getting current power state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        state = controller.get_current_state()
        assert isinstance(state, PowerState)

    def test_update_power_state_charging(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test power state update when charging."""
        mock_battery_monitor.get_battery_status.return_value = BatteryStatus(
            level=50,
            voltage=4.1,
            current=500.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
            timestamp=datetime.now(),
        )

        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        state = controller.update_power_state()
        assert state == PowerState.CHARGING

    def test_update_power_state_quiet_hours(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test power state during quiet hours."""
        with patch(
            "rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=True
        ):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            state = controller.update_power_state()
            assert state == PowerState.QUIET_HOURS

    def test_update_power_state_critical(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test power state when battery is critical."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            mock_battery_monitor.is_battery_critical.return_value = True

            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            state = controller.update_power_state()
            assert state == PowerState.CRITICAL

    def test_update_power_state_conserving(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test power state when conserving power."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            mock_battery_monitor.should_conserve_power.return_value = True

            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            state = controller.update_power_state()
            assert state == PowerState.CONSERVING

    def test_state_change_callbacks(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test state change callback mechanism."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()

            callback_called = False
            old_state_received = None
            new_state_received = None

            def test_callback(old_state: PowerState, new_state: PowerState) -> None:
                nonlocal callback_called, old_state_received, new_state_received
                callback_called = True
                old_state_received = old_state
                new_state_received = new_state

            callback_obj = controller.register_state_change_callback(test_callback)

            # Force a state change
            controller._current_state = PowerState.NORMAL
            mock_battery_monitor.is_battery_critical.return_value = True
            controller.update_power_state()

            assert callback_called
            assert old_state_received == PowerState.NORMAL
            assert new_state_received == PowerState.CRITICAL

            # Unregister callback
            controller.unregister_state_change_callback(callback_obj)

    def test_should_refresh_display_quiet_hours(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test display refresh decision during quiet hours."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.QUIET_HOURS

        assert not controller.should_refresh_display()

    def test_should_refresh_display_charging(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test display refresh when charging."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CHARGING

        assert controller.should_refresh_display()

    def test_should_refresh_display_interval(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock, mock_normal_hours_time: MagicMock
    ) -> None:
        """Test display refresh interval enforcement."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()

            # First refresh should be allowed
            assert controller.should_refresh_display()

            # Record refresh
            controller.record_display_refresh()

            # Immediate refresh should be blocked
            assert not controller.should_refresh_display()

            # After interval, refresh should be allowed
            # Use the mocked time from the fixture
            controller._last_display_refresh = mock_normal_hours_time.now.return_value - timedelta(minutes=31)
            assert controller.should_refresh_display()

    def test_should_update_weather_quiet_hours(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test weather update decision during quiet hours."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.QUIET_HOURS

        assert not controller.should_update_weather()

    def test_should_update_weather_critical(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test weather update in critical state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CRITICAL
        controller._last_weather_update = datetime.now() - timedelta(minutes=30)

        assert not controller.should_update_weather()

    def test_calculate_sleep_time_development_mode(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation in development mode."""
        mock_config.development_mode = True
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        sleep_time = controller.calculate_sleep_time()
        assert sleep_time == 1  # DEFAULT_MOCK_SLEEP_TIME / SECONDS_PER_MINUTE

    def test_calculate_sleep_time_quiet_hours(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time during quiet hours."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.QUIET_HOURS

        # Mock to prevent state change during calculation
        with (
            patch.object(controller, "_update_power_state"),
            patch.object(controller, "_time_until_quiet_change", return_value=120.0),
        ):
            sleep_time = controller.calculate_sleep_time()
            assert sleep_time == 120

    def test_calculate_sleep_time_critical(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time in critical state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CRITICAL

        # Mock to prevent state change during calculation
        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # Critical state uses CRITICAL_SLEEP_FACTOR (8x)
            expected = min(mock_config.display.refresh_interval_minutes * 8, 720)  # Max 720 minutes
            assert sleep_time == expected

    def test_calculate_sleep_time_charging(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time when charging."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            controller._current_state = PowerState.CHARGING

            sleep_time = controller.calculate_sleep_time()
            assert sleep_time <= mock_config.display.refresh_interval_minutes  # Should be reduced

    def test_can_perform_operation_quiet_hours(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test operation permission during quiet hours."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.QUIET_HOURS

        # Mock to prevent state change during operation check
        with patch.object(controller, "_update_power_state"):
            # Critical operations allowed
            assert controller.can_perform_operation("shutdown")
            assert controller.can_perform_operation("low_battery_warning")

            # Normal operations blocked
            assert not controller.can_perform_operation("display_refresh")
            assert not controller.can_perform_operation("weather_update")

    def test_can_perform_operation_critical(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test operation permission in critical state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CRITICAL

        # Mock to prevent state change during operation check
        with patch.object(controller, "_update_power_state"):
            # Only essential operations allowed
            assert controller.can_perform_operation("shutdown")
            assert not controller.can_perform_operation("weather_update")

    def test_enter_low_power_mode(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test entering low power mode."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            controller._current_state = PowerState.NORMAL

            controller.enter_low_power_mode()
            assert controller._current_state == PowerState.CONSERVING

    def test_time_until_quiet_change(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test quiet hours transition time calculation."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        # Mock current time to be during the day
        with patch("rpi_weather_display.utils.power_state_controller.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 5, 25, 14, 0, 0)
            mock_datetime.strptime = datetime.strptime
            mock_datetime.combine = datetime.combine

            minutes = controller._time_until_quiet_change()
            assert minutes > 0  # Should be positive time until quiet hours start


@pytest.mark.usefixtures("mock_normal_hours_time")
class TestPowerStateControllerCoverage:
    """Additional test cases for complete coverage of PowerStateController."""

    def test_already_initialized(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test initialization when already initialized."""
        controller = PowerStateController(mock_config, mock_battery_monitor)

        # First initialization
        result1 = controller.initialize()
        assert result1 is True

        # Second initialization should return early
        result2 = controller.initialize()
        assert result2 is True

    def test_configure_pijuice_events_no_adapter(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test configuring PiJuice events with no adapter."""
        controller = PowerStateController(mock_config, mock_battery_monitor)

        # This should return early without error
        controller._configure_pijuice_events()

    def test_notify_state_change_with_callback_error(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test state change notification when callback raises error."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()

            # Register a callback that raises an error
            def error_callback(old: PowerState, new: PowerState) -> None:
                raise ValueError("Test error")

            controller.register_state_change_callback(error_callback)

            # Register a normal callback to ensure it still gets called
            normal_called = False

            def normal_callback(old: PowerState, new: PowerState) -> None:
                nonlocal normal_called
                normal_called = True

            controller.register_state_change_callback(normal_callback)

            # Force a state change
            controller._current_state = PowerState.NORMAL
            mock_battery_monitor.is_battery_critical.return_value = True
            controller.update_power_state()

            # Normal callback should still have been called despite error in first
            assert normal_called

    def test_unregister_nonexistent_callback(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test unregistering a callback that doesn't exist."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        # Create a callback but don't register it
        def dummy_callback(old: PowerState, new: PowerState) -> None:
            pass

        fake_callback = PowerStateCallback(dummy_callback)

        # Should not raise error
        controller.unregister_state_change_callback(fake_callback)

    def test_should_update_weather_no_last_update(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test weather update decision in critical state with no previous update."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CRITICAL
        controller._last_weather_update = None

        # Should allow update when no previous update exists
        assert controller.should_update_weather() is True

    def test_record_weather_update(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test recording weather update timestamp."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        assert controller._last_weather_update is None
        controller.record_weather_update()
        assert controller._last_weather_update is not None

    def test_calculate_sleep_time_conserving_boundary(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation in conserving state at battery boundaries."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CONSERVING

        # Test with 20% battery - below the 25% threshold
        mock_battery_monitor.get_battery_status.return_value = BatteryStatus(
            level=20,
            voltage=3.6,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=datetime.now(),
        )

        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # With level=20 and MAX_BATTERY_PERCENTAGE_SLEEP=0.25 (25%):
            # normalized_level = 20 / 25 = 0.8
            # factor = 3.0 + (6.0 - 3.0) * (1 - 0.8) = 3.0 + 3.0 * 0.2 = 3.6
            # sleep_minutes = 30 * 3.6 = 108 (but due to floating point, int(107.999...) = 107)
            assert sleep_time == 107

    def test_calculate_sleep_time_conserving_above_threshold(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation in conserving state above 25% battery."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CONSERVING

        # Test with 30% battery - above the 25% threshold
        mock_battery_monitor.get_battery_status.return_value = BatteryStatus(
            level=30,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=datetime.now(),
        )

        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # Battery level >= 25%, so factor = CONSERVING_MIN_FACTOR = 3.0
            # sleep_minutes = 30 * 3.0 = 90
            assert sleep_time == 90

    def test_calculate_sleep_time_conserving_at_zero(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation in conserving state at 0% battery."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CONSERVING

        # Test with 0% battery
        mock_battery_monitor.get_battery_status.return_value = BatteryStatus(
            level=0,
            voltage=3.2,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            timestamp=datetime.now(),
        )

        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # With level=0:
            # normalized_level = 0 / 25 = 0
            # factor = 3.0 + (6.0 - 3.0) * (1 - 0) = 3.0 + 3.0 * 1 = 6.0
            # sleep_minutes = 30 * 6.0 = 180
            assert sleep_time == 180

    def test_calculate_sleep_time_charging_state(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation specifically in charging state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CHARGING

        mock_battery_monitor.get_battery_status.return_value = BatteryStatus(
            level=50,
            voltage=4.1,
            current=500.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
            timestamp=datetime.now(),
        )

        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # Formula: max(base_sleep * BATTERY_CHARGING_FACTOR, BATTERY_CHARGING_MIN)
            # BATTERY_CHARGING_FACTOR = 0.8, BATTERY_CHARGING_MIN = 30
            # base_sleep = 30, so 30 * 0.8 = 24
            # Since 24 < 30 (BATTERY_CHARGING_MIN), result should be 30
            assert sleep_time == 30

    def test_calculate_sleep_time_abnormal_discharge(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test sleep time calculation with abnormal discharge rate."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.NORMAL

        # Set abnormal discharge rate
        mock_battery_monitor.is_discharge_rate_abnormal.return_value = True

        with patch.object(controller, "_update_power_state"):
            sleep_time = controller.calculate_sleep_time()
            # In NORMAL state, base_sleep = 30
            # With abnormal discharge, multiply by ABNORMAL_SLEEP_FACTOR (1.5)
            # 30 * 1.5 = 45
            assert sleep_time == 45

    def test_time_until_quiet_change_variants(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test various quiet hours transition scenarios."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        # Test 1: In quiet hours that span midnight (after midnight)
        mock_config.power.quiet_hours_start = "22:00"
        mock_config.power.quiet_hours_end = "07:00"

        with patch("rpi_weather_display.utils.power_state_controller.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 5, 25, 2, 0, 0)  # 2 AM
            mock_datetime.strptime = datetime.strptime
            mock_datetime.combine = datetime.combine

            minutes = controller._time_until_quiet_change()
            # Should be time until 7 AM (5 hours = 300 minutes)
            assert 299 <= minutes <= 301

    def test_time_until_quiet_change_before_start(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test time calculation before quiet hours start (normal hours)."""
        mock_config.power.quiet_hours_start = "09:00"
        mock_config.power.quiet_hours_end = "17:00"

        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        with patch("rpi_weather_display.utils.power_state_controller.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 5, 25, 8, 0, 0)  # 8 AM
            mock_datetime.strptime = datetime.strptime
            mock_datetime.combine = datetime.combine

            minutes = controller._time_until_quiet_change()
            # Should be 1 hour until quiet start
            assert 59 <= minutes <= 61

    def test_time_until_quiet_change_after_end(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test time calculation after quiet hours end."""
        mock_config.power.quiet_hours_start = "09:00"
        mock_config.power.quiet_hours_end = "17:00"

        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        with patch("rpi_weather_display.utils.power_state_controller.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 5, 25, 18, 0, 0)  # 6 PM
            mock_datetime.strptime = datetime.strptime
            mock_datetime.combine = datetime.combine

            minutes = controller._time_until_quiet_change()
            # Should be time until tomorrow's 9 AM (15 hours = 900 minutes)
            assert 899 <= minutes <= 901

    def test_can_perform_operation_development_mode(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test operation permission in development mode."""
        mock_config.development_mode = True
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        # Everything should be allowed in dev mode
        assert controller.can_perform_operation("any_operation") is True
        assert controller.can_perform_operation("expensive_op", power_cost=10.0) is True

    def test_can_perform_operation_conserving_high_cost(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test high-cost operation in conserving state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CONSERVING

        with patch.object(controller, "_update_power_state"):
            # High cost operation should be blocked
            assert controller.can_perform_operation("expensive_op", power_cost=2.0) is False
            # Normal cost should be allowed
            assert controller.can_perform_operation("normal_op", power_cost=1.0) is True

    def test_enter_low_power_mode_from_normal(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test entering low power mode from normal state."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.NORMAL

        # Register callback to verify state change
        state_changed = False
        old_state_received = None
        new_state_received = None

        def callback(old: PowerState, new: PowerState) -> None:
            nonlocal state_changed, old_state_received, new_state_received
            state_changed = True
            old_state_received = old
            new_state_received = new

        controller.register_state_change_callback(callback)

        controller.enter_low_power_mode()

        assert controller._current_state == PowerState.CONSERVING
        assert state_changed
        assert old_state_received == PowerState.NORMAL
        assert new_state_received == PowerState.CONSERVING

    def test_enter_low_power_mode_already_conserving(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test entering low power mode when already conserving."""
        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()
        controller._current_state = PowerState.CONSERVING

        # No state change should occur
        state_changed = False

        def callback(old: PowerState, new: PowerState) -> None:
            nonlocal state_changed
            state_changed = True

        controller.register_state_change_callback(callback)

        controller.enter_low_power_mode()

        assert controller._current_state == PowerState.CONSERVING
        assert not state_changed

    def test_time_until_quiet_change_overnight_in_quiet(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test time calculation during overnight quiet hours (after midnight)."""
        # Set overnight quiet hours
        mock_config.power.quiet_hours_start = "22:00"
        mock_config.power.quiet_hours_end = "07:00"

        controller = PowerStateController(mock_config, mock_battery_monitor)
        controller.initialize()

        with patch("rpi_weather_display.utils.power_state_controller.datetime") as mock_datetime:
            # Currently 11 PM (23:00) - in quiet hours
            mock_datetime.now.return_value = datetime(2024, 5, 25, 23, 0, 0)
            mock_datetime.strptime = datetime.strptime
            mock_datetime.combine = datetime.combine

            minutes = controller._time_until_quiet_change()
            # Should be time until tomorrow's 7 AM (8 hours = 480 minutes)
            assert 479 <= minutes <= 481

    def test_all_testing_helper_methods(
        self, mock_config: AppConfig, mock_battery_monitor: MagicMock
    ) -> None:
        """Test all testing helper methods."""
        # Mock datetime to be during normal hours (not quiet hours)
        with patch("rpi_weather_display.utils.power_state_controller.is_quiet_hours", return_value=False):
            controller = PowerStateController(mock_config, mock_battery_monitor)
            controller.initialize()
            helper = PowerStateControllerTestHelper()

            # Test state helpers
            assert helper.get_internal_state(controller) == PowerState.NORMAL
            helper.set_internal_state(controller, PowerState.CRITICAL)
            assert helper.get_internal_state(controller) == PowerState.CRITICAL

            # Test refresh time helpers
            assert helper.get_last_refresh(controller) is None
            test_time = datetime.now()
            helper.set_last_refresh(controller, test_time)
            assert helper.get_last_refresh(controller) == test_time

            # Test update time helpers
            assert helper.get_last_update(controller) is None
            test_time2 = datetime.now()
            helper.set_last_update(controller, test_time2)
            assert helper.get_last_update(controller) == test_time2
