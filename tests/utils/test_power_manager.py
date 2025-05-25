"""Tests for the refactored PowerStateManager class."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
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
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.utils import PowerState, PowerStateManager

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.test_helpers.power_manager_test_helpers import PowerStateManagerTestHelper


@pytest.fixture()
def default_config() -> AppConfig:
    """Create a default app config for testing."""
    return AppConfig(
        weather=WeatherConfig(
            api_key="test_key",
            location={"lat": 0.0, "lon": 0.0},
            update_interval_minutes=30,
        ),
        display=DisplayConfig(
            refresh_interval_minutes=30,
            refresh_interval_low_battery_minutes=60,
            refresh_interval_critical_battery_minutes=120,
            refresh_interval_charging_minutes=15,
            battery_aware_refresh=True,
        ),
        power=PowerConfig(
            quiet_hours_start="23:00",
            quiet_hours_end="06:00",
            low_battery_threshold=20,
            critical_battery_threshold=10,
            battery_capacity_mah=12000,
            wake_up_interval_minutes=60,
        ),
        server=ServerConfig(url="http://localhost"),
        logging=LoggingConfig(),
        debug=False,
    )


@pytest.fixture()
def power_manager(default_config: AppConfig) -> PowerStateManager:
    """Create a PowerStateManager with the default config."""
    return PowerStateManager(default_config)


class TestPowerStateManagerPublicInterface:
    """Tests for the public interface of PowerStateManager."""

    def test_init(self, default_config: AppConfig) -> None:
        """Test initialization of the power state manager."""
        manager = PowerStateManager(default_config)
        assert manager.config == default_config
        helper = PowerStateManagerTestHelper()
        assert not helper.get_initialization_status(manager)
        assert manager.get_current_state() == PowerState.NORMAL

    def test_initialize(self, power_manager: PowerStateManager) -> None:
        """Test initialization process."""
        power_manager.initialize()
        helper = PowerStateManagerTestHelper()
        assert helper.get_initialization_status(power_manager)

    def test_get_battery_status(self, power_manager: PowerStateManager) -> None:
        """Test battery status retrieval."""
        power_manager.initialize()
        status = power_manager.get_battery_status()
        assert isinstance(status, BatteryStatus)
        assert status.level >= 0
        assert status.level <= 100

    def test_get_current_state(self, power_manager: PowerStateManager) -> None:
        """Test getting current power state."""
        power_manager.initialize()
        state = power_manager.get_current_state()
        assert isinstance(state, PowerState)

    def test_should_refresh_display(self, power_manager: PowerStateManager) -> None:
        """Test display refresh decision."""
        power_manager.initialize()
        should_refresh = power_manager.should_refresh_display()
        assert isinstance(should_refresh, bool)

    def test_should_update_weather(self, power_manager: PowerStateManager) -> None:
        """Test weather update decision."""
        power_manager.initialize()
        should_update = power_manager.should_update_weather()
        assert isinstance(should_update, bool)

    def test_record_display_refresh(self, power_manager: PowerStateManager) -> None:
        """Test recording display refresh."""
        power_manager.initialize()
        power_manager.record_display_refresh()
        # After recording, the last refresh time should be set
        helper = PowerStateManagerTestHelper()
        assert helper.get_last_refresh(power_manager) is not None

    def test_record_weather_update(self, power_manager: PowerStateManager) -> None:
        """Test recording weather update."""
        power_manager.initialize()
        power_manager.record_weather_update()
        # After recording, the last update time should be set
        helper = PowerStateManagerTestHelper()
        assert helper.get_last_update(power_manager) is not None

    def test_calculate_sleep_time(self, power_manager: PowerStateManager) -> None:
        """Test sleep time calculation."""
        power_manager.initialize()
        sleep_time = power_manager.calculate_sleep_time()
        assert isinstance(sleep_time, int)
        assert sleep_time > 0

    def test_can_perform_operation(self, power_manager: PowerStateManager) -> None:
        """Test operation permission checking."""
        power_manager.initialize()
        can_perform = power_manager.can_perform_operation("display_refresh")
        assert isinstance(can_perform, bool)

    def test_enter_low_power_mode(self, power_manager: PowerStateManager) -> None:
        """Test entering low power mode."""
        power_manager.initialize()
        power_manager.enter_low_power_mode()
        # Should change state to at least CONSERVING
        state = power_manager.get_current_state()
        assert state in [PowerState.CONSERVING, PowerState.CRITICAL]

    def test_shutdown_system_dev_mode(self, power_manager: PowerStateManager) -> None:
        """Test shutdown in development mode."""
        power_manager.config.development_mode = True
        power_manager.shutdown_system()  # Should not actually shutdown

    def test_schedule_wakeup(self, power_manager: PowerStateManager) -> None:
        """Test wakeup scheduling."""
        power_manager.initialize()
        result = power_manager.schedule_wakeup(30)
        assert isinstance(result, bool)

    def test_get_system_metrics(self, power_manager: PowerStateManager) -> None:
        """Test system metrics retrieval."""
        metrics = power_manager.get_system_metrics()
        assert isinstance(metrics, dict)

    def test_state_change_callbacks(self, power_manager: PowerStateManager) -> None:
        """Test state change callback registration."""
        power_manager.initialize()

        callback_called = False

        def test_callback(old_state: PowerState, new_state: PowerState) -> None:
            nonlocal callback_called
            callback_called = True

        callback_obj = power_manager.register_state_change_callback(test_callback)
        assert callback_obj is not None

        # Force a state change by setting state
        helper = PowerStateManagerTestHelper()
        helper.set_internal_state(power_manager, PowerState.CHARGING)
        power_manager.enter_low_power_mode()  # This should trigger a state change

        # Unregister callback
        power_manager.unregister_state_change_callback(callback_obj)

    def test_battery_life_estimation(self, power_manager: PowerStateManager) -> None:
        """Test battery life estimation."""
        power_manager.initialize()
        battery_life = power_manager.get_expected_battery_life()
        # May be None if charging or no data
        assert battery_life is None or isinstance(battery_life, int)

    def test_discharge_rate_check(self, power_manager: PowerStateManager) -> None:
        """Test abnormal discharge rate detection."""
        power_manager.initialize()
        is_abnormal = power_manager.is_discharge_rate_abnormal()
        assert isinstance(is_abnormal, bool)

    def test_get_event_configuration(self, power_manager: PowerStateManager) -> None:
        """Test event configuration retrieval."""
        power_manager.initialize()
        config = power_manager.get_event_configuration("LOW_CHARGE")
        assert isinstance(config, dict)


class TestPowerStateManagerCoverage:
    """Additional tests to improve coverage of PowerStateManager."""

    @pytest.fixture()
    def production_config(self) -> AppConfig:
        """Create a production config (development_mode=False)."""
        return AppConfig(
            weather=WeatherConfig(
                api_key="test_key",
                location={"lat": 0.0, "lon": 0.0},
                update_interval_minutes=30,
            ),
            display=DisplayConfig(
                refresh_interval_minutes=30,
                refresh_interval_low_battery_minutes=60,
                refresh_interval_critical_battery_minutes=120,
                refresh_interval_charging_minutes=15,
                battery_aware_refresh=True,
            ),
            power=PowerConfig(
                quiet_hours_start="23:00",
                quiet_hours_end="06:00",
                low_battery_threshold=20,
                critical_battery_threshold=10,
                battery_capacity_mah=12000,
                wake_up_interval_minutes=60,
            ),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
            debug=False,
            development_mode=False,
        )

    def test_initialize_with_pijuice_hardware(self, production_config: AppConfig) -> None:
        """Test initialization with PiJuice hardware (non-development mode)."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            # Verify PiJuice adapter was created
            mock_adapter_class.assert_called_once()
            mock_adapter.initialize.assert_called_once()

    def test_initialize_with_pijuice_failure(self, production_config: AppConfig) -> None:
        """Test initialization when PiJuice initialization fails."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = False
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            # Should still initialize but adapter should be None
            assert manager._initialized

    def test_initialize_already_initialized(self, power_manager: PowerStateManager) -> None:
        """Test initialize when already initialized (early return)."""
        # First initialization
        power_manager.initialize()

        # Mock the components to track if they're recreated
        original_monitor = power_manager._battery_monitor
        original_controller = power_manager._power_controller

        # Second initialization should return early
        power_manager.initialize()

        # Components should not be recreated
        assert power_manager._battery_monitor is original_monitor
        assert power_manager._power_controller is original_controller

    def test_get_battery_status_not_initialized(self) -> None:
        """Test get_battery_status when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        with pytest.raises(RuntimeError, match="Power state manager not initialized"):
            manager.get_battery_status()

    def test_get_current_state_not_initialized(self) -> None:
        """Test get_current_state when power controller not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return NORMAL when not initialized
        assert manager.get_current_state() == PowerState.NORMAL

    def test_should_refresh_display_not_initialized(self) -> None:
        """Test should_refresh_display when power controller not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return True when not initialized
        assert manager.should_refresh_display() is True

    def test_should_update_weather_not_initialized(self) -> None:
        """Test should_update_weather when power controller not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return True when not initialized
        assert manager.should_update_weather() is True

    def test_register_state_change_callback_not_initialized(self) -> None:
        """Test register_state_change_callback when power controller not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return None when not initialized
        result = manager.register_state_change_callback(lambda _old, _new: None)
        assert result is None

    def test_shutdown_system_production_mode(self, production_config: AppConfig) -> None:
        """Test shutdown_system in production mode."""
        manager = PowerStateManager(production_config)
        manager.initialize()

        with patch("subprocess.run") as mock_run:
            manager.shutdown_system()

            # Verify shutdown command was called
            mock_run.assert_called_once_with(
                ["/usr/bin/sudo", "/sbin/shutdown", "-h", "now"],
                check=True,
            )

    def test_shutdown_system_production_mode_error(self, production_config: AppConfig) -> None:
        """Test shutdown_system when shutdown command fails."""
        manager = PowerStateManager(production_config)
        manager.initialize()

        with patch("subprocess.run", side_effect=subprocess.SubprocessError("Shutdown failed")):
            # Should not raise, just log error
            manager.shutdown_system()

    def test_schedule_wakeup_with_adapter(self, production_config: AppConfig) -> None:
        """Test schedule_wakeup with PiJuice adapter."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter.set_alarm.return_value = True
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            result = manager.schedule_wakeup(30)

            assert result is True
            mock_adapter.set_alarm.assert_called_once()

    def test_schedule_wakeup_without_adapter(self, power_manager: PowerStateManager) -> None:
        """Test schedule_wakeup when no PiJuice adapter."""
        power_manager.initialize()

        # Should return True (mocked) when no adapter
        result = power_manager.schedule_wakeup(30)
        assert result is True

    def test_schedule_wakeup_dynamic_mode(self, production_config: AppConfig) -> None:
        """Test schedule_wakeup with dynamic mode enabled."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter.set_alarm.return_value = True
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            # Mock the power controller to return a different time
            mock_calculate_sleep_time = MagicMock(return_value=60)
            if manager._power_controller:
                manager._power_controller.calculate_sleep_time = mock_calculate_sleep_time

            result = manager.schedule_wakeup(30, dynamic=True)

            assert result is True
            # Should use the dynamic time (60) not the base time (30)
            if manager._power_controller:
                mock_calculate_sleep_time.assert_called_once()

    def test_get_expected_battery_life_not_initialized(self) -> None:
        """Test get_expected_battery_life when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return None when not initialized
        assert manager.get_expected_battery_life() is None

    def test_is_discharge_rate_abnormal_not_initialized(self) -> None:
        """Test is_discharge_rate_abnormal when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return False when not initialized
        assert manager.is_discharge_rate_abnormal() is False

    def test_calculate_sleep_time_not_initialized(self) -> None:
        """Test calculate_sleep_time when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return default 30 when not initialized
        assert manager.calculate_sleep_time() == 30

    def test_can_perform_operation_not_initialized(self) -> None:
        """Test can_perform_operation when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return True when not initialized
        assert manager.can_perform_operation("test") is True

    def test_record_display_refresh_not_initialized(self) -> None:
        """Test record_display_refresh when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should not raise when not initialized
        manager.record_display_refresh()

    def test_record_weather_update_not_initialized(self) -> None:
        """Test record_weather_update when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should not raise when not initialized
        manager.record_weather_update()

    def test_enter_low_power_mode_not_initialized(self) -> None:
        """Test enter_low_power_mode when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should not raise when not initialized
        manager.enter_low_power_mode()

    def test_get_event_configuration_invalid_event(self, production_config: AppConfig) -> None:
        """Test get_event_configuration with invalid event type."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            # Should return empty dict for invalid event
            result = manager.get_event_configuration("INVALID_EVENT")
            assert result == {}

    def test_get_event_configuration_no_adapter(self, power_manager: PowerStateManager) -> None:
        """Test get_event_configuration when no adapter."""
        power_manager.initialize()

        # Should return empty dict when no adapter
        result = power_manager.get_event_configuration("LOW_CHARGE")
        assert result == {}

    def test_unregister_state_change_callback(self, power_manager: PowerStateManager) -> None:
        """Test unregister_state_change_callback."""
        power_manager.initialize()

        # Register a callback first
        callback_obj = power_manager.register_state_change_callback(lambda _old, _new: None)

        # Should not raise when unregistering
        if callback_obj:
            power_manager.unregister_state_change_callback(callback_obj)

    def test_unregister_state_change_callback_no_controller(self) -> None:
        """Test unregister_state_change_callback when no controller."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should not raise even with no controller
        manager.unregister_state_change_callback(MagicMock())

    def test_schedule_wakeup_alarm_fails(self, production_config: AppConfig) -> None:
        """Test schedule_wakeup when set_alarm fails."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter.set_alarm.return_value = False
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            result = manager.schedule_wakeup(30)

            assert result is False

    def test_get_event_configuration_valid_event(self, production_config: AppConfig) -> None:
        """Test get_event_configuration with valid event type."""
        manager = PowerStateManager(production_config)

        with patch("rpi_weather_display.utils.power_manager.PiJuiceAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter.get_event_configuration.return_value = {
                "enabled": True,
                "function": "SYSTEM_HALT",
            }
            mock_adapter_class.return_value = mock_adapter

            manager.initialize()

            result = manager.get_event_configuration("LOW_CHARGE")
            assert result == {"enabled": True, "function": "SYSTEM_HALT"}

    def test_test_helper_methods(self, power_manager: PowerStateManager) -> None:
        """Test the test helper methods."""
        power_manager.initialize()

        # Test get_internal_state
        helper = PowerStateManagerTestHelper()
        state = helper.get_internal_state(power_manager)
        assert isinstance(state, PowerState)

        # Test set_internal_state
        helper.set_internal_state(power_manager, PowerState.CHARGING)
        assert helper.get_internal_state(power_manager) == PowerState.CHARGING

        # Test get/set_last_refresh
        test_time = datetime.now()
        helper.set_last_refresh(power_manager, test_time)
        assert helper.get_last_refresh(power_manager) == test_time

        # Test get/set_last_update
        helper.set_last_update(power_manager, test_time)
        assert helper.get_last_update(power_manager) == test_time

    def test_test_helper_methods_not_initialized(self) -> None:
        """Test the test helper methods when not initialized."""
        config = AppConfig(
            weather=WeatherConfig(api_key="test", location={"lat": 0, "lon": 0}),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
            logging=LoggingConfig(),
        )
        manager = PowerStateManager(config)

        # Should return defaults when not initialized
        helper = PowerStateManagerTestHelper()
        assert helper.get_internal_state(manager) == PowerState.NORMAL
        assert helper.get_last_refresh(manager) is None
        assert helper.get_last_update(manager) is None

        # Should not raise when setting
        helper.set_internal_state(manager, PowerState.CHARGING)
        helper.set_last_refresh(manager, datetime.now())
        helper.set_last_update(manager, datetime.now())
