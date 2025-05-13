import logging
import subprocess
from datetime import datetime, timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any, TypedDict, cast

from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus

# Define absolute paths for executables to avoid partial path security issues
SUDO_PATH = "/usr/bin/sudo"
SHUTDOWN_PATH = "/sbin/shutdown"
TOP_PATH = "/usr/bin/top"
DF_PATH = "/bin/df"


# Type definitions for PiJuice API
class PiJuiceStatus(TypedDict):
    """Type definition for PiJuice status response."""

    error: str
    data: dict[str, Any]


class PiJuiceResponse(TypedDict):
    """Type definition for PiJuice API response."""

    error: str
    data: Any  # Using Any to allow for different data types


# Define a type for PiJuice class for type checking
class PiJuiceInterface:
    """Type stub for the PiJuice class."""

    def __init__(self, bus: int, address: int) -> None:
        """Initialize PiJuice interface.

        Args:
            bus: I2C bus number
            address: I2C address
        """
        pass

    class status:  # noqa: N801  # Name matches PiJuice API
        """PiJuice status interface."""

        @staticmethod
        def GetStatus() -> PiJuiceStatus:  # noqa: N802  # Name matches PiJuice API
            """Get PiJuice status."""
            return {"error": "NO_ERROR", "data": {}}

        @staticmethod
        def GetChargeLevel() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery charge level."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryVoltage() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery voltage."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryCurrent() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery current."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryTemperature() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery temperature."""
            return {"error": "NO_ERROR", "data": 0}

    class rtcAlarm:  # noqa: N801  # Name matches PiJuice API
        """PiJuice RTC alarm interface."""

        @staticmethod
        def SetAlarm(alarm_time: dict[str, int]) -> None:  # noqa: N802  # Name matches PiJuice API
            """Set RTC alarm.

            Args:
                alarm_time: Alarm time configuration
            """
            pass

        @staticmethod
        def SetWakeupEnabled(enabled: bool) -> None:  # noqa: N802  # Name matches PiJuice API
            """Enable or disable wakeup alarm.

            Args:
                enabled: Whether to enable wakeup
            """
            pass


class PowerManager:
    """Power management for the Raspberry Pi using PiJuice."""

    def __init__(self, config: PowerConfig) -> None:
        """Initialize the power manager.

        Args:
            config: Power management configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._pijuice: PiJuiceInterface | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the PiJuice interface.

        This is separated from __init__ so that PiJuice can be mocked for testing.
        """
        try:
            # Import PiJuice, which is only available on Raspberry Pi
            from pijuice import PiJuice  # type: ignore

            # Initialize PiJuice
            self._pijuice = cast(PiJuiceInterface, PiJuice(1, 0x14))
            status: PiJuiceStatus = self._pijuice.status.GetStatus()

            if status["error"] != "NO_ERROR":
                self.logger.error(f"Error initializing PiJuice: {status['error']}")
                self._initialized = False
            else:
                self._initialized = True
                self.logger.info("PiJuice initialized successfully")
        except ImportError:
            # When running on development machine, print message
            self.logger.warning("PiJuice library not available. Using mock PiJuice.")
            self._initialized = False
        except Exception as e:
            self.logger.error(f"Error initializing PiJuice: {e}")
            self._initialized = False

    def get_battery_status(self) -> BatteryStatus:
        """Get the current battery status.

        Returns:
            BatteryStatus object with current battery information.
        """
        if not self._initialized or not self._pijuice:
            # Return mock status when not on a Raspberry Pi
            return BatteryStatus(
                level=75,
                voltage=3.7,
                current=100.0,
                temperature=25.0,
                state=BatteryState.DISCHARGING,
                time_remaining=1200,  # 20 hours
            )

        try:
            # Get charge level
            charge: PiJuiceResponse = self._pijuice.status.GetChargeLevel()
            level: int = 0
            if charge["error"] == "NO_ERROR" and isinstance(charge["data"], int | float):
                level = int(charge["data"])

            # Get battery voltage
            voltage: PiJuiceResponse = self._pijuice.status.GetBatteryVoltage()
            volts: float = 0.0
            if voltage["error"] == "NO_ERROR" and isinstance(voltage["data"], int | float):
                volts = float(voltage["data"]) / 1000.0

            # Get battery current
            current: PiJuiceResponse = self._pijuice.status.GetBatteryCurrent()
            amps: float = 0.0
            if current["error"] == "NO_ERROR" and isinstance(current["data"], int | float):
                amps = float(current["data"]) / 1000.0

            # Get battery temperature
            temp: PiJuiceResponse = self._pijuice.status.GetBatteryTemperature()
            temperature: float = 0.0
            if temp["error"] == "NO_ERROR" and isinstance(temp["data"], int | float):
                temperature = float(temp["data"])

            # Get battery state
            status: PiJuiceStatus = self._pijuice.status.GetStatus()
            state = BatteryState.UNKNOWN
            if status["error"] == "NO_ERROR":
                battery_data = status["data"].get("battery")
                if battery_data:
                    battery_str = str(battery_data)
                    if "CHARGING" in battery_str:
                        state = BatteryState.CHARGING
                    elif "NORMAL" in battery_str:
                        state = BatteryState.DISCHARGING
                    elif "CHARGED" in battery_str:
                        state = BatteryState.FULL

            # Calculate time remaining (rough estimate)
            time_remaining = None
            if state == BatteryState.DISCHARGING and amps != 0:
                # Convert mAh to hours and multiply by 60 for minutes
                time_remaining = int((level / 100.0 * 12000) / abs(amps) * 60)

            return BatteryStatus(
                level=level,
                voltage=volts,
                current=amps * 1000,  # Convert to mA
                temperature=temperature,
                state=state,
                time_remaining=time_remaining,
            )
        except Exception as e:
            self.logger.error(f"Error getting battery status: {e}")
            return BatteryStatus(
                level=0, voltage=0.0, current=0.0, temperature=0.0, state=BatteryState.UNKNOWN
            )

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours.

        Returns:
            True if current time is within quiet hours, False otherwise.
        """
        # Parse quiet hours from config
        try:
            start_hour, start_minute = map(int, self.config.quiet_hours_start.split(":"))
            end_hour, end_minute = map(int, self.config.quiet_hours_end.split(":"))

            start_time = dt_time(start_hour, start_minute)
            end_time = dt_time(end_hour, end_minute)

            # Get current time
            now = datetime.now().time()

            # Check if current time is within quiet hours
            if start_time <= end_time:
                # Simple case: start time is before end time
                return start_time <= now <= end_time
            else:
                # Complex case: quiet hours span midnight
                return now >= start_time or now <= end_time
        except ValueError:
            # Break up long line
            self.logger.error(
                f"Invalid quiet hours format: {self.config.quiet_hours_start} - "
                f"{self.config.quiet_hours_end}"
            )
            return False

    def shutdown_system(self) -> None:
        """Shutdown the Raspberry Pi."""
        if not self._initialized:
            self.logger.info("Mock shutdown: System would shut down now")
            return

        self.logger.info("Shutting down system")
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = Path(SUDO_PATH)
            shutdown_path = Path(SHUTDOWN_PATH)

            if not sudo_path.exists() or not shutdown_path.exists():
                self.logger.warning("Commands not found for shutdown")
                return

            subprocess.run(  # nosec # noqa: S603, S607
                [str(sudo_path), str(shutdown_path), "-h", "now"],
                check=True,
                shell=False,  # Explicitly disable shell
            )
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to shut down: {e}")

    def schedule_wakeup(self, minutes: int) -> bool:
        """Schedule a wakeup using PiJuice.

        Args:
            minutes: Minutes from now to wake up.

        Returns:
            True if wakeup was scheduled successfully, False otherwise.
        """
        if not self._initialized or not self._pijuice:
            self.logger.info(f"Mock wakeup: Would schedule wakeup in {minutes} minutes")
            return True

        try:
            # Get current time
            current_time = datetime.now()

            # Calculate wake time
            wake_time = current_time.replace(microsecond=0) + timedelta(minutes=minutes)

            # Set alarm
            alarm_time: dict[str, int] = {
                "second": wake_time.second,
                "minute": wake_time.minute,
                "hour": wake_time.hour,
                "day": wake_time.day,
                "month": wake_time.month,
                "year": wake_time.year - 2000,  # PiJuice expects 2-digit year
                "weekday": 0,  # Not used
            }

            # Configure wakeup
            self._pijuice.rtcAlarm.SetAlarm(alarm_time)
            self._pijuice.rtcAlarm.SetWakeupEnabled(True)

            self.logger.info(f"Scheduled wakeup for {wake_time}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule wakeup: {e}")
            return False

    def get_system_metrics(self) -> dict[str, float]:
        """Get system metrics like CPU temperature and usage.

        Returns:
            Dictionary of system metrics.
        """
        metrics: dict[str, float] = {}

        try:
            # CPU temperature
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    temp = int(f.read().strip()) / 1000.0
                    metrics["cpu_temp"] = temp
            except (FileNotFoundError, ValueError):
                pass

            # CPU usage
            try:
                # SECURITY: Safe command with fixed arguments - reviewed for injection risk
                top_path = Path(TOP_PATH)
                if not top_path.exists():
                    self.logger.warning(f"Command not found: {TOP_PATH}")
                else:
                    cpu_usage = subprocess.check_output(  # nosec # noqa: S603, S607
                        [str(top_path), "-bn1"],
                        shell=False,  # Explicitly disable shell
                    ).decode()
                    for line in cpu_usage.split("\n"):
                        if "Cpu(s)" in line:
                            # Break up long line and make more readable
                            cpu_info = line.split(",")[0].split(":")[1].strip()
                            cpu_pct = float(cpu_info.replace("%id", "").strip())
                            metrics["cpu_usage"] = 100.0 - cpu_pct
                            break
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass

            # Memory usage
            try:
                with open("/proc/meminfo") as f:
                    meminfo = f.read()
                    total = int(meminfo.split("MemTotal:")[1].split("kB")[0].strip()) * 1024
                    free = int(meminfo.split("MemFree:")[1].split("kB")[0].strip()) * 1024
                    metrics["memory_usage"] = (total - free) / total * 100.0
            except (FileNotFoundError, ValueError, IndexError):
                pass

            # Disk usage
            try:
                # SECURITY: Safe command with fixed arguments - reviewed for injection risk
                df_path = Path(DF_PATH)
                if not df_path.exists():
                    self.logger.warning(f"Command not found: {DF_PATH}")
                else:
                    disk_usage = subprocess.check_output(  # nosec # noqa: S603, S607
                        [str(df_path), "-h", "/"],
                        shell=False,  # Explicitly disable shell
                    ).decode()
                    disk_usage = disk_usage.split("\n")[1]
                    disk_pct = int(disk_usage.split()[4].replace("%", ""))
                    metrics["disk_usage"] = float(disk_pct)
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")

        return metrics
