"""Additional tests for PowerStateManager focusing on specific coverage gaps."""

# ruff: noqa: S101, A002, PLR2004
# pyright: reportPrivateUsage=false

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
def power_manager(default_config: AppConfig) -> PowerStateManager:
    """Create a PowerStateManager with the default config."""
    return PowerStateManager(default_config)


class TestPowerStateManagerAdditional:
    """Additional tests for PowerStateManager focusing on specific coverage gaps."""

    def test_notify_state_change_with_exception(self, power_manager: PowerStateManager) -> None:
        """Test _notify_state_change with a callback that raises an exception."""
        # Create a callback that raises an exception
        failing_callback = MagicMock(side_effect=Exception("Test exception"))

        # Register the failing callback
        callback_obj = power_manager.register_state_change_callback(failing_callback)

        # Call _notify_state_change - should handle the exception gracefully
        try:
            power_manager._notify_state_change(PowerState.NORMAL, PowerState.CONSERVING)
            # If we reach here, the exception was handled correctly
            pass
        except Exception:
            # If an exception is raised, the test should fail
            pytest.fail("Exception not handled correctly in _notify_state_change")

        # Clean up
        power_manager.unregister_state_change_callback(callback_obj)

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

    def test_additional_branch_conditions(self, power_manager: PowerStateManager) -> None:
        """Test additional branch conditions for code coverage."""
        # Test enter_low_power_mode triggering a state change notification
        with patch.object(power_manager, "_notify_state_change") as mock_notify:
            power_manager.enter_low_power_mode()
            mock_notify.assert_called_once()
            assert power_manager.get_internal_state_for_testing() == PowerState.CONSERVING
