"""Tests for the BatteryMonitor module."""

from datetime import datetime
from unittest.mock import MagicMock

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


class TestBatteryMonitor:
    """Test cases for BatteryMonitor class."""

    def test_init(self, mock_config: AppConfig) -> None:
        """Test BatteryMonitor initialization."""
        monitor = BatteryMonitor(mock_config)
        assert monitor.config == mock_config
        assert monitor.pijuice is None
        assert len(monitor._battery_history) == 0

    def test_init_with_pijuice(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test BatteryMonitor initialization with PiJuice."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        assert monitor.pijuice == mock_pijuice

    def test_get_battery_status_development_mode(self, mock_config: AppConfig) -> None:
        """Test battery status in development mode."""
        mock_config.development_mode = True
        monitor = BatteryMonitor(mock_config)

        status = monitor.get_battery_status()
        assert isinstance(status, BatteryStatus)
        assert status.level == 75  # MOCK_BATTERY_LEVEL
        assert status.state == BatteryState.UNKNOWN
        assert status.voltage == 3.7
        assert status.current == 100.0  # MOCK_BATTERY_CURRENT
        assert status.temperature == 25.0

    def test_get_battery_status_no_pijuice(self, mock_config: AppConfig) -> None:
        """Test battery status when PiJuice is not available."""
        monitor = BatteryMonitor(mock_config)

        status = monitor.get_battery_status()
        assert isinstance(status, BatteryStatus)
        assert status.level == 0
        assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_with_pijuice(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status with PiJuice hardware."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        status = monitor.get_battery_status()
        assert isinstance(status, BatteryStatus)
        assert status.level == 75
        assert status.voltage == 3.7  # 3700 / 1000
        assert status.current == -100.0
        assert status.temperature == 25.0
        assert status.state == BatteryState.DISCHARGING

    def test_get_battery_status_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery status when charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {"battery": "CHARGING"},
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

        status = monitor.get_battery_status()
        assert status.level == 0
        assert status.state == BatteryState.UNKNOWN

    def test_battery_history_tracking(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery history tracking."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        # Get status multiple times to build history
        monitor.get_battery_status()
        monitor.get_battery_status()

        history = monitor.get_battery_history()
        assert len(history) == 2
        assert all(isinstance(item, BatteryStatus) for item in history)
        assert all(isinstance(item.timestamp, datetime) for item in history)
        assert all(isinstance(item.level, int) for item in history)

    def test_get_expected_battery_life_development_mode(self, mock_config: AppConfig) -> None:
        """Test battery life estimation in development mode."""
        mock_config.development_mode = True
        monitor = BatteryMonitor(mock_config)

        life = monitor.get_expected_battery_life()
        assert life == 24  # Fixed value in dev mode

    def test_get_expected_battery_life_charging(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life estimation when charging."""
        mock_pijuice.get_status.return_value = {
            "error": "NO_ERROR",
            "data": {"battery": "CHARGING"},
        }
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        life = monitor.get_expected_battery_life()
        assert life is None  # No estimation when charging

    def test_get_expected_battery_life_with_drain_rate(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test battery life estimation with drain rate."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        monitor._current_drain_rate = 100.0  # 100mA drain

        # Get status to populate level
        monitor.get_battery_status()

        life = monitor.get_expected_battery_life()
        assert isinstance(life, int)
        # 75% of 12000mAh = 9000mAh, 9000/100 = 90 hours
        assert life == 90

    def test_is_discharge_rate_abnormal(
        self, mock_config: AppConfig, mock_pijuice: MagicMock
    ) -> None:
        """Test abnormal discharge rate detection."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)
        
        # With default expected_rate=2.0 and factor=1.5, threshold is 3.0
        monitor._current_drain_rate = 100.0  # Well above threshold (3.0)
        assert monitor.is_discharge_rate_abnormal() is True

        monitor._current_drain_rate = 1.0  # Below threshold (3.0)
        assert monitor.is_discharge_rate_abnormal() is False

    def test_should_conserve_power(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test power conservation check."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        # High battery - no conservation needed
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 80}
        assert monitor.should_conserve_power() is False

        # Low battery - conservation needed
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 15}
        assert monitor.should_conserve_power() is True

    def test_is_battery_critical(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test critical battery detection."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        # Above critical threshold
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 15}
        assert monitor.is_battery_critical() is False

        # Below critical threshold
        mock_pijuice.get_charge_level.return_value = {"error": "NO_ERROR", "data": 5}
        assert monitor.is_battery_critical() is True

    def test_clear_battery_history(self, mock_config: AppConfig, mock_pijuice: MagicMock) -> None:
        """Test clearing battery history."""
        monitor = BatteryMonitor(mock_config, mock_pijuice)

        # Build some history
        monitor.get_battery_status()
        monitor.get_battery_status()
        assert len(monitor.get_battery_history()) > 0

        # Clear history
        monitor.clear_battery_history()
        assert len(monitor.get_battery_history()) == 0
        assert monitor._last_battery_update is None
