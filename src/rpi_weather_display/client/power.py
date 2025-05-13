import logging
import subprocess
import time
from datetime import datetime, time as dt_time
from typing import Dict, Optional, Tuple

from rpi_weather_display.models.config import PowerConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus, SystemStatus


class PowerManager:
    """Power management for the Raspberry Pi using PiJuice."""

    def __init__(self, config: PowerConfig):
        """Initialize the power manager.

        Args:
            config: Power management configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._pijuice = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the PiJuice interface.

        This is separated from __init__ so that PiJuice can be mocked for testing.
        """
        try:
            # Import PiJuice, which is only available on Raspberry Pi
            from pijuice import PiJuice

            # Initialize PiJuice
            self._pijuice = PiJuice(1, 0x14)
            status = self._pijuice.status.GetStatus()

            if status["error"] != "NO_ERROR":
                self.logger.error(f"Error initializing PiJuice: {status['error']}")
                self._initialized = False
            else:
                self._initialized = True

                # Apply power-saving settings
                self._apply_power_settings()
        except ImportError:
            # When running on development machine, print message
            self.logger.warning("PiJuice library not available. Using mock PiJuice.")
            self._initialized = False
        except Exception as e:
            self.logger.error(f"Error initializing PiJuice: {e}")
            self._initialized = False

    def _apply_power_settings(self) -> None:
        """Apply power-saving settings."""
        # Disable HDMI
        if self.config.disable_hdmi:
            try:
                subprocess.run(["/usr/bin/tvservice", "-o"], check=True)
                self.logger.info("HDMI disabled")
            except subprocess.SubprocessError as e:
                self.logger.error(f"Failed to disable HDMI: {e}")

        # Disable Bluetooth
        if self.config.disable_bluetooth:
            try:
                subprocess.run(["rfkill", "block", "bluetooth"], check=True)
                self.logger.info("Bluetooth disabled")
            except subprocess.SubprocessError as e:
                self.logger.error(f"Failed to disable Bluetooth: {e}")

        # Disable LEDs
        if self.config.disable_leds:
            try:
                # Disable the ACT LED
                with open("/sys/class/leds/led0/brightness", "w") as f:
                    f.write("0")

                # Disable the PWR LED if available
                try:
                    with open("/sys/class/leds/led1/brightness", "w") as f:
                        f.write("0")
                except FileNotFoundError:
                    pass

                self.logger.info("LEDs disabled")
            except Exception as e:
                self.logger.error(f"Failed to disable LEDs: {e}")

        # Set CPU governor and frequency
        try:
            # Set CPU governor to powersave
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "w") as f:
                f.write(self.config.cpu_governor)

            # Set maximum CPU frequency
            max_freq = self.config.cpu_max_freq_mhz * 1000
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "w") as f:
                f.write(str(max_freq))

            self.logger.info(f"CPU set to {self.config.cpu_governor} with max frequency {self.config.cpu_max_freq_mhz} MHz")
        except Exception as e:
            self.logger.error(f"Failed to set CPU parameters: {e}")

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
                time_remaining=1200  # 20 hours
            )

        try:
            # Get charge level
            charge = self._pijuice.status.GetChargeLevel()
            level = charge["data"] if charge["error"] == "NO_ERROR" else 0

            # Get battery voltage
            voltage = self._pijuice.status.GetBatteryVoltage()
            volts = voltage["data"] / 1000.0 if voltage["error"] == "NO_ERROR" else 0

            # Get battery current
            current = self._pijuice.status.GetBatteryCurrent()
            amps = current["data"] / 1000.0 if current["error"] == "NO_ERROR" else 0

            # Get battery temperature
            temp = self._pijuice.status.GetBatteryTemperature()
            temperature = temp["data"] if temp["error"] == "NO_ERROR" else 0

            # Get battery state
            status = self._pijuice.status.GetStatus()
            if status["error"] == "NO_ERROR":
                if status["data"]["battery"]:
                    if "CHARGING" in status["data"]["battery"]:
                        state = BatteryState.CHARGING
                    elif "NORMAL" in status["data"]["battery"]:
                        state = BatteryState.DISCHARGING
                    elif "CHARGED" in status["data"]["battery"]:
                        state = BatteryState.FULL
                    else:
                        state = BatteryState.UNKNOWN
                else:
                    state = BatteryState.UNKNOWN
            else:
                state = BatteryState.UNKNOWN

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
                time_remaining=time_remaining
            )
        except Exception as e:
            self.logger.error(f"Error getting battery status: {e}")
            return BatteryStatus(
                level=0,
                voltage=0.0,
                current=0.0,
                temperature=0.0,
                state=BatteryState.UNKNOWN
            )

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours.

        Returns:
            True if current time is within quiet hours, False otherwise.
        """
        # Parse quiet hours from config
        try:
            start_hour, start_minute = map(int, self.config.quiet_hours_start.split(':'))
            end_hour, end_minute = map(int, self.config.quiet_hours_end.split(':'))

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
            self.logger.error(f"Invalid quiet hours format: {self.config.quiet_hours_start} - {self.config.quiet_hours_end}")
            return False

    def shutdown_system(self) -> None:
        """Shutdown the Raspberry Pi."""
        if not self._initialized:
            self.logger.info("Mock shutdown: System would shut down now")
            return

        self.logger.info("Shutting down system")
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
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
            wake_time = current_time.replace(microsecond=0) + \
                        datetime.timedelta(minutes=minutes)

            # Set alarm
            alarm_time = {
                "second": wake_time.second,
                "minute": wake_time.minute,
                "hour": wake_time.hour,
                "day": wake_time.day,
                "month": wake_time.month,
                "year": wake_time.year - 2000,  # PiJuice expects 2-digit year
                "weekday": 0  # Not used
            }

            # Configure wakeup
            self._pijuice.rtcAlarm.SetAlarm(alarm_time)
            self._pijuice.rtcAlarm.SetWakeupEnabled(True)

            self.logger.info(f"Scheduled wakeup for {wake_time}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule wakeup: {e}")
            return False

    def get_system_metrics(self) -> Dict[str, float]:
        """Get system metrics like CPU temperature and usage.

        Returns:
            Dictionary of system metrics.
        """
        metrics = {}

        try:
            # CPU temperature
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read().strip()) / 1000.0
                    metrics["cpu_temp"] = temp
            except (FileNotFoundError, ValueError):
                pass

            # CPU usage
            try:
                cpu_usage = subprocess.check_output(["top", "-bn1"]).decode()
                for line in cpu_usage.split("\n"):
                    if "Cpu(s)" in line:
                        cpu_pct = float(line.split(",")[0].split(":")[1].strip().replace("%id", "").strip())
                        metrics["cpu_usage"] = 100.0 - cpu_pct
                        break
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass

            # Memory usage
            try:
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                    total = int(meminfo.split("MemTotal:")[1].split("kB")[0].strip()) * 1024
                    free = int(meminfo.split("MemFree:")[1].split("kB")[0].strip()) * 1024
                    metrics["memory_usage"] = (total - free) / total * 100.0
            except (FileNotFoundError, ValueError, IndexError):
                pass

            # Disk usage
            try:
                disk_usage = subprocess.check_output(["df", "-h", "/"]).decode()
                disk_usage = disk_usage.split("\n")[1]
                disk_pct = int(disk_usage.split()[4].replace("%", ""))
                metrics["disk_usage"] = disk_pct
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")

        return metrics