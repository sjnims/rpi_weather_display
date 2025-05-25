"""Tests for the SystemMetricsCollector module."""

from unittest.mock import MagicMock, patch

from rpi_weather_display.utils.system_metrics_collector import SystemMetricsCollector


class TestSystemMetricsCollector:
    """Test cases for SystemMetricsCollector class."""

    def test_init(self) -> None:
        """Test SystemMetricsCollector initialization."""
        collector = SystemMetricsCollector()
        assert collector._cpu_temp_path == "/sys/class/thermal/thermal_zone0/temp"
        assert collector._meminfo_path == "/proc/meminfo"
        assert collector._loadavg_path == "/proc/loadavg"

    def test_get_system_metrics_empty(self) -> None:
        """Test getting system metrics when all fail."""
        collector = SystemMetricsCollector()

        with (
            patch("subprocess.run", side_effect=Exception("Command failed")),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=False
            ),
        ):
            metrics = collector.get_system_metrics()
            assert isinstance(metrics, dict)
            assert len(metrics) == 0

    @patch("subprocess.run")
    def test_get_cpu_usage(self, mock_run: MagicMock) -> None:
        """Test CPU usage retrieval."""
        collector = SystemMetricsCollector()

        # Mock top output
        mock_run.return_value = MagicMock(
            returncode=0, stdout="%Cpu(s):  5.0 us,  2.0 sy,  0.0 ni, 92.0 id,  1.0 wa"
        )

        usage = collector._get_cpu_usage()
        assert usage == 8.0  # 100 - 92 (idle)

    @patch("subprocess.run")
    def test_get_cpu_usage_error(self, mock_run: MagicMock) -> None:
        """Test CPU usage retrieval with error."""
        collector = SystemMetricsCollector()
        mock_run.side_effect = Exception("Command failed")

        usage = collector._get_cpu_usage()
        assert usage is None

    def test_get_memory_info(self) -> None:
        """Test memory info retrieval."""
        collector = SystemMetricsCollector()

        meminfo_content = """MemTotal:        8000000 kB
MemFree:         2000000 kB
MemAvailable:    3000000 kB"""

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                return_value=meminfo_content,
            ),
        ):
            info = collector._get_memory_info()
            assert info["memory_used_mb"] == 4882.8  # (8000000 - 3000000) / 1024
            assert info["memory_percent"] == 62.5  # 5000000 / 8000000 * 100

    def test_get_memory_info_file_not_found(self) -> None:
        """Test memory info when file not found."""
        collector = SystemMetricsCollector()

        with patch(
            "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=False
        ):
            info = collector._get_memory_info()
            assert info == {}

    @patch("subprocess.run")
    def test_get_disk_usage(self, mock_run: MagicMock) -> None:
        """Test disk usage retrieval."""
        collector = SystemMetricsCollector()

        # Mock df output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""Filesystem      Size  Used Avail Use% Mounted on
/dev/root        29G  5.2G   23G  19% /""",
        )

        info = collector._get_disk_usage()
        assert info["disk_used_gb"] == 5.2
        assert info["disk_percent"] == 19.0

    def test_get_cpu_temperature(self) -> None:
        """Test CPU temperature retrieval."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text", return_value="45123"
            ),
        ):
            temp = collector._get_cpu_temperature()
            assert temp == 45.123

    def test_get_cpu_temperature_file_not_found(self) -> None:
        """Test CPU temperature when file not found."""
        collector = SystemMetricsCollector()

        with patch(
            "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=False
        ):
            temp = collector._get_cpu_temperature()
            assert temp is None

    def test_get_load_average(self) -> None:
        """Test load average retrieval."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                return_value="1.23 0.89 0.67 1/234 5678",
            ),
        ):
            load = collector._get_load_average()
            assert load == 1.23

    def test_parse_size_to_gb(self) -> None:
        """Test size string parsing."""
        collector = SystemMetricsCollector()

        assert collector._parse_size_to_gb("5.2G") == 5.2
        assert collector._parse_size_to_gb("512M") == 0.5
        assert collector._parse_size_to_gb("1024K") == 0.0009765625
        assert collector._parse_size_to_gb("1073741824") == 1.0
        assert collector._parse_size_to_gb("invalid") == 0.0

    def test_get_metrics_summary(self) -> None:
        """Test metrics summary generation."""
        collector = SystemMetricsCollector()

        # Mock all the metric methods
        with patch.object(
            collector,
            "get_system_metrics",
            return_value={
                "cpu_usage": 25.5,
                "memory_percent": 45.2,
                "disk_percent": 75.8,
                "temperature_c": 42.3,
            },
        ):
            summary = collector.get_metrics_summary()
            assert "CPU: 25.5%" in summary
            assert "Memory: 45.2%" in summary
            assert "Disk: 75.8%" in summary
            assert "Temp: 42.3°C" in summary

    def test_get_metrics_summary_empty(self) -> None:
        """Test metrics summary when no metrics available."""
        collector = SystemMetricsCollector()

        with patch.object(collector, "get_system_metrics", return_value={}):
            summary = collector.get_metrics_summary()
            assert summary == "No metrics available"

    def test_get_system_metrics_full(self) -> None:
        """Test getting all system metrics."""
        collector = SystemMetricsCollector()

        # Mock all the individual metric methods
        with (
            patch.object(collector, "_get_cpu_usage", return_value=25.0),
            patch.object(
                collector,
                "_get_memory_info",
                return_value={"memory_used_mb": 1024.0, "memory_percent": 50.0},
            ),
            patch.object(
                collector,
                "_get_disk_usage",
                return_value={"disk_used_gb": 10.0, "disk_percent": 20.0},
            ),
            patch.object(collector, "_get_cpu_temperature", return_value=45.0),
            patch.object(collector, "_get_load_average", return_value=1.5),
        ):
            metrics = collector.get_system_metrics()
            assert metrics["cpu_usage"] == 25.0
            assert metrics["memory_used_mb"] == 1024.0
            assert metrics["memory_percent"] == 50.0
            assert metrics["disk_used_gb"] == 10.0
            assert metrics["disk_percent"] == 20.0
            assert metrics["temperature_c"] == 45.0
            assert metrics["load_average"] == 1.5


class TestSystemMetricsCollectorCoverage:
    """Additional test cases for complete coverage of SystemMetricsCollector."""

    def test_get_memory_info_exception(self) -> None:
        """Test memory info retrieval with exception during parsing."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                side_effect=Exception("Read error"),
            ),
        ):
            info = collector._get_memory_info()
            assert info == {}

    def test_get_memory_info_invalid_content(self) -> None:
        """Test memory info with invalid content that causes parsing error."""
        collector = SystemMetricsCollector()

        # Content that will cause int() to fail
        meminfo_content = """MemTotal:        invalid kB
MemAvailable:    invalid kB"""

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                return_value=meminfo_content,
            ),
        ):
            info = collector._get_memory_info()
            assert info == {}

    def test_get_cpu_temperature_exception(self) -> None:
        """Test CPU temperature retrieval with exception during parsing."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                side_effect=Exception("Read error"),
            ),
        ):
            temp = collector._get_cpu_temperature()
            assert temp is None

    def test_get_cpu_temperature_invalid_content(self) -> None:
        """Test CPU temperature with invalid content that causes parsing error."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text", return_value="invalid"
            ),
        ):
            temp = collector._get_cpu_temperature()
            assert temp is None

    def test_get_load_average_exception(self) -> None:
        """Test load average retrieval with exception during parsing."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                side_effect=Exception("Read error"),
            ),
        ):
            load = collector._get_load_average()
            assert load is None

    def test_get_load_average_invalid_content(self) -> None:
        """Test load average with invalid content that causes parsing error."""
        collector = SystemMetricsCollector()

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text", return_value="invalid"
            ),
        ):
            load = collector._get_load_average()
            assert load is None

    def test_get_load_average_file_not_found(self) -> None:
        """Test load average when file not found."""
        collector = SystemMetricsCollector()

        with patch(
            "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=False
        ):
            load = collector._get_load_average()
            assert load is None

    @patch("subprocess.run")
    def test_get_cpu_usage_no_cpu_line(self, mock_run: MagicMock) -> None:
        """Test CPU usage when %Cpu line is not found in output."""
        collector = SystemMetricsCollector()

        # Mock top output without %Cpu line
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Some other output\nWithout CPU line"
        )

        usage = collector._get_cpu_usage()
        assert usage is None

    @patch("subprocess.run")
    def test_get_cpu_usage_failed_command(self, mock_run: MagicMock) -> None:
        """Test CPU usage when command returns non-zero exit code."""
        collector = SystemMetricsCollector()

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        usage = collector._get_cpu_usage()
        assert usage is None

    @patch("subprocess.run")
    def test_get_disk_usage_error(self, mock_run: MagicMock) -> None:
        """Test disk usage retrieval with error."""
        collector = SystemMetricsCollector()
        mock_run.side_effect = Exception("Command failed")

        info = collector._get_disk_usage()
        assert info == {}

    @patch("subprocess.run")
    def test_get_disk_usage_failed_command(self, mock_run: MagicMock) -> None:
        """Test disk usage when command returns non-zero exit code."""
        collector = SystemMetricsCollector()

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        info = collector._get_disk_usage()
        assert info == {}

    @patch("subprocess.run")
    def test_get_disk_usage_invalid_output(self, mock_run: MagicMock) -> None:
        """Test disk usage with invalid df output."""
        collector = SystemMetricsCollector()

        # Mock df output with insufficient data
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Filesystem\nInvalid",
        )

        info = collector._get_disk_usage()
        assert info == {}

    @patch("subprocess.run")
    def test_get_disk_usage_short_output(self, mock_run: MagicMock) -> None:
        """Test disk usage with too few lines in output."""
        collector = SystemMetricsCollector()

        # Mock df output with only header
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Filesystem      Size  Used Avail Use% Mounted on",
        )

        info = collector._get_disk_usage()
        assert info == {}

    @patch("subprocess.run")
    def test_get_disk_usage_few_parts(self, mock_run: MagicMock) -> None:
        """Test disk usage with too few parts in data line."""
        collector = SystemMetricsCollector()

        # Mock df output with insufficient columns
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""Filesystem      Size  Used
/dev/root        29G""",
        )

        info = collector._get_disk_usage()
        assert info == {}

    def test_parse_size_to_gb_edge_cases(self) -> None:
        """Test size parsing with more edge cases."""
        collector = SystemMetricsCollector()

        # Test lowercase
        assert collector._parse_size_to_gb("5.2g") == 5.2
        assert collector._parse_size_to_gb("512m") == 0.5
        assert collector._parse_size_to_gb("1024k") == 0.0009765625

    def test_get_memory_info_missing_fields(self) -> None:
        """Test memory info when some fields are missing."""
        collector = SystemMetricsCollector()

        # Only MemTotal, no MemAvailable
        meminfo_content = """MemTotal:        8000000 kB
MemFree:         2000000 kB"""

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                return_value=meminfo_content,
            ),
        ):
            info = collector._get_memory_info()
            # With MemAvailable missing (defaulting to 0), it will calculate:
            # mem_used = 8000000 - 0 = 8000000 kB
            # mem_used_mb = 8000000 / 1024 = 7812.5 MB
            # mem_percent = 8000000 / 8000000 * 100 = 100%
            assert info["memory_used_mb"] == 7812.5
            assert info["memory_percent"] == 100.0

    def test_get_memory_info_zero_total(self) -> None:
        """Test memory info when MemTotal is zero."""
        collector = SystemMetricsCollector()

        meminfo_content = """MemTotal:        0 kB
MemAvailable:    0 kB"""

        with (
            patch(
                "rpi_weather_display.utils.system_metrics_collector.file_exists", return_value=True
            ),
            patch(
                "rpi_weather_display.utils.system_metrics_collector.read_text",
                return_value=meminfo_content,
            ),
        ):
            info = collector._get_memory_info()
            # Should return empty dict because division by zero would occur
            assert info == {}

    def test_get_metrics_summary_partial(self) -> None:
        """Test metrics summary with only some metrics available."""
        collector = SystemMetricsCollector()

        # Mock with only CPU and memory metrics
        with patch.object(
            collector,
            "get_system_metrics",
            return_value={
                "cpu_usage": 25.5,
                "memory_percent": 45.2,
            },
        ):
            summary = collector.get_metrics_summary()
            assert "CPU: 25.5%" in summary
            assert "Memory: 45.2%" in summary
            assert "Disk:" not in summary
            assert "Temp:" not in summary

    @patch("subprocess.run")
    def test_get_cpu_usage_malformed_idle(self, mock_run: MagicMock) -> None:
        """Test CPU usage with malformed idle value."""
        collector = SystemMetricsCollector()

        # Mock top output with %Cpu line but no "id" field
        mock_run.return_value = MagicMock(
            returncode=0, stdout="%Cpu(s):  5.0 us,  2.0 sy,  0.0 ni,  1.0 wa"
        )

        usage = collector._get_cpu_usage()
        assert usage is None
