"""System metrics collector for the Raspberry Pi weather display.

Collects and reports system metrics such as CPU usage, memory usage,
disk space, and temperature.
"""

import logging
import subprocess  # nosec B404 - subprocess usage has been security reviewed

from rpi_weather_display.constants import BYTES_PER_KILOBYTE
from rpi_weather_display.utils.file_utils import file_exists, read_text

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Collects system performance and health metrics."""

    def __init__(self) -> None:
        """Initialize system metrics collector."""
        self._cpu_temp_path = "/sys/class/thermal/thermal_zone0/temp"
        self._meminfo_path = "/proc/meminfo"
        self._loadavg_path = "/proc/loadavg"

    def get_system_metrics(self) -> dict[str, float]:
        """Get comprehensive system metrics.

        Returns:
            Dictionary containing system metrics:
            - cpu_usage: CPU usage percentage
            - memory_used_mb: Memory usage in MB
            - memory_percent: Memory usage percentage
            - disk_used_gb: Disk usage in GB
            - disk_percent: Disk usage percentage
            - temperature_c: CPU temperature in Celsius
            - load_average: 1-minute load average
        """
        metrics: dict[str, float] = {}

        # Get CPU usage
        cpu_usage = self._get_cpu_usage()
        if cpu_usage is not None:
            metrics["cpu_usage"] = cpu_usage

        # Get memory usage
        memory_info = self._get_memory_info()
        if memory_info:
            metrics.update(memory_info)

        # Get disk usage
        disk_info = self._get_disk_usage()
        if disk_info:
            metrics.update(disk_info)

        # Get temperature
        temp = self._get_cpu_temperature()
        if temp is not None:
            metrics["temperature_c"] = temp

        # Get load average
        load_avg = self._get_load_average()
        if load_avg is not None:
            metrics["load_average"] = load_avg

        logger.debug("System metrics collected", extra={"metrics": metrics})
        return metrics

    def _get_cpu_usage(self) -> float | None:
        """Get current CPU usage percentage.

        Returns:
            CPU usage percentage or None if unavailable
        """
        try:
            # Use top command in batch mode
            # Security: Using hardcoded paths and arguments to prevent injection
            result = subprocess.run(  # nosec B603 - hardcoded command with no user input  # noqa: S603
                ["/usr/bin/top", "-bn1"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,  # We handle errors ourselves
            )

            if result.returncode == 0:
                # Parse CPU usage from top output
                for line in result.stdout.split("\n"):
                    if line.startswith("%Cpu"):
                        # Extract idle percentage
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "id" in part and i > 0:
                                idle = float(parts[i - 1].replace(",", ""))
                                return 100.0 - idle
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")

        return None

    def _get_memory_info(self) -> dict[str, float]:
        """Get memory usage information.

        Returns:
            Dictionary with memory_used_mb and memory_percent
        """
        try:
            if file_exists(self._meminfo_path):
                content = read_text(self._meminfo_path)

                # Parse memory values
                mem_total = 0
                mem_available = 0

                for line in content.split("\n"):
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])  # in kB
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])  # in kB

                if mem_total > 0:
                    mem_used_kb = mem_total - mem_available
                    mem_used_mb = mem_used_kb / BYTES_PER_KILOBYTE
                    mem_percent = (mem_used_kb / mem_total) * 100

                    return {
                        "memory_used_mb": round(mem_used_mb, 1),
                        "memory_percent": round(mem_percent, 1),
                    }
        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")

        return {}

    def _get_disk_usage(self) -> dict[str, float]:
        """Get disk usage information for root filesystem.

        Returns:
            Dictionary with disk_used_gb and disk_percent
        """
        try:
            # Use df command for disk usage
            # Security: Using hardcoded paths and arguments to prevent injection
            result = subprocess.run(  # nosec B603 - hardcoded command with no user input  # noqa: S603
                ["/bin/df", "-h", "/"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,  # We handle errors ourselves
            )

            if result.returncode == 0:
                # Parse df output (second line has the data)
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        # Extract used space and percentage
                        used = parts[2]  # e.g., "5.2G"
                        percent = parts[4].rstrip("%")  # e.g., "54%"

                        # Convert used to GB
                        used_gb = self._parse_size_to_gb(used)

                        return {
                            "disk_used_gb": round(used_gb, 1),
                            "disk_percent": float(percent),
                        }
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")

        return {}

    def _get_cpu_temperature(self) -> float | None:
        """Get CPU temperature in Celsius.

        Returns:
            Temperature in Celsius or None if unavailable
        """
        try:
            if file_exists(self._cpu_temp_path):
                content = read_text(self._cpu_temp_path).strip()
                # Temperature is in millidegrees
                temp_milli = int(content)
                return temp_milli / 1000.0
        except Exception as e:
            logger.error(f"Failed to get CPU temperature: {e}")

        return None

    def _get_load_average(self) -> float | None:
        """Get 1-minute load average.

        Returns:
            1-minute load average or None if unavailable
        """
        try:
            if file_exists(self._loadavg_path):
                content = read_text(self._loadavg_path).strip()
                # First value is 1-minute average
                load_1min = float(content.split()[0])
                return load_1min
        except Exception as e:
            logger.error(f"Failed to get load average: {e}")

        return None

    def _parse_size_to_gb(self, size_str: str) -> float:
        """Parse size string (e.g., "5.2G", "512M") to GB.

        Args:
            size_str: Size string with unit suffix

        Returns:
            Size in GB
        """
        try:
            # Extract number and unit
            size_str = size_str.upper()
            if size_str.endswith("G"):
                return float(size_str[:-1])
            elif size_str.endswith("M"):
                return float(size_str[:-1]) / 1024
            elif size_str.endswith("K"):
                return float(size_str[:-1]) / (1024 * 1024)
            else:
                # Assume bytes
                return float(size_str) / (1024 * 1024 * 1024)
        except Exception:
            return 0.0

    def get_metrics_summary(self) -> str:
        """Get a human-readable summary of system metrics.

        Returns:
            Formatted string with key metrics
        """
        metrics = self.get_system_metrics()

        summary_parts: list[str] = []

        if "cpu_usage" in metrics:
            summary_parts.append(f"CPU: {metrics['cpu_usage']:.1f}%")

        if "memory_percent" in metrics:
            summary_parts.append(f"Memory: {metrics['memory_percent']:.1f}%")

        if "disk_percent" in metrics:
            summary_parts.append(f"Disk: {metrics['disk_percent']:.1f}%")

        if "temperature_c" in metrics:
            summary_parts.append(f"Temp: {metrics['temperature_c']:.1f}°C")

        return " | ".join(summary_parts) if summary_parts else "No metrics available"
