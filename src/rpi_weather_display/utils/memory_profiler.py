"""Memory profiling and monitoring utilities.

Provides tools for tracking memory usage across the application,
helping identify memory leaks and optimize resource usage.
"""

import logging
import os
import time
from dataclasses import dataclass

from typing_extensions import TypedDict

from rpi_weather_display.constants import BYTES_PER_MEGABYTE
from rpi_weather_display.utils.error_utils import get_error_location

# Dynamic import to avoid dependency on development machines
try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # type: ignore


class CurrentMemoryDict(TypedDict):
    """Current memory statistics."""

    rss_mb: float
    vms_mb: float
    percent: float
    available_system_mb: float


class BaselineDeltaDict(TypedDict):
    """Memory change since baseline."""

    rss_change_mb: float
    percent_change: float
    duration_seconds: float


class HistoryDict(TypedDict):
    """Memory history statistics."""

    samples: int
    average_rss_mb: float
    peak_rss_mb: float
    min_rss_mb: float


class MemoryReportDict(TypedDict, total=False):
    """Complete memory report structure."""

    current: CurrentMemoryDict
    timestamp: float
    error: str
    baseline_delta: BaselineDeltaDict
    history: HistoryDict
    warning: str


@dataclass
class MemoryStats:
    """Container for memory statistics.

    Attributes:
        rss_mb: Resident Set Size in megabytes (physical memory)
        vms_mb: Virtual Memory Size in megabytes
        percent: Percentage of total system memory used
        available_mb: Available system memory in megabytes
        timestamp: Time when stats were collected
    """

    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float
    timestamp: float


class MemoryProfiler:
    """Memory profiler for tracking application memory usage.

    Tracks memory usage over time and provides utilities for
    detecting memory leaks and optimizing resource usage.

    Attributes:
        logger: Logger instance
        _baseline: Baseline memory usage for comparison
        _history: List of memory snapshots over time
        _max_history: Maximum number of snapshots to keep
    """

    def __init__(self, max_history: int = 100) -> None:
        """Initialize the memory profiler.

        Args:
            max_history: Maximum number of memory snapshots to keep
        """
        self.logger = logging.getLogger(__name__)
        self._baseline: MemoryStats | None = None
        self._history: list[MemoryStats] = []
        self._max_history = max_history

    def get_memory_stats(self) -> MemoryStats | None:
        """Get current memory statistics.

        Returns:
            Current memory stats or None if psutil is not available
        """
        if psutil is None:
            return None

        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Get system memory info
            virtual_memory = psutil.virtual_memory()

            return MemoryStats(
                rss_mb=memory_info.rss / BYTES_PER_MEGABYTE,
                vms_mb=memory_info.vms / BYTES_PER_MEGABYTE,
                percent=memory_percent,
                available_mb=virtual_memory.available / BYTES_PER_MEGABYTE,
                timestamp=time.time(),
            )
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error getting memory stats [{error_location}]: {e}")
            return None

    def set_baseline(self) -> None:
        """Set the current memory usage as baseline for comparison."""
        self._baseline = self.get_memory_stats()
        if self._baseline:
            self.logger.info(
                f"Memory baseline set: {self._baseline.rss_mb:.1f}MB RSS, "
                f"{self._baseline.percent:.1f}% of system"
            )

    def record_snapshot(self) -> MemoryStats | None:
        """Record a memory snapshot and add to history.

        Returns:
            The recorded memory stats or None if unavailable
        """
        stats = self.get_memory_stats()
        if stats:
            self._history.append(stats)

            # Trim history if needed
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

        return stats

    def get_memory_delta(self) -> tuple[float, float] | None:
        """Get memory change since baseline.

        Returns:
            Tuple of (RSS delta in MB, percent change) or None
        """
        if not self._baseline:
            return None

        current = self.get_memory_stats()
        if not current:
            return None

        rss_delta = current.rss_mb - self._baseline.rss_mb
        percent_change = (
            (current.rss_mb - self._baseline.rss_mb) / self._baseline.rss_mb * 100
            if self._baseline.rss_mb > 0
            else 0
        )

        return (rss_delta, percent_change)

    def check_memory_growth(self, threshold_mb: float = 50.0) -> bool:
        """Check if memory has grown beyond threshold.

        Args:
            threshold_mb: Memory growth threshold in megabytes

        Returns:
            True if memory growth exceeds threshold
        """
        delta = self.get_memory_delta()
        if not delta:
            return False

        rss_delta, _ = delta
        if rss_delta > threshold_mb:
            self.logger.warning(
                f"Memory growth detected: {rss_delta:.1f}MB increase since baseline"
            )
            return True

        return False

    def get_report(self) -> MemoryReportDict:
        """Generate a memory usage report.

        Returns:
            Dictionary containing memory statistics and analysis
        """
        current = self.get_memory_stats()
        if not current:
            return {"error": "Memory profiling not available (psutil not installed)"}

        report: MemoryReportDict = {
            "current": {
                "rss_mb": current.rss_mb,
                "vms_mb": current.vms_mb,
                "percent": current.percent,
                "available_system_mb": current.available_mb,
            },
            "timestamp": current.timestamp,
        }

        # Add baseline comparison if available
        if self._baseline:
            delta = self.get_memory_delta()
            if delta:
                rss_delta, percent_change = delta
                report["baseline_delta"] = {
                    "rss_change_mb": rss_delta,
                    "percent_change": percent_change,
                    "duration_seconds": current.timestamp - self._baseline.timestamp,
                }

        # Add history analysis if available
        if len(self._history) >= 2:
            # Calculate average and peak memory usage
            rss_values = [s.rss_mb for s in self._history]
            report["history"] = {
                "samples": len(self._history),
                "average_rss_mb": sum(rss_values) / len(rss_values),
                "peak_rss_mb": max(rss_values),
                "min_rss_mb": min(rss_values),
            }

            # Check for memory leak pattern (consistent growth)
            if len(self._history) >= 10:
                recent = self._history[-10:]
                growth_count = sum(
                    1 for i in range(1, len(recent)) if recent[i].rss_mb > recent[i - 1].rss_mb
                )
                if growth_count >= 8:  # 80% growing
                    report["warning"] = "Possible memory leak detected (consistent growth)"

        return report

    def log_memory_status(self) -> None:
        """Log current memory status."""
        stats = self.get_memory_stats()
        if not stats:
            return

        self.logger.info(
            f"Memory usage: {stats.rss_mb:.1f}MB RSS, "
            f"{stats.vms_mb:.1f}MB VMS, "
            f"{stats.percent:.1f}% of system"
        )

        # Log delta if baseline is set
        delta = self.get_memory_delta()
        if delta:
            rss_delta, percent_change = delta
            self.logger.info(
                f"Memory delta: {rss_delta:+.1f}MB ({percent_change:+.1f}%) since baseline"
            )


# Global memory profiler instance
memory_profiler = MemoryProfiler()
