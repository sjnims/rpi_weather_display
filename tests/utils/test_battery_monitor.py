"""Comprehensive tests for the BatteryMonitor module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.exceptions import (
    BatteryMonitoringError,
    CriticalBatteryError,
    PiJuiceCommunicationError,
    PiJuiceInitializationError,
)
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
    config.power.expected_discharge_rate = 2.0
    return config


@pytest.fixture()
def mock_pijuice() -> MagicMock:
    """Create a mock PiJuice adapter."""
    pijuice = MagicMock(spec=PiJuiceAdapter)
    
    # Default successful responses
    pijuice.get_status.return_value = {
        "error": "NO_ERROR",
        "data": {
            "battery": "NORMAL",
            "powerInput": "NOT_PRESENT",
            "powerInput5vIo": "NOT_PRESENT",
            "isFault": False,
        },
    }
    pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 75}
    pijuice.get_battery_voltage.return_value = {"error": "NO_ERROR", "data": 3700}
    pijuice.get_battery_current.return_value = {"error": "NO_ERROR", "data": -100}
    pijuice.get_battery_temperature.return_value = {"error": "NO_ERROR", "data": 25}
    
    return pijuice


class TestBatteryMonitor:
    """Test cases for BatteryMonitor class."""

    # === Basic Initialization Tests ===
    
    def test_init(self, mock_config: AppConfig) -> None:
        """Test BatteryMonitor initialization without PiJuice."""
        monitor = BatteryMonitor(mock_config)
        assert monitor.config == mock_config
        assert monitor.pijuice is None

    def test_init_with_pijuice(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test BatteryMonitor initialization with PiJuice."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        assert monitor.config == mock_config
        assert monitor.pijuice == mock_pijuice

    # === Battery Status Tests ===
    
    def test_get_battery_status_development_mode(self, mock_config: AppConfig) -> None:
        """Test battery status in development mode."""
        mock_config.development_mode = True
        monitor = BatteryMonitor(mock_config)
        
        status = monitor.get_battery_status()
        assert status.level == 75  # Default mock level
        assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_no_pijuice(self, mock_config: AppConfig) -> None:
        """Test battery status without PiJuice adapter."""
        monitor = BatteryMonitor(mock_config)
        
        status = monitor.get_battery_status()
        assert status.level == 0
        assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_no_adapter(self, mock_config: AppConfig) -> None:
        """Test battery status when PiJuice adapter is None."""
        # Create monitor with no adapter
        monitor = BatteryMonitor(mock_config, None)
        
        # Should return default battery status since it's not development mode
        status = monitor.get_battery_status()
        assert status.level == 0
        assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_with_pijuice(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test normal battery status reading."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        status = monitor.get_battery_status()
        assert status.level == 75
        assert status.voltage == 3.7
        assert status.current == -100.0
        assert status.temperature == 25.0
        assert status.state == BatteryState.DISCHARGING

    def test_get_battery_status_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "CHARGING_FROM_IN",
                "powerInput": "PRESENT",
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert status.state == BatteryState.CHARGING

    def test_get_battery_status_error(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when PiJuice returns error."""
        mock_pijuice.get_status.side_effect = Exception("PiJuice error")
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        with pytest.raises(PiJuiceCommunicationError) as exc_info:
            monitor.get_battery_status()
        
        assert "Failed to communicate with PiJuice" in str(exc_info.value)

    def test_get_battery_status_with_fault(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status with fault condition."""
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
        status = monitor.get_battery_status()
        
        assert hasattr(status, "_pijuice_fault")
        assert status._pijuice_fault is True  # type: ignore[attr-defined]

    def test_get_battery_status_fully_charged(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when fully charged (special case)."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "PRESENT",
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 98}
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        status = monitor.get_battery_status()
        
        assert status.state == BatteryState.CHARGING  # Special case for fully charged

    def test_get_battery_status_fully_charged_below_threshold(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status with power present but below full charge threshold."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "PRESENT",
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 90}
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        status = monitor.get_battery_status()
        
        assert status.state == BatteryState.DISCHARGING  # Not charging if below 95%

    def test_get_battery_status_power_present_not_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when power is present but not charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "NORMAL",
                "powerInput": "WEAK",
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        status = monitor.get_battery_status()
        
        # Should log but still return DISCHARGING state
        assert status.state == BatteryState.DISCHARGING

    def test_get_battery_status_invalid_response_types(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status with invalid response types."""
        # Test with string instead of numeric value
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": "75"}
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        status = monitor.get_battery_status()
        
        # Should handle string conversion
        assert status.level == 75

    # === Battery History Tests ===
    
    def test_battery_history_tracking(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery history tracking."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Get status multiple times
        for _ in range(3):
            monitor.get_battery_status()
        
        history = monitor.get_battery_history()
        assert len(history) == 3

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
        """Test that battery history only tracks positive charge levels."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Add positive charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 50}
        monitor.get_battery_status()
        
        # Try to add zero charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 0}
        monitor.get_battery_status()
        
        # Add another positive charge
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 45}
        monitor.get_battery_status()
        
        history = monitor.get_battery_history()
        # Should only have positive charge levels
        assert len(history) == 2
        assert all(status.level > 0 for status in history)

    def test_clear_battery_history(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test clearing battery history."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Add some history
        monitor.get_battery_status()
        assert len(monitor.get_battery_history()) > 0
        
        # Clear history
        monitor.clear_battery_history()
        assert len(monitor.get_battery_history()) == 0

    # === Drain Rate Tests ===
    
    def test_drain_rate_calculation(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test drain rate calculation with battery history."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Create history with decreasing charge levels
        with patch('rpi_weather_display.utils.battery_monitor.calculate_drain_rate') as mock_calc:
            mock_calc.return_value = 150.0  # mA drain rate
            
            # First status - no drain rate calculation yet
            monitor.get_battery_status()
            
            # Second status - should trigger drain rate calculation
            mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 70}
            monitor.get_battery_status()
            
            # Check that drain rate was updated
            assert monitor._current_drain_rate != 100.0  # Changed from default
            mock_calc.assert_called_once()

    # === Battery Life Calculation Tests ===
    
    def test_get_expected_battery_life_development_mode(
        self, mock_config: AppConfig
    ) -> None:
        """Test battery life in development mode."""
        mock_config.development_mode = True
        monitor = BatteryMonitor(mock_config)
        
        life = monitor.get_expected_battery_life()
        assert life == 24  # Fixed value in development mode

    def test_get_expected_battery_life_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life when charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {
                "battery": "CHARGING_FROM_IN",
                "powerInput": "PRESENT",
                "powerInput5vIo": "PRESENT",
                "isFault": False,
            },
        }
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        life = monitor.get_expected_battery_life()
        assert life is None  # No estimate while charging

    def test_get_expected_battery_life_with_drain_rate(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life calculation with known drain rate."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 100.0  # 100mA drain
        
        life = monitor.get_expected_battery_life()
        # 75% of 12000mAh = 9000mAh, at 100mA = 90 hours
        assert life == 90

    def test_get_expected_battery_life_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life calculation with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = BatteryMonitoringError("Test error", {"test": True})
            
            with pytest.raises(BatteryMonitoringError):
                monitor.get_expected_battery_life()

    def test_get_expected_battery_life_zero_drain(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life calculation with zero drain rate."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 0.0  # Zero drain
        
        life = monitor.get_expected_battery_life()
        assert life is None  # Cannot calculate with zero drain

    # === Discharge Rate Tests ===
    
    def test_is_discharge_rate_abnormal(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test abnormal discharge rate detection."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 2.5  # 2.5% per hour
        
        # Expected rate is 2%, abnormal is > 50% more = 3%
        assert monitor.is_discharge_rate_abnormal() is False
        
        monitor._current_drain_rate = 4.0  # 4% per hour, well above threshold
        assert monitor.is_discharge_rate_abnormal() is True

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
            mock_get_status.side_effect = BatteryMonitoringError("Test error", {"test": True})
            
            with pytest.raises(BatteryMonitoringError):
                monitor.is_discharge_rate_abnormal()

    # === Power Conservation Tests ===
    
    def test_should_conserve_power(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test power conservation detection."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # High battery - no conservation needed
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 50}
        assert monitor.should_conserve_power() is False
        
        # Low battery - conservation needed
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 15}
        assert monitor.should_conserve_power() is True

    def test_should_conserve_power_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test power conservation check with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = BatteryMonitoringError("Test error", {"test": True})
            
            with pytest.raises(BatteryMonitoringError):
                monitor.should_conserve_power()

    # === Critical Battery Tests ===
    
    def test_is_battery_critical(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test critical battery detection."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        # Above critical threshold
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 15}
        assert monitor.is_battery_critical() is False

        # Below critical threshold - should raise CriticalBatteryError
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 5}
        with pytest.raises(CriticalBatteryError) as exc_info:
            monitor.is_battery_critical()
        
        assert "critically low" in str(exc_info.value)
        assert exc_info.value.details["level"] == 5

    def test_is_battery_critical_exception(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test critical battery check with exception."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Make get_battery_status raise an exception
        with patch.object(monitor, 'get_battery_status') as mock_get_status:
            mock_get_status.side_effect = BatteryMonitoringError("Test error", {"test": True})
            
            with pytest.raises(BatteryMonitoringError):
                monitor.is_battery_critical()

    def test_is_battery_critical_raises_critical_error(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test critical battery check raises CriticalBatteryError when battery is critical."""
        # Set critical threshold
        mock_config.power.critical_battery_threshold = 10
        
        # Set battery level to critical (5%)
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 5}
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Should raise CriticalBatteryError
        with pytest.raises(CriticalBatteryError) as exc_info:
            monitor.is_battery_critical()
        
        assert "critically low" in str(exc_info.value)
        assert exc_info.value.details["level"] == 5
        assert exc_info.value.details["threshold"] == 10

    # === Diagnostic Info Tests ===
    
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
            mock_get_status.side_effect = BatteryMonitoringError("Test error", {"test": True})
            
            with pytest.raises(BatteryMonitoringError):
                monitor.get_diagnostic_info()

    # === Exception Handling Tests ===
    
    def test_pijuice_communication_error(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test PiJuice communication error handling."""
        # Make PiJuice calls raise exceptions
        mock_pijuice.get_status.side_effect = Exception("I2C communication error")
        
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # Should raise PiJuiceCommunicationError
        with pytest.raises(PiJuiceCommunicationError) as exc_info:
            monitor.get_battery_status()
        
        assert "Failed to communicate with PiJuice" in str(exc_info.value)
        assert exc_info.value.details["error"] == "I2C communication error"

    def test_pijuice_initialization_error(
        self, mock_config: AppConfig
    ) -> None:
        """Test PiJuice initialization error when adapter is None."""
        # Create monitor with no adapter
        monitor = BatteryMonitor(mock_config, None)
        
        # Manually call _get_pijuice_data to trigger initialization error
        with pytest.raises(PiJuiceInitializationError) as exc_info:
            monitor._get_pijuice_data()
        
        assert "PiJuice adapter is not available" in str(exc_info.value)
        assert exc_info.value.details["operation"] == "get_battery_data"
        assert exc_info.value.details["adapter_present"] is False