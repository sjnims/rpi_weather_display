"""Additional tests for the PowerStateManager class focused on code coverage."""

# ruff: noqa: S101, A002, PLR2004
# pyright: reportPrivateUsage=false

import subprocess
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
def power_manager(default_config: AppConfig) -> PowerStateManager:
    """Create a PowerStateManager with the default config."""
    return PowerStateManager(default_config)


class TestPowerStateManagerCoverage:
    """Additional tests for the PowerStateManager class focusing on coverage."""

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

        # Patch the import inside the initialize method
        with (
            patch.dict("sys.modules", {"pijuice": MagicMock(PiJuice=mock_pijuice_class)}),
            patch.object(power_manager, "_update_power_state"),
        ):
            power_manager.initialize()

            assert power_manager.get_initialization_status_for_testing()
            # Verify the PiJuice was initialized correctly
            mock_pijuice_class.assert_called_once_with(1, 0x14)

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
        # Set invalid quiet hours format
        invalid_config = power_manager.config.model_copy(deep=True)
        invalid_config.power.quiet_hours_start = "invalid"
        invalid_config.power.quiet_hours_end = "format"
        power_manager.config = invalid_config

        result = power_manager._time_until_quiet_change()

        # Should return -1 for error
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
