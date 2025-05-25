"""Additional tests for BatteryMonitor to improve coverage."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.models.config import AppConfig, PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils.battery_monitor import BatteryMonitor
from rpi_weather_display.utils.pijuice_adapter import PiJuiceAdapter


@pytest.fixture()
def mock_config() -> AppConfig:
    """Create a mock configuration for testing."""
    config = MagicMock(spec=AppConfig)
    config.development_mode = False
    config.power = MagicMock(spec=PowerConfig)
    config.power.battery_capacity_mah = 12000
    config.power.abnormal_discharge_threshold = 50.0
    config.power.low_battery_threshold = 20
    config.power.critical_battery_threshold = 10
    config.power.expected_discharge_rate = 2.0  # Add expected discharge rate
    return config


@pytest.fixture()
def mock_pijuice() -> MagicMock:
    """Create a mock PiJuice adapter."""
    mock = MagicMock(spec=PiJuiceAdapter)
    mock.get_status.return_value = {
        "error": "NO_ERROR",
        "data": {
            "battery": "NORMAL",
            "powerInput": "NOT_PRESENT",
            "powerInput5vIo": "NOT_PRESENT",
            "isFault": False,
        },
    }
    mock.get_charge_level.return_value = {"error": "NO_ERROR", "data": 75}
    mock.get_battery_voltage.return_value = {"error": "NO_ERROR", "data": 3700}
    mock.get_battery_current.return_value = {"error": "NO_ERROR", "data": -100}
    mock.get_battery_temperature.return_value = {"error": "NO_ERROR", "data": 25}
    return mock


class TestBatteryMonitorCoverage:
    """Additional test cases for BatteryMonitor coverage."""

    def test_get_battery_status_with_fault(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when PiJuice reports a fault."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "PRESENT",
                "powerInput5vIo": "PRESENT",
                "isFault": True,  # Fault condition
            },
        }
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert isinstance(status, BatteryStatus)
        assert hasattr(status, "_pijuice_fault")
        assert status._pijuice_fault is True  # type: ignore[attr-defined]

    def test_get_battery_status_fully_charged(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when fully charged (power present, high charge, not charging)."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",  # Not charging
                "powerInput": "PRESENT",  # Power connected
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 96}  # High charge
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert status.state == BatteryState.CHARGING  # Should be detected as charging
        assert status.level == 96

    def test_get_battery_status_fully_charged_below_threshold(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when power present but charge below 95%."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",  # Not charging
                "powerInput": "PRESENT",  # Power connected
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 90}  # Below 95%
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert status.state == BatteryState.DISCHARGING  # Should use NORMAL -> DISCHARGING
        assert status.level == 90

    def test_get_battery_status_power_present_not_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when power is present but battery not charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",  # Not a charging state
                "powerInput": "WEAK",  # Weak power input
                "powerInput5vIo": "NOT_PRESENT",
                "isFault": False,
            },
        }
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 50}
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert status.state == BatteryState.DISCHARGING
        assert hasattr(status, "_power_input")
        assert status._power_input == "WEAK"  # type: ignore[attr-defined]

    def test_get_battery_status_invalid_response_types(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status with invalid response data types."""
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": "invalid"}
        mock_pijuice.get_battery_voltage.return_value = {"error": "NO_ERROR", "data": None}
        mock_pijuice.get_battery_current.return_value = {"error": "ERROR", "data": -100}
        mock_pijuice.get_battery_temperature.return_value = {"error": "NO_ERROR", "data": []}
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        status = monitor.get_battery_status()
        
        # Should handle invalid types gracefully
        assert status.level == 0  # Invalid charge data
        assert status.voltage == 0.0  # Invalid voltage data
        assert status.current == 0.0  # Error response
        assert status.temperature == 0.0  # Invalid temp data

    def test_drain_rate_calculation(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test drain rate calculation with battery history."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Simulate multiple readings with decreasing charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 80}
        monitor.get_battery_status()
        
        # Advance time and reduce charge
        with patch('rpi_weather_display.utils.battery_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(hours=1)
            mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 78}
            
            # Mock calculate_drain_rate to return a value
            with patch('rpi_weather_display.utils.battery_monitor.calculate_drain_rate') as mock_calc:
                mock_calc.return_value = 240.0  # 240mA drain rate
                monitor.get_battery_status()
                
                # Check that drain rate was updated
                assert monitor._current_drain_rate != 100.0  # Changed from default
                mock_calc.assert_called_once()

    def test_get_expected_battery_life_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life calculation with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = Exception("Test error")
            
            life = monitor.get_expected_battery_life()
            assert life is None

    def test_get_expected_battery_life_zero_drain(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life calculation with zero drain rate."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 0.0  # Zero drain
        
        life = monitor.get_expected_battery_life()
        assert life is None  # Can't calculate with zero drain

    def test_is_discharge_rate_abnormal_with_fault(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test abnormal discharge rate detection with fault status."""
        # Set up fault condition
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "NOT_PRESENT",
                "powerInput5vIo": "NOT_PRESENT",
                "isFault": True,
            },
        }
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor.get_battery_status()  # This will set the fault flag
        
        # Should return True due to fault
        assert monitor.is_discharge_rate_abnormal() is True

    def test_is_discharge_rate_abnormal_no_expected_rate_config(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test abnormal discharge rate detection without expected_discharge_rate config."""
        # Remove the expected_discharge_rate attribute
        delattr(mock_config.power, 'expected_discharge_rate')
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 2.5  # Between default 2.0 and threshold 3.0
        
        # Should use default expected rate of 2.0
        assert monitor.is_discharge_rate_abnormal() is False
        
        monitor._current_drain_rate = 4.0  # Above threshold (2.0 * 1.5 = 3.0)
        assert monitor.is_discharge_rate_abnormal() is True

    def test_is_discharge_rate_abnormal_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test abnormal discharge rate detection with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = Exception("Test error")
            
            result = monitor.is_discharge_rate_abnormal()
            assert result is False  # Returns False on error

    def test_should_conserve_power_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test power conservation check with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = Exception("Test error")
            
            result = monitor.should_conserve_power()
            assert result is True  # Conserves power on error

    def test_is_battery_critical_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test critical battery check with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = Exception("Test error")
            
            result = monitor.is_battery_critical()
            assert result is False  # Returns False on error

    def test_get_diagnostic_info(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test getting diagnostic information."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "PRESENT",
                "powerInput5vIo": "5V_PRESENT",
                "isFault": True,
            },
        }
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 150.0
        
        # Get diagnostic info
        info = monitor.get_diagnostic_info()
        
        assert info["power_input"] == "PRESENT"
        assert info["io_voltage"] == "5V_PRESENT"
        assert info["is_fault"] is True
        assert info["battery_level"] == 75
        assert info["battery_state"] == "discharging"
        assert info["drain_rate"] == 150.0

    def test_get_diagnostic_info_no_private_attrs(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test diagnostic info when private attributes don't exist."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Create a status without private attributes
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            status = BatteryStatus(
                level=50,
                voltage=3.6,
                current=-100,
                temperature=22,
                state=BatteryState.DISCHARGING,
                timestamp=datetime.now()
            )
            # Don't set private attributes
            mock_get_status.return_value = status
            
            info = monitor.get_diagnostic_info()
            
            assert info["power_input"] == "UNKNOWN"
            assert info["io_voltage"] == "UNKNOWN" 
            assert info["is_fault"] is False
            assert info["battery_level"] == 50

    def test_get_diagnostic_info_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test diagnostic info with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = Exception("Test error")
            
            info = monitor.get_diagnostic_info()
            assert info == {}  # Returns empty dict on error

    def test_battery_history_max_size(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test that battery history respects maximum size."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Get status more times than history size (24)
        for i in range(30):
            mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 90 - i}
            monitor.get_battery_status()
        
        history = monitor.get_battery_history()
        assert len(history) == 24  # BATTERY_HISTORY_SIZE constant
        
        # Check that oldest entries were removed (newest should have lower charge)
        assert history[-1].level < history[0].level

    def test_battery_history_only_positive_charge(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test that battery history only includes positive charge levels."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # First reading with positive charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 50}
        monitor.get_battery_status()
        
        # Second reading with zero charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 0}
        monitor.get_battery_status()
        
        # Third reading with positive charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 45}
        monitor.get_battery_status()
        
        history = monitor.get_battery_history()
        # Should only have first and third readings
        assert len(history) == 2
        assert all(status.level > 0 for status in history)