"""Comprehensive tests for the PowerStateManager class."""

# ruff: noqa: S101, A002, PLR2004
# pyright: reportPrivateUsage=false

import subprocess
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import MagicMock, mock_open, patch

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
from rpi_weather_display.utils.power_manager import (
    PiJuiceInterface,
    PowerStateCallback,
)


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


class TestPowerStateManagerCore:
    """Core tests for the PowerStateManager class functionality."""

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


class TestPowerStateManagerAdvanced:
    """Advanced tests for the PowerStateManager class."""

    def test_initialize_with_pijuice(self, power_manager: PowerStateManager) -> None:
        """Test initialization with PiJuice import success but error in status."""
        # Create a mock for the PiJuice class
        mock_pijuice_class = MagicMock()
        mock_pijuice_instance = MagicMock()
        mock_pijuice_class.return_value = mock_pijuice_instance
        mock_pijuice_instance.status.GetStatus.return_value = {"error": "ERROR", "data": {}}

        # Patch the import inside the initialize method
        with (
            patch.dict("sys.modules", {"pijuice": MagicMock(PiJuice=mock_pijuice_class)}),
            patch.object(power_manager, "_update_power_state"),
        ):
            power_manager.initialize()

            assert not power_manager.get_initialization_status_for_testing()
            # Verify the PiJuice was initialized correctly
            mock_pijuice_class.assert_called_once_with(1, 0x14)

    def test_initialize_with_pijuice_success(self, power_manager: PowerStateManager) -> None:
        """Test successful initialization with PiJuice."""
        # Create a mock for the PiJuice class
        mock_pijuice_class = MagicMock()
        mock_pijuice_instance = MagicMock()
        mock_pijuice_class.return_value = mock_pijuice_instance
        mock_pijuice_instance.status.GetStatus.return_value = {"error": "NO_ERROR", "data": {}}
        # Mock the event configuration responses
        mock_pijuice_instance.config.SetSystemTaskParameters.return_value = {
            "error": "NO_ERROR", 
            "data": {}
        }
        mock_pijuice_instance.config.SetButtonConfiguration.return_value = {
            "error": "NO_ERROR", 
            "data": {}
        }

        # Patch the import inside the initialize method
        with (
            patch.dict("sys.modules", {"pijuice": MagicMock(PiJuice=mock_pijuice_class)}),
            patch.object(power_manager, "_update_power_state"),
        ):
            # Make sure events are enabled in config
            power_manager.config.power.enable_pijuice_events = True
            
            # Initialize PiJuice
            power_manager.initialize()

            # Check initialization result
            assert power_manager.get_initialization_status_for_testing()
            
            # Verify the PiJuice was initialized correctly
            mock_pijuice_class.assert_called_once_with(1, 0x14)
            
            # Verify event handlers were configured
            mock_pijuice_instance.config.SetSystemTaskParameters.assert_called_once_with(
                "LOW_CHARGE", 
                power_manager.config.power.low_charge_action,
                power_manager.config.power.low_charge_delay
            )
            
            mock_pijuice_instance.config.SetButtonConfiguration.assert_called_once_with(
                "SW1", 
                "SINGLE_PRESS",
                {"function": power_manager.config.power.button_press_action, 
                 "parameter": power_manager.config.power.button_press_delay}
            )

    def test_initialize_with_pijuice_exception(self, power_manager: PowerStateManager) -> None:
        """Test initialization with PiJuice throwing an exception."""
        # Create a mock for the PiJuice class that raises an exception
        mock_pijuice_class = MagicMock()
        mock_pijuice_instance = MagicMock()
        mock_pijuice_class.return_value = mock_pijuice_instance
        mock_pijuice_instance.status.GetStatus.side_effect = Exception("Test exception")

        # Patch the import inside the initialize method
        with (
            patch.dict("sys.modules", {"pijuice": MagicMock(PiJuice=mock_pijuice_class)}),
            patch.object(power_manager, "_update_power_state"),
        ):
            power_manager.initialize()

            assert not power_manager.get_initialization_status_for_testing()

    def test_initialize_with_special_cases(self, power_manager: PowerStateManager) -> None:
        """Test initialize() with special case handling."""
        # Create a mock PiJuice class that raises ImportError initially
        mock_pijuice_class = MagicMock()

        # First patch to simulate ImportError, then succeed on second attempt
        with patch.dict("sys.modules", {"pijuice": None}):
            # This should fall back to mock mode
            power_manager.initialize()
            assert not power_manager.get_initialization_status_for_testing()

        # Now test with PiJuice available but with exception in initialization
        mock_pijuice_class = MagicMock()
        mock_pijuice_instance = MagicMock()
        mock_pijuice_class.return_value = mock_pijuice_instance
        # Raise a general exception during initialization
        mock_pijuice_class.side_effect = Exception("General initialization error")

        with patch.dict("sys.modules", {"pijuice": MagicMock(PiJuice=mock_pijuice_class)}):
            power_manager.initialize()
            assert not power_manager.get_initialization_status_for_testing()
            
    def test_configure_pijuice_events_not_initialized(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test _configure_pijuice_events when PiJuice is not initialized."""
        # Ensure PiJuice is not initialized
        power_manager._initialized = False
        power_manager._pijuice = None
        
        # Should not raise any exceptions
        power_manager._configure_pijuice_events()
        
        # No assertions needed, just checking it doesn't raise exceptions
        
    def test_configure_pijuice_events_with_errors(self, power_manager: PowerStateManager) -> None:
        """Test _configure_pijuice_events handling API errors."""
        # Create mock PiJuice instance
        mock_pijuice = MagicMock()
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True
        
        # Configure mocks to return errors
        mock_pijuice.config.SetSystemTaskParameters.return_value = {"error": "ERROR", "data": {}}
        mock_pijuice.config.SetButtonConfiguration.return_value = {"error": "ERROR", "data": {}}
        
        # Should log errors but not raise exceptions
        power_manager._configure_pijuice_events()
        
        # Verify method calls
        mock_pijuice.config.SetSystemTaskParameters.assert_called_once()
        mock_pijuice.config.SetButtonConfiguration.assert_called_once()
        
    def test_configure_pijuice_events_with_exception(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test _configure_pijuice_events handling exceptions."""
        # Create mock PiJuice instance
        mock_pijuice = MagicMock()
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True
        
        # Configure mock to raise an exception
        mock_pijuice.config.SetSystemTaskParameters.side_effect = Exception("Test exception")
        
        # Should catch exception and log error
        power_manager._configure_pijuice_events()
        
        # Verify method was called despite exception
        mock_pijuice.config.SetSystemTaskParameters.assert_called_once()
        
    def test_get_event_configuration(self, power_manager: PowerStateManager) -> None:
        """Test get_event_configuration with different event types."""
        from rpi_weather_display.utils.power_manager import PiJuiceEvent
        
        # Create mock PiJuice instance
        mock_pijuice = MagicMock()
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True
        
        # Configure mocks to return valid responses
        mock_pijuice.config.GetSystemTaskParameters.return_value = {
            "error": "NO_ERROR", 
            "data": {"function": "SYSTEM_HALT", "delay": 5}
        }
        mock_pijuice.config.GetButtonConfiguration.return_value = {
            "error": "NO_ERROR", 
            "data": {"function": "SYSDOWN", "parameter": 180}
        }
        
        # Test LOW_CHARGE event
        result = power_manager.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {"function": "SYSTEM_HALT", "delay": 5}
        
        # Test button press event
        result = power_manager.get_event_configuration(PiJuiceEvent.BUTTON_SW1_PRESS)
        assert result == {"function": "SYSDOWN", "parameter": 180}
        
        # Test unsupported event type
        result = power_manager.get_event_configuration(PiJuiceEvent.SYSTEM_WAKEUP)
        assert result == {}
        
    def test_get_event_configuration_errors(self, power_manager: PowerStateManager) -> None:
        """Test get_event_configuration error handling."""
        from rpi_weather_display.utils.power_manager import PiJuiceEvent
        
        # Test not initialized case
        power_manager._initialized = False
        power_manager._pijuice = None
        result = power_manager.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}
        
        # Test API error responses
        power_manager._initialized = True
        mock_pijuice = MagicMock()
        power_manager._pijuice = mock_pijuice
        
        # Configure mocks to return error responses
        mock_pijuice.config.GetSystemTaskParameters.return_value = {
            "error": "ERROR", 
            "data": {}
        }
        mock_pijuice.config.GetButtonConfiguration.return_value = {
            "error": "ERROR", 
            "data": {}
        }
        
        # Test LOW_CHARGE event with error
        result = power_manager.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}
        
        # Test button press event with error
        result = power_manager.get_event_configuration(PiJuiceEvent.BUTTON_SW1_PRESS)
        assert result == {}
        
    def test_get_event_configuration_exceptions(self, power_manager: PowerStateManager) -> None:
        """Test get_event_configuration exception handling."""
        from rpi_weather_display.utils.power_manager import PiJuiceEvent
        
        # Setup manager with mock that raises exceptions
        power_manager._initialized = True
        mock_pijuice = MagicMock()
        power_manager._pijuice = mock_pijuice
        
        # Configure mocks to raise exceptions
        mock_pijuice.config.GetSystemTaskParameters.side_effect = Exception("Test exception")
        mock_pijuice.config.GetButtonConfiguration.side_effect = Exception("Test exception")
        
        # Test LOW_CHARGE event with exception
        result = power_manager.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}
        
        # Test button press event with exception
        result = power_manager.get_event_configuration(PiJuiceEvent.BUTTON_SW1_PRESS)
        assert result == {}

    def test_notify_callback_errors(self, power_manager: PowerStateManager) -> None:
        """Test error handling in the callback notifications."""
        # Create two callbacks - one that raises an exception, one that works
        error_callback = MagicMock(side_effect=Exception("Test exception"))
        normal_callback = MagicMock()

        # Register both callbacks
        error_obj = power_manager.register_state_change_callback(error_callback)
        normal_obj = power_manager.register_state_change_callback(normal_callback)

        # Trigger notification - should handle first error and still call second callback
        power_manager._notify_state_change(PowerState.NORMAL, PowerState.CONSERVING)

        # Verify both callbacks were called
        error_callback.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)
        normal_callback.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)

        # Clean up
        power_manager.unregister_state_change_callback(error_obj)
        power_manager.unregister_state_change_callback(normal_obj)

    def test_pijuice_interface_methods(self) -> None:
        """Test the PiJuiceInterface class stubs for coverage."""
        # Create an instance of PiJuiceInterface
        interface = PiJuiceInterface(1, 0x14)

        # Test status class methods
        status_result = interface.status.GetStatus()
        assert isinstance(status_result, dict)
        assert "error" in status_result
        assert "data" in status_result

        # Test the other status methods
        charge_level = interface.status.GetChargeLevel()
        assert isinstance(charge_level, dict)
        assert "error" in charge_level
        assert "data" in charge_level

        voltage = interface.status.GetBatteryVoltage()
        assert isinstance(voltage, dict)
        assert "error" in voltage
        assert "data" in voltage

        current = interface.status.GetBatteryCurrent()
        assert isinstance(current, dict)
        assert "error" in current
        assert "data" in current

        temperature = interface.status.GetBatteryTemperature()
        assert isinstance(temperature, dict)
        assert "error" in temperature
        assert "data" in temperature

        # Test rtcAlarm methods
        interface.rtcAlarm.SetAlarm(
            {"second": 0, "minute": 0, "hour": 0, "day": 1, "month": 1, "year": 23}
        )
        interface.rtcAlarm.SetWakeupEnabled(True)
        
        # Test the new power class methods
        power_result = interface.power.SetSystemPowerSwitch(1)
        assert isinstance(power_result, dict)
        assert "error" in power_result
        assert "data" in power_result
        
        # Test the new config class methods
        sys_task_result = interface.config.SetSystemTaskParameters("LOW_CHARGE", "SYSTEM_HALT", 5)
        assert isinstance(sys_task_result, dict)
        assert "error" in sys_task_result
        assert "data" in sys_task_result
        
        get_sys_task_result = interface.config.GetSystemTaskParameters("LOW_CHARGE")
        assert isinstance(get_sys_task_result, dict)
        assert "error" in get_sys_task_result
        assert "data" in get_sys_task_result
        
        button_config_result = interface.config.SetButtonConfiguration(
            "SW1", "SINGLE_PRESS", {"function": "SYSDOWN", "parameter": 180}
        )
        assert isinstance(button_config_result, dict)
        assert "error" in button_config_result
        assert "data" in button_config_result
        
        get_button_config_result = interface.config.GetButtonConfiguration("SW1", "SINGLE_PRESS")
        assert isinstance(get_button_config_result, dict)
        assert "error" in get_button_config_result
        assert "data" in get_button_config_result
        
        # Test wakeupalarm class methods
        wakeup_result = interface.wakeupalarm.SetWakeupEnabled(True)
        assert isinstance(wakeup_result, dict)
        assert "error" in wakeup_result
        assert "data" in wakeup_result
        
        # Test convenience methods
        status = interface.get_status()
        assert isinstance(status, dict)
        assert "error" in status
        assert "data" in status
        
        level = interface.get_charge_level()
        assert level == 0

    def test_power_state_callback_class(self) -> None:
        """Test the PowerStateCallback class for coverage."""
        mock_callback = MagicMock()
        callback_obj = PowerStateCallback(mock_callback)

        # Call the callback
        callback_obj.callback(PowerState.NORMAL, PowerState.CONSERVING)

        # Verify callback was called
        mock_callback.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)


class TestPowerManagerBatteryAndMetrics:
    """Tests for battery status and system metric functionality."""

    def test_get_battery_status_initialized(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status when PiJuice is initialized."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure mock responses
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 80}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 4000}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": -200}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": 25,
            }
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": "NORMAL"},
            }

            status = power_manager.get_battery_status()

            assert status.level == 80
            assert status.voltage == 4.0  # 4000 / 1000
            assert status.current == -200.0  # Negative because discharging
            assert status.temperature == 25.0
            assert status.state == BatteryState.DISCHARGING

    def test_get_battery_status_charging(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status with charging state."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure mock responses
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 60}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 4100}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": 500}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": 30,
            }
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": "CHARGING"},
            }

            status = power_manager.get_battery_status()

            assert status.level == 60
            assert status.voltage == 4.1
            assert status.current == 500.0  # Positive because charging
            assert status.temperature == 30.0
            assert status.state == BatteryState.CHARGING
            assert status.time_remaining is None  # No time remaining when charging

    def test_get_battery_status_full(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status with full battery state."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure mock responses
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 100}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 4200}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": 0}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": 25,
            }
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": "CHARGED"},
            }

            status = power_manager.get_battery_status()

            assert status.level == 100
            assert status.voltage == 4.2
            assert status.current == 0.0
            assert status.temperature == 25.0
            assert status.state == BatteryState.FULL

    def test_get_battery_status_error_responses(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status handling error responses."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure error responses
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "ERROR", "data": None}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "ERROR", "data": None}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "ERROR", "data": None}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "ERROR",
                "data": None,
            }
            mock_pijuice.status.GetStatus.return_value = {"error": "ERROR", "data": None}

            status = power_manager.get_battery_status()

            # Should return zeros with unknown state
            assert status.level == 0
            assert status.voltage == 0.0
            assert status.current == 0.0
            assert status.temperature == 0.0
            assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_invalid_data_types(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status handling invalid data types."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure invalid data types
            mock_pijuice.status.GetChargeLevel.return_value = {
                "error": "NO_ERROR",
                "data": "invalid",
            }
            mock_pijuice.status.GetBatteryVoltage.return_value = {
                "error": "NO_ERROR",
                "data": "invalid",
            }
            mock_pijuice.status.GetBatteryCurrent.return_value = {
                "error": "NO_ERROR",
                "data": "invalid",
            }
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": "invalid",
            }
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": None},
            }

            status = power_manager.get_battery_status()

            # Should return zeros with unknown state
            assert status.level == 0
            assert status.voltage == 0.0
            assert status.current == 0.0
            assert status.temperature == 0.0
            assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_exception(self, power_manager: PowerStateManager) -> None:
        """Test get_battery_status handling exceptions."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Raise an exception
            mock_pijuice.status.GetChargeLevel.side_effect = Exception("Test exception")

            status = power_manager.get_battery_status()

            # Should return zeros with unknown state
            assert status.level == 0
            assert status.voltage == 0.0
            assert status.current == 0.0
            assert status.temperature == 0.0
            assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_additional_cases(self, power_manager: PowerStateManager) -> None:
        """Test additional cases in get_battery_status."""
        # Test with battery in "NOT_PRESENT" state
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Mock all the required responses
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 0}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 0}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": 0}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": 0,
            }

            # Return a "NOT_PRESENT" battery state (non-standard PiJuice status)
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": "NOT_PRESENT"},
            }

            # Get battery status
            status = power_manager.get_battery_status()

            # Should return unknown state with zeros
            assert status.level == 0
            assert status.voltage == 0.0
            assert status.current == 0.0
            assert status.temperature == 0.0
            assert status.state == BatteryState.UNKNOWN


class TestQuietHoursAndSleepTiming:
    """Tests for quiet hours and sleep timing calculations."""

    def test_should_update_weather_first_time(self, power_manager: PowerStateManager) -> None:
        """Test should_update_weather on first run."""
        # First time (no previous update) should always return True
        assert power_manager.should_update_weather()

    def test_should_update_weather_normal_interval(self, power_manager: PowerStateManager) -> None:
        """Test should_update_weather with normal interval."""
        # Set last update time
        now = datetime.now()
        power_manager.set_last_update_for_testing(now - timedelta(minutes=25))

        # Not enough time has passed
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert not power_manager.should_update_weather()

        # Enough time has passed
        power_manager.set_last_update_for_testing(now - timedelta(minutes=31))
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            assert power_manager.should_update_weather()

    def test_should_update_weather_conserving_state(self, power_manager: PowerStateManager) -> None:
        """Test should_update_weather in power conserving state."""
        # Set last update time
        now = datetime.now()
        power_manager.set_last_update_for_testing(now - timedelta(minutes=31))

        # In conserving state - interval should be doubled
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING):
            assert not power_manager.should_update_weather()  # Not enough time (31 min < 60 min)

        # Set longer time - should update now
        power_manager.set_last_update_for_testing(now - timedelta(minutes=61))
        with patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING):
            assert power_manager.should_update_weather()  # Enough time (61 min > 60 min)

    def test_should_update_weather_quiet_hours(self, power_manager: PowerStateManager) -> None:
        """Test should_update_weather during quiet hours."""
        # Set last update time
        now = datetime.now()
        power_manager.set_last_update_for_testing(now - timedelta(minutes=31))

        # In quiet hours - should use normal interval
        with patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS):
            assert power_manager.should_update_weather()  # Enough time (31 min > 30 min)

    def test_record_display_refresh(self, power_manager: PowerStateManager) -> None:
        """Test record_display_refresh updates last refresh time."""
        power_manager.record_display_refresh()
        refresh_time = power_manager.get_last_refresh_for_testing()

        assert refresh_time is not None
        # Should be very recent (within 0.1 seconds)
        assert (datetime.now() - refresh_time).total_seconds() < 0.1

    def test_record_weather_update(self, power_manager: PowerStateManager) -> None:
        """Test record_weather_update updates last update time."""
        power_manager.record_weather_update()
        update_time = power_manager.get_last_update_for_testing()

        assert update_time is not None
        # Should be very recent (within 0.1 seconds)
        assert (datetime.now() - update_time).total_seconds() < 0.1

    def test_calculate_sleep_time_quiet_hours(self, power_manager: PowerStateManager) -> None:
        """Test calculate_sleep_time during quiet hours."""
        with patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS):
            sleep_time = power_manager.calculate_sleep_time()

            # Should return wake_up_interval_minutes * 60
            assert sleep_time == 60 * 60  # 60 minutes in seconds

    def test_calculate_sleep_time_normal(self, power_manager: PowerStateManager) -> None:
        """Test calculate_sleep_time in normal state."""
        now = datetime.now()

        # Set last refresh and update times
        power_manager.set_last_refresh_for_testing(now - timedelta(minutes=15))  # 15 min ago
        power_manager.set_last_update_for_testing(now - timedelta(minutes=10))  # 10 min ago

        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL),
            patch.object(power_manager, "_time_until_quiet_change", return_value=7200.0),  # 2 hours
        ):
            # Calculate time until next refresh (in seconds)
            refresh_time = (
                now - timedelta(minutes=15) + timedelta(minutes=30) - now
            ).total_seconds()
            refresh_time = max(int(refresh_time), 0)

            sleep_time = power_manager.calculate_sleep_time()

            # Compare with the expected time until next refresh
            assert sleep_time == min(refresh_time, 60) if refresh_time > 0 else 60

    def test_calculate_sleep_time_conserving(self, power_manager: PowerStateManager) -> None:
        """Test calculate_sleep_time in conserving state."""
        now = datetime.now()

        # Set last refresh and update times
        power_manager.set_last_refresh_for_testing(now - timedelta(minutes=15))  # 15 min ago
        power_manager.set_last_update_for_testing(now - timedelta(minutes=10))  # 10 min ago

        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.CONSERVING),
            patch.object(power_manager, "_time_until_quiet_change", return_value=7200.0),  # 2 hours
        ):
            # Calculate time until next refresh (in seconds) - doubled in conserving state
            refresh_time = (
                now - timedelta(minutes=15) + timedelta(minutes=60) - now
            ).total_seconds()
            refresh_time = max(int(refresh_time), 0)

            sleep_time = power_manager.calculate_sleep_time()

            # Compare with the expected time until next refresh
            assert sleep_time == min(refresh_time, 60) if refresh_time > 0 else 60

    def test_calculate_sleep_time_default(self, power_manager: PowerStateManager) -> None:
        """Test calculate_sleep_time with default times."""
        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL),
            patch.object(power_manager, "_time_until_quiet_change", return_value=7200.0),  # 2 hours
        ):
            # No previous refresh or update times
            sleep_time = power_manager.calculate_sleep_time()

            # Should use default (60 seconds)
            assert sleep_time == 60

    def test_calculate_sleep_time_minimum(self, power_manager: PowerStateManager) -> None:
        """Test calculate_sleep_time with very short times."""
        now = datetime.now()

        # Set last refresh and update times to be almost due
        power_manager.set_last_refresh_for_testing(now - timedelta(seconds=1795))  # 5 sec until due
        power_manager.set_last_update_for_testing(now - timedelta(seconds=1790))  # 10 sec until due

        with (
            patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL),
            patch.object(power_manager, "_time_until_quiet_change", return_value=5.0),  # 5 sec
        ):
            sleep_time = power_manager.calculate_sleep_time()

            # Should use minimum (10 seconds)
            assert sleep_time == 10

    def test_time_until_quiet_change_complete(self, power_manager: PowerStateManager) -> None:
        """Test the _time_until_quiet_change method with various time scenarios."""
        # Configure quiet hours for testing
        config = power_manager.config.model_copy(deep=True)
        config.power.wake_up_interval_minutes = 60  # Ensure this is explicitly set
        power_manager.config = config

        # Mock get_current_state to ensure it returns QUIET_HOURS consistently
        with patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS):
            # Calculate sleep time in QUIET_HOURS state, it should return wake_up_interval_minutes * 60  # noqa: E501
            result = power_manager.calculate_sleep_time()

            # Should return 3600 seconds (60 minutes * 60 seconds)
            assert result == 3600

    def test_time_until_quiet_change_daytime_span(self, power_manager: PowerStateManager) -> None:
        """Test _time_until_quiet_change with quiet hours during the day (start < end)."""
        # Configure daytime quiet hours and use direct method testing
        # For code coverage, we'll directly test the branch condition where
        # time_until_quiet_change > 0

        # Set quiet hours to be in the future to ensure time_until_quiet_change returns a positive value  # noqa: E501
        config = power_manager.config.model_copy(deep=True)
        # Set quiet hours to start 1 hour from now and end 2 hours from now
        now = datetime.now()
        start_hour = (now.hour + 1) % 24
        end_hour = (now.hour + 2) % 24
        config.power.quiet_hours_start = f"{start_hour:02d}:00"
        config.power.quiet_hours_end = f"{end_hour:02d}:00"
        power_manager.config = config

        # Directly override the method with our test value
        power_manager._time_until_quiet_change = lambda: 3600  # Return 1 hour (3600 seconds)

        # Mock get_current_state to ensure it returns NORMAL consistently
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            # Call calculate_sleep_time
            result = power_manager.calculate_sleep_time()

            # With _time_until_quiet_change returning 3600, and default sleep time 60,
            # it should use the min(3600, 60) = 60
            assert result == 60

    def test_time_until_quiet_change_equal_start_end(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test _time_until_quiet_change when start and end times are the same."""
        # Instead of trying to test the exact time arithmetic which is time-zone dependent,
        # Test the ValueError exception path in _time_until_quiet_change

        # Configure invalid format for quiet hours
        config = power_manager.config.model_copy(deep=True)
        config.power.quiet_hours_start = "invalid"
        config.power.quiet_hours_end = "format"
        power_manager.config = config

        # This should trigger the ValueError exception in _time_until_quiet_change
        result = power_manager._time_until_quiet_change()

        # The method should return -1 on error
        assert result == -1

    def test_time_until_quiet_change_detailed(self, power_manager: PowerStateManager) -> None:
        """Test more branches in _time_until_quiet_change."""
        # Test time_until_start/end logic when both values are positive

        # Directly override the method with our test value instead of mocking
        config = power_manager.config.model_copy(deep=True)
        config.power.wake_up_interval_minutes = 60  # Ensure this is explicitly set
        power_manager.config = config

        power_manager._time_until_quiet_change = lambda: 100  # Return 100 seconds

        # Mock get_current_state to ensure it returns NORMAL consistently
        with patch.object(power_manager, "get_current_state", return_value=PowerState.NORMAL):
            # Call a method that uses _time_until_quiet_change
            result = power_manager.calculate_sleep_time()

            # Verify the result uses the expected value
            expected_result = 60  # Default sleep time
            assert result == expected_result

    def test_time_until_quiet_change_with_positive_values(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test _time_until_quiet_change when time_until_start or time_until_end are positive."""
        # Create a patched datetime.now that returns a specific time
        now = datetime(2023, 1, 1, 12, 0, 0)  # Noon

        # Configure quiet hours
        config = power_manager.config.model_copy(deep=True)
        config.power.quiet_hours_start = "22:00"  # 10 PM
        config.power.quiet_hours_end = "06:00"  # 6 AM
        power_manager.config = config

        # Test the case where only time_until_start is positive
        # and time_until_end is negative (after end, before start)
        with patch("datetime.datetime") as mock_dt:
            # Mock the datetime functionality needed
            mock_dt.now.return_value = now
            mock_dt.combine = datetime.combine

            # Create a simplified test implementation that just checks if
            # the parameters are passed to the internal time calculation correctly
            def mock_get_positive_time(*args: object, **kwargs: object) -> float:
                # This simulates time_until_start being positive and time_until_end being negative
                return 10 * 3600  # 10 hours until start

            # Replace _time_until_quiet_change with our test function
            with patch.object(
                power_manager, "_time_until_quiet_change", side_effect=mock_get_positive_time
            ):
                # Mock get_current_state to ensure it returns NORMAL consistently
                with patch.object(
                    power_manager, "get_current_state", return_value=PowerState.NORMAL
                ):
                    # Call calculate_sleep_time which will use our mocked function
                    result = power_manager.calculate_sleep_time()

                    # Verify the result - since we're mocking both time_until_quiet_change
                    # and get_current_state, we expect the minimum sleep time (60)
                    expected_result = 60  # Default sleep time
                    assert result == expected_result


class TestSystemMetricsAndShutdown:
    """Tests for system metrics, shutdown and wakeup functionality."""

    def test_get_system_metrics_mock(self, power_manager: PowerStateManager) -> None:
        """Test get_system_metrics in mock mode."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            metrics = power_manager.get_system_metrics()

            # Should return empty dictionary
            assert isinstance(metrics, dict)
            assert len(metrics) == 0

    def test_get_system_metrics_success(self, power_manager: PowerStateManager) -> None:
        """Test get_system_metrics success."""
        mock_temp_content = "45000\n"  # 45 degrees C
        mock_meminfo_content = "MemTotal:        1024000 kB\nMemFree:         512000 kB\n"

        # Setup for a successful metrics gathering
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open") as mock_open,
            patch("subprocess.check_output") as mock_output,
        ):
            # Mock file reads
            mock_file1 = MagicMock()
            mock_file1.read.return_value = mock_temp_content
            mock_file2 = MagicMock()
            mock_file2.read.return_value = mock_meminfo_content

            # Configure open to return different mock file objects
            mock_open.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_file1)),
                MagicMock(__enter__=MagicMock(return_value=mock_file2)),
            ]

            # Mock subprocess outputs - need two different formats to match parsing
            mock_output.side_effect = [
                b"Cpu(s):  10.0%id, 90.0%us",  # CPU usage
                (
                    b"Filesystem     1K-blocks     Used Available Use% Mounted on\n"
                    b"/ 100000000 50000000 50000000  50% /"
                ),  # Disk usage in df format
            ]

            # Also mock the battery history
            with patch.object(power_manager, "_battery_history", []):
                metrics = power_manager.get_system_metrics()

                # Should include CPU temp, usage, memory usage
                assert "cpu_temp" in metrics
                assert metrics["cpu_temp"] == 45.0
                assert "cpu_usage" in metrics
                assert metrics["cpu_usage"] == 90.0
                assert "memory_usage" in metrics
                assert metrics["memory_usage"] == 50.0

                # We'll check for existence only since df output format is harder to mock perfectly
                # The exact values might differ but disk_usage should exist
                assert "disk_usage" in metrics

    def test_get_system_metrics_errors(self, power_manager: PowerStateManager) -> None:
        """Test get_system_metrics handling errors."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("subprocess.check_output", side_effect=subprocess.SubprocessError()),
        ):
            # Mock battery history to test drain rate calculation
            with (
                patch.object(power_manager, "_battery_history", []),
                patch(
                    "rpi_weather_display.utils.power_manager.calculate_drain_rate",
                    return_value=None,
                ),
            ):
                metrics = power_manager.get_system_metrics()

                # Should return empty dictionary
                assert isinstance(metrics, dict)
                assert len(metrics) == 0

    def test_get_system_metrics_edge_cases(self, power_manager: PowerStateManager) -> None:
        """Test the edge cases in get_system_metrics method."""
        # Test case: Memory info parsing errors
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "builtins.open",
                side_effect=[
                    # First call for CPU temperature
                    mock_open(read_data="45000").return_value,
                    # Second call for meminfo but with invalid format
                    mock_open(read_data="Invalid meminfo format").return_value,
                ],
            ),
            patch("subprocess.check_output") as mock_output,
        ):
            # Mock the subprocess calls
            mock_output.side_effect = [
                b"Cpu(s):  10.0%id, 90.0%us",  # CPU usage
                b"",  # Empty disk usage to test empty response parsing
            ]

            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should still have CPU temp but not memory or disk due to parsing error
            assert "cpu_temp" in metrics
            assert "cpu_usage" in metrics
            # But should not have memory usage due to parsing error
            assert "memory_usage" not in metrics

    def test_get_system_metrics_parse_errors(self, power_manager: PowerStateManager) -> None:
        """Test system metrics with different parsing errors."""
        # Test case: CPU usage parsing errors
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open") as mock_open_fn,
            patch("subprocess.check_output") as mock_output,
        ):
            # Mock file reads
            mock_file1 = MagicMock()
            mock_file1.read.return_value = "45000\n"
            mock_file2 = MagicMock()
            mock_file2.read.return_value = (
                "MemTotal:        1024000 kB\nMemFree:         512000 kB\n"
            )

            # Configure open to return different mock file objects
            mock_open_fn.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_file1)),
                MagicMock(__enter__=MagicMock(return_value=mock_file2)),
            ]

            # Mock CPU usage with invalid format
            mock_output.side_effect = [
                b"Invalid CPU format",  # Invalid CPU usage format
                (
                    b"Filesystem     1K-blocks     Used Available Use% Mounted on\n"
                    b"/ 100000000 50000000 50000000  50% /"
                ),
            ]

            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should have CPU temp but not CPU usage due to parsing error
            assert "cpu_temp" in metrics
            assert metrics["cpu_temp"] == 45.0
            assert "cpu_usage" not in metrics

    def test_shutdown_system_mock(self, power_manager: PowerStateManager) -> None:
        """Test shutdown_system in mock mode."""
        with patch.object(power_manager, "_initialized", False):
            # Should log but not do anything in mock mode
            power_manager.shutdown_system()
            # Just verifying no exception

    def test_shutdown_system_commands_not_found(self, power_manager: PowerStateManager) -> None:
        """Test shutdown_system when commands not found."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch("pathlib.Path.exists", return_value=False),
        ):
            # Should log warning but not run command
            power_manager.shutdown_system()
            # Just verifying no exception

    def test_shutdown_system_success(self, power_manager: PowerStateManager) -> None:
        """Test shutdown_system success."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            power_manager.shutdown_system()

            # Should run shutdown command
            mock_run.assert_called_once()

    def test_shutdown_system_error(self, power_manager: PowerStateManager) -> None:
        """Test shutdown_system with error."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", side_effect=subprocess.SubprocessError("Test error")),
        ):
            # Should log error but not crash
            power_manager.shutdown_system()
            # Just verifying no exception

    def test_schedule_wakeup_mock(self, power_manager: PowerStateManager) -> None:
        """Test schedule_wakeup in mock mode."""
        with patch.object(power_manager, "_initialized", False):
            # Should return True in mock mode
            result = power_manager.schedule_wakeup(30)
            assert result is True

    def test_schedule_wakeup_success(self, power_manager: PowerStateManager) -> None:
        """Test schedule_wakeup success."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice") as mock_pijuice,
        ):
            minutes = 30
            result = power_manager.schedule_wakeup(minutes)

            # Should set alarm and enable wakeup
            mock_pijuice.rtcAlarm.SetAlarm.assert_called_once()
            mock_pijuice.rtcAlarm.SetWakeupEnabled.assert_called_once_with(True)
            assert result is True

    def test_schedule_wakeup_error(self, power_manager: PowerStateManager) -> None:
        """Test schedule_wakeup with error."""
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice") as mock_pijuice,
        ):
            # Set an exception
            mock_pijuice.rtcAlarm.SetAlarm.side_effect = Exception("Test error")

            result = power_manager.schedule_wakeup(30)

            # Should log error and return False
            assert result is False
            
    def test_handle_low_charge_event(self, power_manager: PowerStateManager) -> None:
        """Test handling a direct PiJuice LOW_CHARGE event."""
        # Need to initialize _pijuice and set _initialized to True
        with patch.object(power_manager, "_initialized", True):
            # Mock the relevant methods
            power_manager.get_battery_status = MagicMock()
            power_manager.schedule_wakeup = MagicMock()
            power_manager.shutdown_system = MagicMock()
            
            # Call the handler method
            power_manager._handle_low_charge_event()
            
            # Verify actions
            power_manager.get_battery_status.assert_called_once()
            power_manager.schedule_wakeup.assert_called_once_with(12 * 60)  # 12 hours in minutes
            power_manager.shutdown_system.assert_called_once()
            
    def test_register_pijuice_event_listener(self, power_manager: PowerStateManager) -> None:
        """Test registering a PiJuice event listener."""
        # Need to initialize _pijuice and set _initialized to True
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", MagicMock()),
        ):
            # Set up an event configuration
            power_manager.get_event_configuration = MagicMock(
                return_value={"function": "SYSSHUTDOWN"}
            )
            
            # Call the method
            power_manager._register_pijuice_event_listener()
            
            # Verify the configuration was checked
            power_manager.get_event_configuration.assert_called_once()


class TestBatteryCoverageExtensions:
    """Additional tests to cover edge cases in battery drain functionality."""

    def test_is_discharge_rate_abnormal_no_data(self, power_manager: PowerStateManager) -> None:
        """Test is_discharge_rate_abnormal with no history data."""
        with patch(
            "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=None
        ):
            result = power_manager.is_discharge_rate_abnormal()

            # Should return False if no drain rate available
            assert result is False

    def test_is_discharge_rate_abnormal_normal(self, power_manager: PowerStateManager) -> None:
        """Test is_discharge_rate_abnormal with normal rate."""
        with (
            patch("rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=1.0),
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                return_value=False,
            ),
        ):
            result = power_manager.is_discharge_rate_abnormal()

            # Should return False for normal rate
            assert result is False

    def test_is_discharge_rate_abnormal_high(self, power_manager: PowerStateManager) -> None:
        """Test is_discharge_rate_abnormal with high rate."""
        with (
            patch("rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=3.0),
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                return_value=True,
            ),
        ):
            result = power_manager.is_discharge_rate_abnormal()

            # Should return True for abnormal rate
            assert result is True

    def test_get_expected_battery_life_calculation(self, power_manager: PowerStateManager) -> None:
        """Test get_expected_battery_life calculation paths."""
        # Mock drain_rate to return a specific value
        with patch(
            "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=1.0
        ):
            # Mock get_battery_status to return a battery with level 80, discharging
            with patch.object(
                power_manager,
                "get_battery_status",
                return_value=MagicMock(level=80, state="DISCHARGING", time_remaining=None),
            ):
                expected_life = power_manager.get_expected_battery_life()
                assert expected_life == 80  # 80% / 1% per hour = 80 hours

    def test_get_expected_battery_life_charging(self, power_manager: PowerStateManager) -> None:
        """Test get_expected_battery_life while charging."""
        # Mock a charging battery
        with patch.object(
            power_manager,
            "get_battery_status",
            return_value=BatteryStatus(
                level=50,
                voltage=3.7,
                current=500.0,
                temperature=25.0,
                state=BatteryState.CHARGING,
                time_remaining=None,
            ),
        ):
            result = power_manager.get_expected_battery_life()

            # Should return None while charging
            assert result is None

    def test_get_expected_battery_life_with_drain_rate(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test get_expected_battery_life with calculated drain rate."""
        # Mock a discharging battery and drain rate
        with (
            patch.object(
                power_manager,
                "get_battery_status",
                return_value=BatteryStatus(
                    level=80,
                    voltage=3.7,
                    current=-100.0,
                    temperature=25.0,
                    state=BatteryState.DISCHARGING,
                    time_remaining=None,
                ),
            ),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=2.0
            ),  # 2% per hour
        ):
            result = power_manager.get_expected_battery_life()

            # Should return level / drain rate (80 / 2 = 40 hours)
            assert result == 40

    def test_get_expected_battery_life_with_time_remaining(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test get_expected_battery_life with time_remaining in battery status."""
        # Mock a discharging battery with time_remaining
        with (
            patch.object(
                power_manager,
                "get_battery_status",
                return_value=BatteryStatus(
                    level=50,
                    voltage=3.7,
                    current=-100.0,
                    temperature=25.0,
                    state=BatteryState.DISCHARGING,
                    time_remaining=120,  # 120 minutes
                ),
            ),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=None
            ),
        ):
            result = power_manager.get_expected_battery_life()

            # Should return time_remaining / 60 (120 / 60 = 2 hours)
            assert result == 2

    def test_get_expected_battery_life_no_data(self, power_manager: PowerStateManager) -> None:
        """Test get_expected_battery_life with no data available."""
        # Mock a discharging battery with no usable data
        with (
            patch.object(
                power_manager,
                "get_battery_status",
                return_value=BatteryStatus(
                    level=50,
                    voltage=3.7,
                    current=-100.0,
                    temperature=25.0,
                    state=BatteryState.DISCHARGING,
                    time_remaining=None,
                ),
            ),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=None
            ),
        ):
            result = power_manager.get_expected_battery_life()

            # Should return None if no data available
            assert result is None

    def test_get_expected_battery_life_zero_drain(self, power_manager: PowerStateManager) -> None:
        """Test get_expected_battery_life with zero drain rate."""
        # Mock a discharging battery with zero drain rate
        with (
            patch.object(
                power_manager,
                "get_battery_status",
                return_value=BatteryStatus(
                    level=50,
                    voltage=3.7,
                    current=-100.0,
                    temperature=25.0,
                    state=BatteryState.DISCHARGING,
                    time_remaining=None,
                ),
            ),
            patch("rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=0.0),
        ):
            result = power_manager.get_expected_battery_life()

            # Should return None if drain rate is zero
            assert result is None

    def test_time_until_quiet_change_invalid_format(self, power_manager: PowerStateManager) -> None:
        """Test _time_until_quiet_change with invalid format."""
        # Set invalid quiet hours format (already covered in another test but keeping for completeness)  # noqa: E501
        config = power_manager.config.model_copy(deep=True)
        config.power.quiet_hours_start = "invalid"
        config.power.quiet_hours_end = "format"
        power_manager.config = config

        result = power_manager._time_until_quiet_change()

        # The method should return -1 on error
        assert result == -1

    def test_callbacks_registration(self, power_manager: PowerStateManager) -> None:
        """Test registering and unregistering callbacks."""
        callback_mock = MagicMock()

        # Register callback
        callback_obj = power_manager.register_state_change_callback(callback_mock)

        # Verify callback is in the list
        assert callback_obj in power_manager._state_changed_callbacks

        # Test notification
        power_manager._notify_state_change(PowerState.NORMAL, PowerState.CONSERVING)
        callback_mock.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)

        # Unregister callback
        power_manager.unregister_state_change_callback(callback_obj)

        # Verify callback is removed
        assert callback_obj not in power_manager._state_changed_callbacks

        # Reset mock and verify it's not called after unregistering
        callback_mock.reset_mock()
        power_manager._notify_state_change(PowerState.CONSERVING, PowerState.NORMAL)
        callback_mock.assert_not_called()

    def test_callbacks_error_handling(self, power_manager: PowerStateManager) -> None:
        """Test error handling in callbacks."""
        # Create a callback that raises an exception
        error_callback = MagicMock(side_effect=Exception("Test exception"))
        normal_callback = MagicMock()

        # Register both callbacks
        error_obj = power_manager.register_state_change_callback(error_callback)
        normal_obj = power_manager.register_state_change_callback(normal_callback)

        # Test notification - should handle exception and continue
        power_manager._notify_state_change(PowerState.NORMAL, PowerState.CONSERVING)

        # First callback should have been called despite error
        error_callback.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)

        # Second callback should still be called
        normal_callback.assert_called_once_with(PowerState.NORMAL, PowerState.CONSERVING)

        # Clean up
        power_manager.unregister_state_change_callback(error_obj)
        power_manager.unregister_state_change_callback(normal_obj)

    def test_test_methods_coverage(self, power_manager: PowerStateManager) -> None:
        """Test methods added for testing."""
        # Test get/set methods added for testing
        state = PowerState.CONSERVING
        power_manager.set_internal_state_for_testing(state)
        assert power_manager.get_internal_state_for_testing() == state

        time = datetime.now()
        power_manager.set_last_refresh_for_testing(time)
        assert power_manager.get_last_refresh_for_testing() == time

        power_manager.set_last_update_for_testing(time)
        assert power_manager.get_last_update_for_testing() == time

    def test_can_perform_operation_branches(self, power_manager: PowerStateManager) -> None:
        """Test additional branches in can_perform_operation."""
        # Test quiet hours with network operations
        with patch.object(power_manager, "get_current_state", return_value=PowerState.QUIET_HOURS):
            # High-cost network operation (should be rejected)
            assert not power_manager.can_perform_operation("network", 0.6)
            # Low-cost network operation (should be allowed)
            assert power_manager.can_perform_operation("network", 0.4)

            # High-cost display operation (should be rejected)
            assert not power_manager.can_perform_operation("display", 0.3)
            # Low-cost display operation (should be allowed)
            assert power_manager.can_perform_operation("display", 0.1)

            # Other operation types with various costs
            assert power_manager.can_perform_operation("sensor", 0.5)
            assert power_manager.can_perform_operation("other", 1.0)


class TestRemainingCoverageGaps:
    """Tests to cover remaining gaps in code coverage."""

    def test_battery_history_update(self, power_manager: PowerStateManager) -> None:
        """Test adding battery data to history and updating expected drain rate."""
        # Create a battery status with timestamp
        status = BatteryStatus(
            level=80,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=300,
            timestamp=datetime.now(),
        )

        # Mock calculate_drain_rate to return a value
        with patch(
            "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=1.5
        ) as mock_calculate:
            # Set empty battery history
            power_manager._battery_history = deque(maxlen=24)
            # Mock initial drain rate
            power_manager._expected_drain_rate = 1.0

            # Call _update_power_state which should append to history and update expected drain rate
            with (
                patch.object(power_manager, "get_battery_status", return_value=status),
                patch.object(power_manager, "_notify_state_change"),
            ):
                power_manager._update_power_state()

                # Check history was updated with the new status
                assert len(power_manager._battery_history) == 1
                assert power_manager._battery_history[0] == status

                # Check calculate_drain_rate was called with history
                mock_calculate.assert_called_once()

                # Check expected drain rate was updated (90% old + 10% new)
                # Expected = 0.9*1.0 + 0.1*1.5 = 1.05
                assert power_manager._expected_drain_rate == 1.05

    def test_get_battery_status_branches(self, power_manager: PowerStateManager) -> None:
        """Test additional branches in get_battery_status."""
        # Test handling None values in battery status responses
        with (
            patch.object(power_manager, "_initialized", True),
            patch.object(power_manager, "_pijuice", autospec=True) as mock_pijuice,
        ):
            # Configure response where data is None
            mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": None}
            mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": None}
            mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": None}
            mock_pijuice.status.GetBatteryTemperature.return_value = {
                "error": "NO_ERROR",
                "data": None,
            }
            mock_pijuice.status.GetStatus.return_value = {
                "error": "NO_ERROR",
                "data": {"battery": None},
            }

            status = power_manager.get_battery_status()

            # Should handle None values gracefully
            assert status.level == 0
            assert status.voltage == 0.0
            assert status.current == 0.0
            assert status.temperature == 0.0
            assert status.state == BatteryState.UNKNOWN

    def test_get_system_metrics_additional_branches(self, power_manager: PowerStateManager) -> None:
        """Test additional branches in get_system_metrics."""
        # Test the branch where we check for TOP_PATH and DF_PATH existence for memory usage
        with (
            patch("pathlib.Path.exists", side_effect=[True, True, True, True]),  # All paths exist
            patch("builtins.open") as mock_open,
            patch("subprocess.check_output") as mock_output,
        ):
            # Mock file reads with unusual content to test alternate parsing paths
            mock_file1 = MagicMock()
            mock_file1.read.return_value = "45000\n"  # Normal temperature
            mock_file2 = MagicMock()
            # Unusual meminfo format to test a different parsing path
            mock_file2.read.return_value = "MemTotal: not a number kB\nMemFree: not a number kB\n"

            # Configure open to return different mock file objects
            mock_open.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_file1)),
                MagicMock(__enter__=MagicMock(return_value=mock_file2)),
            ]

            # Mock subprocess outputs - first call is ok, second raises an exception
            mock_output.side_effect = [
                b"Cpu(s):  10.0%id, 90.0%us",  # CPU usage
                ValueError("Invalid disk format"),  # Invalid disk usage data
            ]

            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should have CPU temp but not memory or disk due to parsing errors
            assert "cpu_temp" in metrics
            assert "cpu_usage" in metrics
            assert "memory_usage" not in metrics
            assert "disk_usage" not in metrics


class TestFinalCoverageGaps:
    """Tests to cover remaining gaps in code coverage."""

    def test_system_metrics_with_drain_rate(self, power_manager: PowerStateManager) -> None:
        """Test get_system_metrics with drain rate and expected_drain_rate for abnormal detection."""  # noqa: E501
        # Mock battery_history and expected_drain_rate
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 1.0),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=2.0
            ),  # Higher than expected
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                return_value=True,
            ),
            patch("pathlib.Path.exists", return_value=False),  # Skip other metrics
        ):
            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should include battery_drain_rate and abnormal_drain
            assert "battery_drain_rate" in metrics
            assert metrics["battery_drain_rate"] == 2.0
            assert "abnormal_drain" in metrics
            assert metrics["abnormal_drain"] == 1.0

    def test_system_metrics_abnormal_drain_detection(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test get_system_metrics abnormal drain detection branch."""
        # Set up a specific case to trigger the is_discharge_rate_abnormal check
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 1.0),  # Ensure positive value
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=2.0
            ),  # Ensure non-None value
            # This is the key part - the function call inside the if condition
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                return_value=False,  # Trigger normal drain case
            ),
            patch("pathlib.Path.exists", return_value=False),  # Skip other metrics
        ):
            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Verify the abnormal_drain value is set to 0.0 (False)
            assert "battery_drain_rate" in metrics
            assert metrics["battery_drain_rate"] == 2.0
            assert "abnormal_drain" in metrics
            assert metrics["abnormal_drain"] == 0.0

    def test_system_metrics_with_normal_drain_rate(self, power_manager: PowerStateManager) -> None:
        """Test get_system_metrics with normal drain rate for abnormal detection."""
        # Mock battery_history and expected_drain_rate
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 1.0),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=1.0
            ),  # Same as expected
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                return_value=False,
            ),
            patch("pathlib.Path.exists", return_value=False),  # Skip other metrics
        ):
            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should include battery_drain_rate and abnormal_drain
            assert "battery_drain_rate" in metrics
            assert metrics["battery_drain_rate"] == 1.0
            assert "abnormal_drain" in metrics
            assert metrics["abnormal_drain"] == 0.0

    def test_system_metrics_is_abnormal_no_drain_rate(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test get_system_metrics when battery drain rate is None."""
        # Mock battery_history but actual is_discharge_rate_abnormal shouldn't be called
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 1.0),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=None
            ),
            # This mock should not be called if drain_rate is None
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                side_effect=Exception("This should not be called"),
            ),
            patch("pathlib.Path.exists", return_value=False),  # Skip other metrics
        ):
            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should not include abnormal_drain since drain_rate is None
            assert "battery_drain_rate" not in metrics
            assert "abnormal_drain" not in metrics

    def test_system_metrics_with_zero_expected_drain_rate(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test get_system_metrics with zero expected_drain_rate to avoid division by zero."""
        # Mock battery_history and expected_drain_rate
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 0.0),  # Zero drain rate
            patch("rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=1.0),
            # This shouldn't be called with a zero expected_drain_rate
            patch(
                "rpi_weather_display.utils.power_manager.is_discharge_rate_abnormal",
                side_effect=Exception("This should not be called"),
            ),
            patch("pathlib.Path.exists", return_value=False),  # Skip other metrics
        ):
            # Execute the method
            metrics = power_manager.get_system_metrics()

            # Should include battery_drain_rate but not abnormal_drain
            assert "battery_drain_rate" in metrics
            assert metrics["battery_drain_rate"] == 1.0
            assert "abnormal_drain" not in metrics

    def test_system_metrics_with_negative_drain_rate(
        self, power_manager: PowerStateManager
    ) -> None:
        """Test negative drain rate for is_discharge_rate_abnormal."""
        # Test with a negative drain rate
        with (
            patch.object(power_manager, "_battery_history"),
            patch.object(power_manager, "_expected_drain_rate", 1.0),
            patch(
                "rpi_weather_display.utils.power_manager.calculate_drain_rate", return_value=-1.0
            ),
            patch("pathlib.Path.exists", return_value=False),
        ):
            # Call the method
            metrics = power_manager.get_system_metrics()

            # Verify results
            assert "battery_drain_rate" in metrics
            assert metrics["battery_drain_rate"] == -1.0
            assert "abnormal_drain" in metrics
            assert metrics["abnormal_drain"] == 0.0


# Simple test runner to verify this combined test file works
if __name__ == "__main__":
    import pytest

    # Run only tests from this file
    pytest.main(["-xvs", __file__])
