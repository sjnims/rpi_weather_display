"""Tests for memory profiler utilities."""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from rpi_weather_display.utils.memory_profiler import (
    MemoryProfiler,
    MemoryStats,
    memory_profiler,
)


@pytest.fixture()
def mock_psutil() -> Mock:
    """Create a mock psutil module."""
    mock = MagicMock()
    
    # Mock process
    mock_process = MagicMock()
    mock_memory_info = MagicMock()
    mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB
    mock_memory_info.vms = 200 * 1024 * 1024  # 200 MB
    mock_process.memory_info.return_value = mock_memory_info
    mock_process.memory_percent.return_value = 5.0
    
    # Mock virtual memory
    mock_virtual_memory = MagicMock()
    mock_virtual_memory.available = 1000 * 1024 * 1024  # 1000 MB
    mock.virtual_memory.return_value = mock_virtual_memory
    
    # Make Process return our mock process
    mock.Process.return_value = mock_process
    
    return mock


@pytest.fixture()
def profiler() -> MemoryProfiler:
    """Create a memory profiler instance."""
    return MemoryProfiler(max_history=5)


class TestMemoryStats:
    """Test MemoryStats dataclass."""

    def test_memory_stats_creation(self) -> None:
        """Test creating MemoryStats instance."""
        stats = MemoryStats(
            rss_mb=100.0,
            vms_mb=200.0,
            percent=5.0,
            available_mb=1000.0,
            timestamp=1234567890.0
        )
        
        assert stats.rss_mb == 100.0
        assert stats.vms_mb == 200.0
        assert stats.percent == 5.0
        assert stats.available_mb == 1000.0
        assert stats.timestamp == 1234567890.0


class TestMemoryProfiler:
    """Test MemoryProfiler class."""

    def test_init(self, profiler: MemoryProfiler) -> None:
        """Test profiler initialization."""
        assert profiler._baseline is None
        assert profiler._history == []
        assert profiler._max_history == 5
        assert isinstance(profiler.logger, logging.Logger)

    def test_get_memory_stats_no_psutil(self, profiler: MemoryProfiler) -> None:
        """Test getting memory stats when psutil is not available."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            stats = profiler.get_memory_stats()
            assert stats is None

    def test_get_memory_stats_success(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test successfully getting memory stats."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             patch("time.time", return_value=1234567890.0):
            stats = profiler.get_memory_stats()
            
            assert stats is not None
            assert stats.rss_mb == 100.0
            assert stats.vms_mb == 200.0
            assert stats.percent == 5.0
            assert stats.available_mb == 1000.0
            assert stats.timestamp == 1234567890.0

    def test_get_memory_stats_exception(self, profiler: MemoryProfiler, mock_psutil: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test getting memory stats with exception."""
        mock_psutil.Process.side_effect = Exception("Process error")
        
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             caplog.at_level(logging.ERROR):
            stats = profiler.get_memory_stats()
            
            assert stats is None
            assert "Error getting memory stats" in caplog.text
            assert "Process error" in caplog.text

    def test_set_baseline(self, profiler: MemoryProfiler, mock_psutil: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test setting memory baseline."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             caplog.at_level(logging.INFO):
            profiler.set_baseline()
            
            assert profiler._baseline is not None
            assert profiler._baseline.rss_mb == 100.0
            assert "Memory baseline set: 100.0MB RSS" in caplog.text

    def test_set_baseline_no_psutil(self, profiler: MemoryProfiler) -> None:
        """Test setting baseline when psutil is not available."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            profiler.set_baseline()
            assert profiler._baseline is None

    def test_record_snapshot(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test recording memory snapshot."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Record first snapshot
            stats1 = profiler.record_snapshot()
            assert stats1 is not None
            assert len(profiler._history) == 1
            
            # Record more snapshots
            for _ in range(4):
                profiler.record_snapshot()
            assert len(profiler._history) == 5
            
            # Record one more - should trim history
            profiler.record_snapshot()
            assert len(profiler._history) == 5  # Still 5 due to max_history

    def test_record_snapshot_no_psutil(self, profiler: MemoryProfiler) -> None:
        """Test recording snapshot when psutil is not available."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            stats = profiler.record_snapshot()
            assert stats is None
            assert len(profiler._history) == 0

    def test_get_memory_delta_no_baseline(self, profiler: MemoryProfiler) -> None:
        """Test getting memory delta without baseline."""
        delta = profiler.get_memory_delta()
        assert delta is None

    def test_get_memory_delta_no_current(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test getting memory delta when current stats unavailable."""
        # Set baseline
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            profiler.set_baseline()
        
        # Now make psutil unavailable
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            delta = profiler.get_memory_delta()
            assert delta is None

    def test_get_memory_delta_success(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test successfully getting memory delta."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Set baseline
            profiler.set_baseline()
            
            # Change memory values
            mock_psutil.Process.return_value.memory_info.return_value.rss = 150 * 1024 * 1024  # 150 MB
            
            # Get delta
            delta = profiler.get_memory_delta()
            assert delta is not None
            rss_delta, percent_change = delta
            assert rss_delta == 50.0  # 150 - 100
            assert percent_change == 50.0  # 50% increase

    def test_get_memory_delta_zero_baseline(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test memory delta with zero baseline."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Set baseline with 0 RSS
            mock_psutil.Process.return_value.memory_info.return_value.rss = 0
            profiler.set_baseline()
            
            # Change to non-zero
            mock_psutil.Process.return_value.memory_info.return_value.rss = 100 * 1024 * 1024
            
            # Get delta - should handle division by zero
            delta = profiler.get_memory_delta()
            assert delta is not None
            rss_delta, percent_change = delta
            assert rss_delta == 100.0
            assert percent_change == 0  # Avoided division by zero

    def test_check_memory_growth_no_delta(self, profiler: MemoryProfiler) -> None:
        """Test checking memory growth without delta."""
        result = profiler.check_memory_growth()
        assert result is False

    def test_check_memory_growth_below_threshold(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test memory growth below threshold."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Set baseline
            profiler.set_baseline()
            
            # Small increase
            mock_psutil.Process.return_value.memory_info.return_value.rss = 120 * 1024 * 1024  # 120 MB
            
            result = profiler.check_memory_growth(threshold_mb=50.0)
            assert result is False

    def test_check_memory_growth_above_threshold(self, profiler: MemoryProfiler, mock_psutil: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test memory growth above threshold."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             caplog.at_level(logging.WARNING):
            # Set baseline
            profiler.set_baseline()
            
            # Large increase
            mock_psutil.Process.return_value.memory_info.return_value.rss = 200 * 1024 * 1024  # 200 MB
            
            result = profiler.check_memory_growth(threshold_mb=50.0)
            assert result is True
            assert "Memory growth detected: 100.0MB increase" in caplog.text

    def test_get_report_no_psutil(self, profiler: MemoryProfiler) -> None:
        """Test getting report when psutil is not available."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            report = profiler.get_report()
            assert report == {"error": "Memory profiling not available (psutil not installed)"}

    def test_get_report_basic(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test getting basic report."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             patch("time.time", return_value=1234567890.0):
            report = profiler.get_report()
            
            assert "current" in report
            assert report["current"]["rss_mb"] == 100.0
            assert report["current"]["vms_mb"] == 200.0
            assert report["current"]["percent"] == 5.0
            assert report["current"]["available_system_mb"] == 1000.0
            assert "timestamp" in report
            assert report["timestamp"] == 1234567890.0

    def test_get_report_with_baseline(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test report with baseline comparison."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             patch("time.time", side_effect=[1000.0, 2000.0, 2000.0]):  # Extra value for get_memory_delta call
            # Set baseline
            profiler.set_baseline()
            
            # Change memory
            mock_psutil.Process.return_value.memory_info.return_value.rss = 150 * 1024 * 1024
            
            report = profiler.get_report()
            
            assert "baseline_delta" in report
            assert report["baseline_delta"]["rss_change_mb"] == 50.0
            assert report["baseline_delta"]["percent_change"] == 50.0
            assert report["baseline_delta"]["duration_seconds"] == 1000.0

    def test_get_report_with_baseline_no_delta(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test report with baseline but no delta available."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Set baseline
            profiler.set_baseline()
            
            # Make get_memory_delta return None by making current stats unavailable
            with patch.object(profiler, 'get_memory_delta', return_value=None):
                report = profiler.get_report()
                
                # Should have current stats but no baseline_delta
                assert "current" in report
                assert "baseline_delta" not in report

    def test_get_report_with_history(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test report with history analysis."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Record multiple snapshots with different memory values
            memory_values = [100, 120, 110, 130, 125]  # in MB
            for mb in memory_values:
                mock_psutil.Process.return_value.memory_info.return_value.rss = mb * 1024 * 1024
                profiler.record_snapshot()
            
            report = profiler.get_report()
            
            assert "history" in report
            assert report["history"]["samples"] == 5
            assert report["history"]["average_rss_mb"] == sum(memory_values) / len(memory_values)
            assert report["history"]["peak_rss_mb"] == 130.0
            assert report["history"]["min_rss_mb"] == 100.0

    def test_get_report_memory_leak_detection(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test memory leak detection in report."""
        # Need larger max_history for leak detection
        profiler = MemoryProfiler(max_history=20)
        
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Record 10 snapshots with consistent growth
            for i in range(10):
                mb = 100 + (i * 10)  # Consistent growth
                mock_psutil.Process.return_value.memory_info.return_value.rss = mb * 1024 * 1024
                profiler.record_snapshot()
            
            report = profiler.get_report()
            
            assert "warning" in report
            assert "Possible memory leak detected" in report["warning"]

    def test_get_report_no_memory_leak(self, profiler: MemoryProfiler, mock_psutil: Mock) -> None:
        """Test report with fluctuating memory (no leak)."""
        profiler = MemoryProfiler(max_history=20)
        
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil):
            # Record 10 snapshots with fluctuating values
            memory_values = [100, 110, 105, 115, 110, 120, 115, 125, 120, 130]
            for mb in memory_values:
                mock_psutil.Process.return_value.memory_info.return_value.rss = mb * 1024 * 1024
                profiler.record_snapshot()
            
            report = profiler.get_report()
            
            # Should not detect leak with fluctuating values
            assert "warning" not in report

    def test_log_memory_status_no_stats(self, profiler: MemoryProfiler, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging memory status when stats unavailable."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", None):
            profiler.log_memory_status()
            # Should not log anything
            assert len(caplog.records) == 0

    def test_log_memory_status_basic(self, profiler: MemoryProfiler, mock_psutil: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test basic memory status logging."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             caplog.at_level(logging.INFO):
            profiler.log_memory_status()
            
            assert "Memory usage: 100.0MB RSS, 200.0MB VMS, 5.0% of system" in caplog.text

    def test_log_memory_status_with_delta(self, profiler: MemoryProfiler, mock_psutil: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging memory status with delta."""
        with patch("rpi_weather_display.utils.memory_profiler.psutil", mock_psutil), \
             caplog.at_level(logging.INFO):
            # Set baseline
            profiler.set_baseline()
            caplog.clear()
            
            # Change memory
            mock_psutil.Process.return_value.memory_info.return_value.rss = 150 * 1024 * 1024
            
            profiler.log_memory_status()
            
            assert "Memory usage: 150.0MB RSS" in caplog.text
            assert "Memory delta: +50.0MB (+50.0%) since baseline" in caplog.text


class TestGlobalMemoryProfiler:
    """Test the global memory profiler instance."""

    def test_global_instance(self) -> None:
        """Test that global instance is available."""
        assert isinstance(memory_profiler, MemoryProfiler)
        assert memory_profiler._max_history == 100  # Default value