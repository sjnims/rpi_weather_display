"""Tests for the PiJuiceAdapter module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.utils.pijuice_adapter import (
    PiJuiceAction,
    PiJuiceAdapter,
    PiJuiceEvent,
)


@pytest.fixture()
def mock_pijuice_hardware() -> MagicMock:
    """Create a mock PiJuice hardware instance."""
    mock = MagicMock()
    mock.status.GetStatus.return_value = {"error": "NO_ERROR", "data": {}}
    mock.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 75}
    mock.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 3700}
    mock.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": -100}
    mock.status.GetBatteryTemperature.return_value = {"error": "NO_ERROR", "data": 25}
    mock.power.SetSystemPowerSwitch.return_value = {"error": "NO_ERROR", "data": {}}
    mock.config.SetSystemTaskParameters.return_value = {"error": "NO_ERROR", "data": {}}
    mock.config.GetSystemTaskParameters.return_value = {
        "error": "NO_ERROR",
        "data": {"function": "SYSTEM_HALT", "delay": 60},
    }
    mock.config.SetButtonConfiguration.return_value = {"error": "NO_ERROR", "data": {}}
    mock.config.GetButtonConfiguration.return_value = {
        "error": "NO_ERROR",
        "data": {"function": "SYSDOWN", "parameter": 2},
    }
    mock.wakeUpOnCharge.SetWakeupEnabled.return_value = {"error": "NO_ERROR", "data": {}}
    return mock


class TestPiJuiceAdapter:
    """Test cases for PiJuiceAdapter class."""

    def test_init(self) -> None:
        """Test PiJuiceAdapter initialization."""
        adapter = PiJuiceAdapter()
        assert adapter.pijuice is None
        assert not adapter._initialized

    def test_init_with_instance(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test PiJuiceAdapter initialization with existing instance."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        assert adapter.pijuice == mock_pijuice_hardware

    def test_initialize_with_existing_instance(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test initialization when instance already provided."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.initialize()
        assert result is True
        assert adapter._initialized is True

    def test_initialize_hardware_not_available(self) -> None:
        """Test initialization when PiJuice library not available."""
        adapter = PiJuiceAdapter()
        with patch("builtins.__import__", side_effect=ImportError("No module named 'pijuice'")):
            result = adapter.initialize()
            assert result is False
            assert not adapter._initialized

    def test_initialize_hardware_error(self) -> None:
        """Test initialization when hardware connection fails."""
        adapter = PiJuiceAdapter()
        
        # Mock the module import to succeed but PiJuice class to fail
        mock_module = MagicMock()
        mock_module.PiJuice.side_effect = Exception("Hardware error")
        
        with patch.dict("sys.modules", {"pijuice": mock_module}):
            result = adapter.initialize()
            assert result is False

    def test_initialize_success(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test successful hardware initialization."""
        adapter = PiJuiceAdapter()
        
        # Mock the module import to succeed
        mock_module = MagicMock()
        mock_module.PiJuice.return_value = mock_pijuice_hardware
        
        with patch.dict("sys.modules", {"pijuice": mock_module}):
            result = adapter.initialize()
            assert result is True
            assert adapter._initialized is True
            mock_module.PiJuice.assert_called_once_with(1, 0x14)

    def test_get_status_not_initialized(self) -> None:
        """Test get_status when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_status()
        assert result["error"] == "NOT_INITIALIZED"

    def test_get_status_success(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test successful status retrieval."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_status()
        assert result["error"] == "NO_ERROR"
        mock_pijuice_hardware.status.GetStatus.assert_called_once()

    def test_get_charge_level(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test charge level retrieval."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_charge_level()
        assert result["error"] == "NO_ERROR"
        assert result["data"] == 75

    def test_get_battery_voltage(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test battery voltage retrieval."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_battery_voltage()
        assert result["error"] == "NO_ERROR"
        assert result["data"] == 3700

    def test_get_battery_current(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test battery current retrieval."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_battery_current()
        assert result["error"] == "NO_ERROR"
        assert result["data"] == -100

    def test_get_battery_temperature(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test battery temperature retrieval."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_battery_temperature()
        assert result["error"] == "NO_ERROR"
        assert result["data"] == 25

    def test_set_alarm(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test setting RTC alarm."""
        # Configure mock to return success
        mock_pijuice_hardware.rtcAlarm.SetAlarm.return_value = {"error": "NO_ERROR"}
        mock_pijuice_hardware.rtcAlarm.SetWakeupEnabled.return_value = {"error": "NO_ERROR"}
        
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        wake_time = datetime(2024, 5, 25, 10, 30, 0)

        result = adapter.set_alarm(wake_time)
        assert result is True

        # Verify alarm was set with correct parameters
        mock_pijuice_hardware.rtcAlarm.SetAlarm.assert_called_once()
        alarm_config = mock_pijuice_hardware.rtcAlarm.SetAlarm.call_args[0][0]
        assert alarm_config["hour"] == 10
        assert alarm_config["minute"] == 30
        assert alarm_config["year"] == 24  # 2024 - 2000

    def test_set_alarm_not_initialized(self) -> None:
        """Test setting alarm when not initialized."""
        from rpi_weather_display.exceptions import WakeupSchedulingError
        
        adapter = PiJuiceAdapter()
        with pytest.raises(WakeupSchedulingError) as exc_info:
            adapter.set_alarm(datetime.now())
        
        assert "PiJuice not initialized" in str(exc_info.value)

    def test_set_alarm_failure(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test setting alarm when it fails."""
        from rpi_weather_display.exceptions import WakeupSchedulingError
        
        # Configure mock to return error
        mock_pijuice_hardware.rtcAlarm.SetAlarm.return_value = {"error": "COMMUNICATION_ERROR"}
        
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        wake_time = datetime(2024, 5, 25, 10, 30, 0)
        
        with pytest.raises(WakeupSchedulingError) as exc_info:
            adapter.set_alarm(wake_time)
        
        assert "Failed to set RTC alarm" in str(exc_info.value)
        assert exc_info.value.details["target_time"] == wake_time.isoformat()

    def test_disable_wakeup(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test disabling wakeup alarm."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.disable_wakeup()
        assert result is True
        mock_pijuice_hardware.wakeUpOnCharge.SetWakeupEnabled.assert_called_once_with(False)

    def test_set_power_switch(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test setting power switch state."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.set_power_switch(1)
        assert result is True
        mock_pijuice_hardware.power.SetSystemPowerSwitch.assert_called_once_with(1)

    def test_configure_event_system_task(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test configuring system task event."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.configure_event(
            PiJuiceEvent.LOW_CHARGE, PiJuiceAction.SYSTEM_HALT_POW_OFF, 60
        )
        assert result is True
        mock_pijuice_hardware.config.SetSystemTaskParameters.assert_called_once_with(
            "LOW_CHARGE", "SYSTEM_HALT_POW_OFF", 60
        )

    def test_configure_event_button(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test configuring button event."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.configure_event(
            PiJuiceEvent.BUTTON_SW1_PRESS, PiJuiceAction.SYSTEM_WAKEUP, 2
        )
        assert result is True
        mock_pijuice_hardware.config.SetButtonConfiguration.assert_called_once()

    def test_get_event_configuration_system_task(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test getting system task event configuration."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {"function": "SYSTEM_HALT", "delay": 60}

    def test_get_event_configuration_button(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test getting button event configuration."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_event_configuration(PiJuiceEvent.BUTTON_SW1_PRESS)
        assert result == {"function": "SYSDOWN", "parameter": 2}

    def test_is_initialized(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test initialization status check."""
        adapter = PiJuiceAdapter()
        assert not adapter.is_initialized()

        adapter._initialized = True
        adapter.pijuice = mock_pijuice_hardware
        assert adapter.is_initialized()

    def test_initialize_already_initialized(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test initialization when already initialized."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        adapter.initialize()
        assert adapter._initialized is True
        
        # Second initialization should return early
        result = adapter.initialize()
        assert result is True

    def test_initialize_bad_status(self) -> None:
        """Test initialization when status check fails."""
        adapter = PiJuiceAdapter()
        
        # Mock the module import to succeed
        mock_module = MagicMock()
        mock_pijuice_hardware = MagicMock()
        mock_pijuice_hardware.status.GetStatus.return_value = {"error": "COMMUNICATION_ERROR", "data": {}}
        mock_module.PiJuice.return_value = mock_pijuice_hardware
        
        with patch.dict("sys.modules", {"pijuice": mock_module}):
            result = adapter.initialize()
            assert result is False
            assert not adapter._initialized

    def test_get_status_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_status with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.status.GetStatus.side_effect = Exception("Communication error")
        
        result = adapter.get_status()
        assert result["error"] == "Communication error"
        assert result["data"] == {}

    def test_get_charge_level_not_initialized(self) -> None:
        """Test get_charge_level when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_charge_level()
        assert result["error"] == "NOT_INITIALIZED"
        assert result["data"] == 0

    def test_get_charge_level_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_charge_level with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.status.GetChargeLevel.side_effect = Exception("Read error")
        
        result = adapter.get_charge_level()
        assert result["error"] == "Read error"
        assert result["data"] == 0

    def test_get_battery_voltage_not_initialized(self) -> None:
        """Test get_battery_voltage when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_battery_voltage()
        assert result["error"] == "NOT_INITIALIZED"
        assert result["data"] == 0

    def test_get_battery_voltage_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_battery_voltage with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.status.GetBatteryVoltage.side_effect = Exception("Read error")
        
        result = adapter.get_battery_voltage()
        assert result["error"] == "Read error"
        assert result["data"] == 0

    def test_get_battery_current_not_initialized(self) -> None:
        """Test get_battery_current when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_battery_current()
        assert result["error"] == "NOT_INITIALIZED"
        assert result["data"] == 0

    def test_get_battery_current_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_battery_current with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.status.GetBatteryCurrent.side_effect = Exception("Read error")
        
        result = adapter.get_battery_current()
        assert result["error"] == "Read error"
        assert result["data"] == 0

    def test_get_battery_temperature_not_initialized(self) -> None:
        """Test get_battery_temperature when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_battery_temperature()
        assert result["error"] == "NOT_INITIALIZED"
        assert result["data"] == 0

    def test_get_battery_temperature_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_battery_temperature with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.status.GetBatteryTemperature.side_effect = Exception("Read error")
        
        result = adapter.get_battery_temperature()
        assert result["error"] == "Read error"
        assert result["data"] == 0

    def test_set_alarm_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test set_alarm with exception."""
        from rpi_weather_display.exceptions import WakeupSchedulingError
        
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.rtcAlarm.SetAlarm.side_effect = Exception("RTC error")
        
        with pytest.raises(WakeupSchedulingError) as exc_info:
            adapter.set_alarm(datetime.now())
        
        assert "Failed to schedule wakeup" in str(exc_info.value)
        assert "RTC error" in exc_info.value.details["error"]

    def test_disable_wakeup_not_initialized(self) -> None:
        """Test disable_wakeup when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.disable_wakeup()
        assert result is False

    def test_disable_wakeup_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test disable_wakeup with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.wakeUpOnCharge.SetWakeupEnabled.side_effect = Exception("Config error")
        
        result = adapter.disable_wakeup()
        assert result is False

    def test_set_power_switch_not_initialized(self) -> None:
        """Test set_power_switch when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.set_power_switch(1)
        assert result is False

    def test_set_power_switch_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test set_power_switch with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.power.SetSystemPowerSwitch.side_effect = Exception("Power error")
        
        result = adapter.set_power_switch(1)
        assert result is False

    def test_configure_event_not_initialized(self) -> None:
        """Test configure_event when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.configure_event(PiJuiceEvent.LOW_CHARGE, PiJuiceAction.SYSTEM_HALT)
        assert result is False

    def test_configure_event_unknown_event(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test configure_event with unknown event type."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.configure_event(PiJuiceEvent.SYSTEM_WAKEUP, PiJuiceAction.SYSTEM_HALT)
        assert result is False

    def test_configure_event_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test configure_event with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.config.SetSystemTaskParameters.side_effect = Exception("Config error")
        
        result = adapter.configure_event(PiJuiceEvent.LOW_CHARGE, PiJuiceAction.SYSTEM_HALT)
        assert result is False

    def test_get_event_configuration_not_initialized(self) -> None:
        """Test get_event_configuration when not initialized."""
        adapter = PiJuiceAdapter()
        result = adapter.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}

    def test_get_event_configuration_unknown_event(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_event_configuration with unknown event type."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        result = adapter.get_event_configuration(PiJuiceEvent.SYSTEM_WAKEUP)
        assert result == {}

    def test_get_event_configuration_error_response(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_event_configuration with error response."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.config.GetSystemTaskParameters.return_value = {
            "error": "COMMUNICATION_ERROR",
            "data": {}
        }
        
        result = adapter.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}

    def test_get_event_configuration_non_dict_data(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_event_configuration with non-dict data."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.config.GetSystemTaskParameters.return_value = {
            "error": "NO_ERROR",
            "data": "invalid"
        }
        
        result = adapter.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}

    def test_get_event_configuration_exception(self, mock_pijuice_hardware: MagicMock) -> None:
        """Test get_event_configuration with exception."""
        adapter = PiJuiceAdapter(mock_pijuice_hardware)
        mock_pijuice_hardware.config.GetSystemTaskParameters.side_effect = Exception("Config error")
        
        result = adapter.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
        assert result == {}
