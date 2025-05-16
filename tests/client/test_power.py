"""Tests for the power management module."""
# ruff: noqa: S101, A002, PLR2004, SLF001
# ^ Ignores "Use of assert detected" in test files
# pyright: reportPrivateUsage=false
# ^ Allows tests to access protected members

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from rpi_weather_display.client.power import PowerManager
from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState


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
def mock_pijuice() -> MagicMock:
    """Create a mock PiJuice instance."""
    mock = MagicMock()

    # Mock status methods
    mock.status = MagicMock()
    mock.status.GetStatus = MagicMock(
        return_value={"error": "NO_ERROR", "data": {"battery": "CHARGING"}}
    )
    mock.status.GetChargeLevel = MagicMock(return_value={"error": "NO_ERROR", "data": 75})
    mock.status.GetBatteryVoltage = MagicMock(return_value={"error": "NO_ERROR", "data": 3700})
    mock.status.GetBatteryCurrent = MagicMock(return_value={"error": "NO_ERROR", "data": 100})
    mock.status.GetBatteryTemperature = MagicMock(return_value={"error": "NO_ERROR", "data": 25})

    # Mock RTC alarm methods
    mock.rtcAlarm = MagicMock()
    mock.rtcAlarm.SetAlarm = MagicMock()
    mock.rtcAlarm.SetWakeupEnabled = MagicMock()

    return mock


@pytest.fixture()
def power_manager(power_config: PowerConfig) -> PowerManager:
    """Create a PowerManager instance with mock PiJuice."""
    return PowerManager(power_config)


class TestPowerManager:
    """Test suite for the PowerManager class."""

    def test_init(self, power_config: PowerConfig) -> None:
        """Test PowerManager initialization."""
        manager = PowerManager(power_config)
        assert manager.config == power_config
        assert manager._pijuice is None
        assert not manager._initialized

    def test_initialize_success(self, power_manager: PowerManager) -> None:
        """Test successful initialization of PiJuice."""
        # Mock PiJuice class and status
        mock_pijuice = MagicMock()
        mock_pijuice.status.GetStatus.return_value = {"error": "NO_ERROR", "data": {}}

        # Need to patch at module level where it's imported, not where it's used
        with (
            patch.dict("sys.modules", {"pijuice": MagicMock()}),
            patch("pijuice.PiJuice", return_value=mock_pijuice),
        ):
            # Initialize
            power_manager.initialize()

            # Verify
            assert power_manager._initialized is True
            assert power_manager._pijuice is not None

    def test_initialize_error(self, power_manager: PowerManager) -> None:
        """Test initialization with PiJuice error."""
        # Mock PiJuice with error
        mock_pijuice = MagicMock()
        mock_pijuice.status.GetStatus.return_value = {"error": "SOME_ERROR", "data": {}}

        # Patch the import and PiJuice class
        with patch(
            "rpi_weather_display.client.power.PiJuice", return_value=mock_pijuice, create=True
        ):
            # Initialize
            power_manager.initialize()

            # Verify initialization failed
            assert power_manager._initialized is False

    def test_initialize_import_error(self, power_manager: PowerManager) -> None:
        """Test initialization with ImportError (development environment)."""
        # Patch the import to raise ImportError
        with patch(
            "rpi_weather_display.client.power.PiJuice", side_effect=ImportError(), create=True
        ):
            # Initialize should handle ImportError gracefully
            power_manager.initialize()

            # Verify
            assert power_manager._initialized is False

    def test_initialize_exception(self, power_manager: PowerManager) -> None:
        """Test initialization with generic exception."""
        # Patch the import to raise a generic exception
        with patch(
            "rpi_weather_display.client.power.PiJuice",
            side_effect=Exception("Unknown error"),
            create=True,
        ):
            # Initialize should handle Exception gracefully
            power_manager.initialize()

            # Verify
            assert power_manager._initialized is False

    def test_get_battery_status_mock(self, power_manager: PowerManager) -> None:
        """Test get_battery_status when not initialized (mock mode)."""
        # When not initialized, should return mock values
        status = power_manager.get_battery_status()

        assert status.level == 75
        assert status.voltage == 3.7
        assert status.current == 100.0
        assert status.temperature == 25.0
        assert status.state == BatteryState.DISCHARGING
        assert status.time_remaining == 1200

    def test_get_battery_status_initialized(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test get_battery_status with initialized PiJuice."""
        # Set up PiJuice mock
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Configure mock responses
        mock_pijuice.status.GetStatus.return_value = {
            "error": "NO_ERROR",
            "data": {"battery": "NORMAL"},
        }
        mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 50}
        mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 3800}
        mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": -200}
        mock_pijuice.status.GetBatteryTemperature.return_value = {"error": "NO_ERROR", "data": 30}

        # Get battery status
        status = power_manager.get_battery_status()

        # Verify
        assert status.level == 50
        assert status.voltage == 3.8
        assert status.current == -200.0
        assert status.temperature == 30.0
        assert status.state == BatteryState.DISCHARGING
        # Verify time_remaining calculation: (level / 100 * 12000) / abs(amps) * 60 minutes
        assert status.time_remaining == int((50 / 100 * 12000) / 0.2 * 60)

    def test_get_battery_status_charging(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test get_battery_status with charging battery."""
        # Set up PiJuice mock
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Configure mock for charging state
        mock_pijuice.status.GetStatus.return_value = {
            "error": "NO_ERROR",
            "data": {"battery": "CHARGING"},
        }
        mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 60}
        mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "NO_ERROR", "data": 4200}
        mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "NO_ERROR", "data": 500}
        mock_pijuice.status.GetBatteryTemperature.return_value = {"error": "NO_ERROR", "data": 35}

        # Get battery status
        status = power_manager.get_battery_status()

        # Verify
        assert status.level == 60
        assert status.voltage == 4.2
        assert status.current == 500.0
        assert status.temperature == 35.0
        assert status.state == BatteryState.CHARGING
        # No time_remaining when charging
        assert status.time_remaining is None

    def test_get_battery_status_full(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test get_battery_status with full battery."""
        # Set up PiJuice mock
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Configure mock for full state
        mock_pijuice.status.GetStatus.return_value = {
            "error": "NO_ERROR",
            "data": {"battery": "CHARGED"},
        }
        mock_pijuice.status.GetChargeLevel.return_value = {"error": "NO_ERROR", "data": 100}

        # Get battery status
        status = power_manager.get_battery_status()

        # Verify
        assert status.state == BatteryState.FULL

    def test_get_battery_status_error(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test get_battery_status with PiJuice errors."""
        # Set up PiJuice mock
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Configure mock to return errors
        mock_pijuice.status.GetStatus.return_value = {"error": "ERROR", "data": {}}
        mock_pijuice.status.GetChargeLevel.return_value = {"error": "ERROR", "data": 0}
        mock_pijuice.status.GetBatteryVoltage.return_value = {"error": "ERROR", "data": 0}
        mock_pijuice.status.GetBatteryCurrent.return_value = {"error": "ERROR", "data": 0}
        mock_pijuice.status.GetBatteryTemperature.return_value = {"error": "ERROR", "data": 0}

        # Get battery status
        status = power_manager.get_battery_status()

        # Verify we get zeros and unknown state
        assert status.level == 0
        assert status.voltage == 0.0
        assert status.current == 0.0
        assert status.temperature == 0.0
        assert status.state == BatteryState.UNKNOWN

    def test_get_battery_status_exception(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test get_battery_status with exception."""
        # Set up PiJuice mock
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Make GetStatus raise an exception
        mock_pijuice.status.GetStatus.side_effect = Exception("Test exception")

        # Get battery status
        status = power_manager.get_battery_status()

        # Verify we get zeros and unknown state
        assert status.level == 0
        assert status.voltage == 0.0
        assert status.current == 0.0
        assert status.temperature == 0.0
        assert status.state == BatteryState.UNKNOWN

    def test_shutdown_system_mock(self, power_manager: PowerManager) -> None:
        """Test shutdown_system in mock mode."""
        # Should not attempt actual shutdown when not initialized
        power_manager.shutdown_system()
        # No assertions needed, just verifying it doesn't raise exceptions

    @patch("subprocess.run")
    def test_shutdown_system_initialized(
        self, mock_subprocess: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test shutdown_system when initialized."""
        # Set initialized
        power_manager._initialized = True

        # Mock Path.exists to return True
        with patch.object(Path, "exists", return_value=True):
            # Call shutdown
            power_manager.shutdown_system()

            # Verify subprocess.run was called with correct arguments
            mock_subprocess.assert_called_once_with(
                ["/usr/bin/sudo", "/sbin/shutdown", "-h", "now"],
                check=True,
                shell=False,
            )

    @patch("subprocess.run")
    def test_shutdown_system_command_not_found(
        self, mock_subprocess: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test shutdown_system when commands are not found."""
        # Set initialized
        power_manager._initialized = True

        # Mock Path.exists to return False (commands not found)
        with patch.object(Path, "exists", return_value=False):
            # Call shutdown
            power_manager.shutdown_system()

            # Verify subprocess.run was not called
            mock_subprocess.assert_not_called()

    @patch("subprocess.run", side_effect=subprocess.SubprocessError("Command failed"))
    def test_shutdown_system_error(
        self, mock_subprocess: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test shutdown_system with subprocess error."""
        # Set initialized
        power_manager._initialized = True

        # Mock Path.exists to return True
        with patch.object(Path, "exists", return_value=True):
            # Call shutdown
            power_manager.shutdown_system()

            # Verify subprocess.run was called
            mock_subprocess.assert_called_once()
            # No assertion on result needed - just verifying it handles the error gracefully

    def test_schedule_wakeup_mock(self, power_manager: PowerManager) -> None:
        """Test schedule_wakeup in mock mode."""
        # Should return True for mock wakeup
        result = power_manager.schedule_wakeup(30)
        assert result is True

    def test_schedule_wakeup_initialized(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test schedule_wakeup when initialized."""
        # Set initialized with mock PiJuice
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Call with 30 minutes
        with freeze_time("2023-01-01 12:00:00"):  # Freeze time to test calculation
            result = power_manager.schedule_wakeup(30)

        # Verify
        assert result is True

        # Verify SetAlarm was called with correct time (30 minutes from now)
        mock_pijuice.rtcAlarm.SetAlarm.assert_called_once()
        alarm_time = mock_pijuice.rtcAlarm.SetAlarm.call_args[0][0]
        assert alarm_time["second"] == 0
        assert alarm_time["minute"] == 30
        assert alarm_time["hour"] == 12
        assert alarm_time["day"] == 1
        assert alarm_time["month"] == 1
        assert alarm_time["year"] == 23  # 2023 - 2000 = 23

        # Verify wakeup was enabled
        mock_pijuice.rtcAlarm.SetWakeupEnabled.assert_called_once_with(True)

    def test_schedule_wakeup_error(
        self, power_manager: PowerManager, mock_pijuice: MagicMock
    ) -> None:
        """Test schedule_wakeup with error."""
        # Set initialized with mock PiJuice
        power_manager._pijuice = mock_pijuice
        power_manager._initialized = True

        # Make SetAlarm raise an exception
        mock_pijuice.rtcAlarm.SetAlarm.side_effect = Exception("Test exception")

        # Call schedule_wakeup
        result = power_manager.schedule_wakeup(30)

        # Verify
        assert result is False

    @patch("rpi_weather_display.client.power.Path.exists", return_value=True)
    def test_get_system_metrics(
        self, mock_path_exists: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test get_system_metrics."""
        # We need to mock multiple file opens and command outputs

        # Mock for CPU temperature file
        mock_temp_file = MagicMock()
        mock_temp_file.__enter__.return_value.read.return_value = "45000\n"

        # Mock for memory info file
        mock_meminfo_file = MagicMock()
        mock_meminfo_file.__enter__.return_value.read.return_value = (
            "MemTotal:        8000000 kB\nMemFree:         4000000 kB\n"
        )

        # Set up the open mock to return different file handles for different paths
        with patch("builtins.open") as mock_open:
            mock_open.side_effect = [mock_temp_file, mock_meminfo_file]

            # Mock the subprocess calls for CPU usage and disk usage
            with patch("subprocess.check_output") as mock_check_output:
                # Set up the mock to return different outputs for different commands
                # Note: The cpu usage parsing in power.py expects:
                # 1. A line with "Cpu(s)" in it
                # 2. This line to be split by "," and then by ":" to get the idle percentage
                # 3. Specifically, it uses split(",")[0].split(":")[1].strip() to get "80.0 %id"
                # 4. Then it replaces "%id" with "" and converts to float
                mock_check_output.side_effect = [
                    # top command output with CPU idle at 80%
                    b"top - 12:00:00 up 1 day, 2:03, 1 user, load average: 0.52, 0.58, 0.59\n"
                    b"Tasks: 100 total,   1 running,  99 sleeping,   0 stopped,   0 zombie\n"
                    b"%Cpu(s): 80.0 %id, 10.0 us, 5.0 sy, 0.0 ni, 5.0 wa, 0.0 hi, 0.0 si, 0.0 st",
                    # df command output with disk usage at 36%
                    b"Filesystem      Size  Used Avail Use% Mounted on\n"
                    b"/dev/root        29G   10G   18G  36% /",
                ]

                # Call get_system_metrics
                metrics = power_manager.get_system_metrics()

                # Verify all expected metrics are present
                assert "cpu_temp" in metrics
                assert metrics["cpu_temp"] == 45.0
                assert "cpu_usage" in metrics
                assert metrics["cpu_usage"] == 20.0  # 100 - 80 (idle)
                assert "memory_usage" in metrics
                assert metrics["memory_usage"] == 50.0  # (8000000 - 4000000) / 8000000 * 100
                assert "disk_usage" in metrics
                assert metrics["disk_usage"] == 36.0

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_system_metrics_file_not_found(
        self, mock_open: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test get_system_metrics with FileNotFoundError."""
        # Call get_system_metrics
        metrics = power_manager.get_system_metrics()

        # Verify we get an empty dict but no exceptions
        assert isinstance(metrics, dict)
        assert len(metrics) == 0

    @patch("rpi_weather_display.client.power.Path.exists", return_value=False)
    def test_get_system_metrics_command_not_found(
        self, mock_exists: MagicMock, power_manager: PowerManager
    ) -> None:
        """Test get_system_metrics when commands are not found."""
        # Call get_system_metrics
        metrics = power_manager.get_system_metrics()

        # Verify we get an empty dict but no exceptions
        assert isinstance(metrics, dict)
        assert len(metrics) == 0
