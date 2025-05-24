"""Tests for the async network management utilities."""

import asyncio
import subprocess
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rpi_weather_display.constants import (
    GOOGLE_DNS,
    GOOGLE_DNS_PORT,
    WIFI_INTERFACE_NAME,
)
from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import (
    BatteryState,
    BatteryStatus,
    NetworkState,
)
from rpi_weather_display.utils.network import AsyncNetworkManager


@pytest.fixture()
def power_config():
    """Create a test power configuration."""
    return PowerConfig(
        low_battery_threshold=20,
        critical_battery_threshold=10,
        retry_max_attempts=3,
        retry_initial_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        retry_max_delay_seconds=10.0,
        retry_jitter_factor=0.1,
        wifi_timeout_seconds=10,
        wifi_power_save_mode="auto",
        enable_battery_aware_wifi=True,
    )


@pytest.fixture()
def app_config():
    """Create a test app configuration."""
    return AppConfig(
        weather=WeatherConfig(
            api_key="test_key",
            location={"lat": 0.0, "lon": 0.0},
        ),
        display=DisplayConfig(
            width=800,
            height=600,
        ),
        server=ServerConfig(
            url="http://localhost",
            port=8000,
        ),
        power=PowerConfig(),
        debug=False,
    )


@pytest.fixture()
def network_manager(power_config):
    """Create an AsyncNetworkManager instance for testing."""
    return AsyncNetworkManager(power_config)


@pytest.fixture()
def battery_status():
    """Create a test battery status."""
    return BatteryStatus(
        level=50,
        voltage=3.7,
        current=-0.5,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
    )


class TestAsyncNetworkManager:
    """Test the AsyncNetworkManager class."""

    @staticmethod
    def patch_file_command(command_path: str = "/usr/bin/cmd", exists: bool = True) -> Any:
        """Helper to patch both path resolution and file existence checks."""
        return patch.multiple(
            "rpi_weather_display.utils.network",
            path_resolver=Mock(get_bin_path=Mock(return_value=command_path)),
            file_exists=Mock(return_value=exists),
        )

    @staticmethod
    def patch_wifi_script(sudo_exists: bool = True, script_exists: bool = True) -> Any:
        """Helper to patch wifi-sleep.sh script and sudo checks."""
        def get_bin_path(cmd: str) -> str:
            if cmd == "sudo":
                return "/usr/bin/sudo"
            elif cmd == "ifconfig":
                return "/usr/bin/ifconfig"
            elif cmd == "iw":
                return "/usr/bin/iw"
            elif cmd == "iwconfig":
                return "/usr/bin/iwconfig"
            return f"/usr/bin/{cmd}"
        
        def file_exists_check(path: str) -> bool:
            if "sudo" in path:
                return sudo_exists
            elif "wifi-sleep.sh" in path:
                return script_exists
            return True
        
        return patch.multiple(
            "rpi_weather_display.utils.network",
            path_resolver=Mock(
                get_bin_path=Mock(side_effect=get_bin_path),
                normalize_path=Mock(return_value="/path/to/wifi-sleep.sh")
            ),
            file_exists=Mock(side_effect=file_exists_check),
        )

    def test_init(self, network_manager, power_config):
        """Test initialization of AsyncNetworkManager."""
        assert network_manager.config == power_config
        assert network_manager.app_config is None
        assert network_manager.current_battery_status is None
        assert isinstance(network_manager._subprocess_semaphore, asyncio.Semaphore)

    def test_set_app_config(self, network_manager, app_config):
        """Test setting app config."""
        network_manager.set_app_config(app_config)
        assert network_manager.app_config == app_config

    def test_update_battery_status(self, network_manager, battery_status):
        """Test updating battery status."""
        network_manager.update_battery_status(battery_status)
        assert network_manager.current_battery_status == battery_status

    @pytest.mark.asyncio()
    async def test_get_network_status_connected(self, network_manager):
        """Test getting network status when connected."""
        # Mock the internal methods
        with patch.object(network_manager, "_check_connectivity", return_value=True) as mock_check:
            with patch.object(network_manager, "_get_ssid", return_value="TestSSID") as mock_ssid:
                with patch.object(
                    network_manager, "_get_ip_address", return_value="192.168.1.100"
                ) as mock_ip:
                    with patch.object(
                        network_manager, "_get_signal_strength", return_value=-50
                    ) as mock_signal:
                        status = await network_manager.get_network_status()

                        assert status.state == NetworkState.CONNECTED
                        assert status.ssid == "TestSSID"
                        assert status.ip_address == "192.168.1.100"
                        assert status.signal_strength == -50
                        assert isinstance(status.last_connection, datetime)

                        # Verify all methods were called
                        mock_check.assert_called_once()
                        mock_ssid.assert_called_once()
                        mock_ip.assert_called_once()
                        mock_signal.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_network_status_disconnected(self, network_manager):
        """Test getting network status when disconnected."""
        with patch.object(network_manager, "_check_connectivity", return_value=False):
            status = await network_manager.get_network_status()

            assert status.state == NetworkState.DISCONNECTED
            assert status.ssid is None
            assert status.ip_address is None

    @pytest.mark.asyncio()
    async def test_get_network_status_error(self, network_manager):
        """Test getting network status when error occurs."""
        with patch.object(
            network_manager, "_check_connectivity", side_effect=Exception("Test error")
        ):
            status = await network_manager.get_network_status()

            assert status.state == NetworkState.ERROR

    @pytest.mark.asyncio()
    async def test_check_connectivity_success(self, network_manager):
        """Test checking connectivity successfully."""
        mock_socket = Mock()
        mock_socket.connect_ex = Mock(return_value=0)
        mock_socket.close = Mock()

        with patch("socket.socket", return_value=mock_socket):
            result = await network_manager._check_connectivity()

            assert result is True
            mock_socket.settimeout.assert_called_once_with(
                network_manager.config.wifi_timeout_seconds
            )
            mock_socket.connect_ex.assert_called_once_with((GOOGLE_DNS, GOOGLE_DNS_PORT))
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_check_connectivity_failure(self, network_manager):
        """Test checking connectivity failure."""
        mock_socket = Mock()
        mock_socket.connect_ex = Mock(return_value=1)  # Non-zero means failure
        mock_socket.close = Mock()

        with patch("socket.socket", return_value=mock_socket):
            result = await network_manager._check_connectivity()

            assert result is False

    @pytest.mark.asyncio()
    async def test_check_connectivity_exception(self, network_manager):
        """Test checking connectivity with exception."""
        with patch("socket.socket", side_effect=OSError("Connection failed")):
            result = await network_manager._check_connectivity()

            assert result is False

    def test_calculate_backoff_delay(self, network_manager):
        """Test calculating backoff delay."""
        # Test first attempt
        delay = network_manager._calculate_backoff_delay(0)
        assert 0.9 <= delay <= 1.1  # 1.0 +/- 0.1 jitter

        # Test second attempt
        delay = network_manager._calculate_backoff_delay(1)
        assert 1.8 <= delay <= 2.2  # 2.0 +/- 0.2 jitter

        # Test max delay cap
        delay = network_manager._calculate_backoff_delay(10)
        assert delay <= network_manager.config.retry_max_delay_seconds * 1.1

    @pytest.mark.asyncio()
    async def test_with_retry_success(self, network_manager):
        """Test retry mechanism with successful operation."""

        async def mock_operation(value: int) -> int:
            return value * 2

        result = await network_manager.with_retry(mock_operation, 5)
        assert result == 10

    @pytest.mark.asyncio()
    async def test_with_retry_eventual_success(self, network_manager):
        """Test retry mechanism with eventual success."""
        attempt_count = 0

        async def mock_operation() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnectionError("Failed")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            result = await network_manager.with_retry(mock_operation)
            assert result == "success"
            assert attempt_count == 2

    @pytest.mark.asyncio()
    async def test_with_retry_all_attempts_fail(self, network_manager):
        """Test retry mechanism when all attempts fail."""

        async def mock_operation() -> None:
            raise ConnectionError("Always fails")

        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            result = await network_manager.with_retry(mock_operation)
            assert result is None

    @pytest.mark.asyncio()
    async def test_run_subprocess_success(self, network_manager):
        """Test running subprocess successfully."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await network_manager._run_subprocess(["echo", "test"])

            assert result.returncode == 0
            assert result.stdout == "output"
            assert result.stderr == ""
            mock_create.assert_called_once_with(
                "echo",
                "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio()
    async def test_run_subprocess_timeout(self, network_manager):
        """Test running subprocess with timeout."""
        mock_proc = Mock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError())
        mock_proc.kill = Mock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(subprocess.TimeoutExpired):
                await network_manager._run_subprocess(["sleep", "100"])

            mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_ssid_success(self, network_manager):
        """Test getting SSID successfully."""
        with self.patch_file_command("/usr/bin/iwgetid", exists=True):
            with patch.object(
                network_manager,
                "_run_subprocess",
                return_value=Mock(returncode=0, stdout="TestNetwork\n", stderr=""),
            ) as mock_run:
                ssid = await network_manager._get_ssid()

                assert ssid == "TestNetwork"
                mock_run.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_ssid_command_not_found(self, network_manager):
        """Test getting SSID when command not found."""
        with self.patch_file_command("/usr/bin/iwgetid", exists=False):
            ssid = await network_manager._get_ssid()
            assert ssid is None

    @pytest.mark.asyncio()
    async def test_get_ssid_failure(self, network_manager):
        """Test getting SSID failure."""
        with self.patch_file_command("/usr/bin/iwgetid", exists=True):
            with patch.object(
                network_manager,
                "_run_subprocess",
                return_value=Mock(returncode=1, stdout="", stderr="Error"),
            ):
                ssid = await network_manager._get_ssid()
                assert ssid is None

    @pytest.mark.asyncio()
    async def test_get_ip_address_success(self, network_manager):
        """Test getting IP address successfully."""
        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("192.168.1.100", 0)
        mock_socket.__enter__ = Mock(return_value=mock_socket)
        mock_socket.__exit__ = Mock(return_value=None)

        with patch("socket.socket", return_value=mock_socket):
            ip = await network_manager._get_ip_address()
            assert ip == "192.168.1.100"

    @pytest.mark.asyncio()
    async def test_get_ip_address_failure(self, network_manager):
        """Test getting IP address failure."""
        with patch("socket.socket", side_effect=Exception("Failed")):
            ip = await network_manager._get_ip_address()
            assert ip is None

    @pytest.mark.asyncio()
    async def test_get_signal_strength_success(self, network_manager):
        """Test getting signal strength successfully."""
        output = """
wlan0     IEEE 802.11  ESSID:"TestNetwork"
          Mode:Managed  Frequency:2.412 GHz  Access Point: 00:00:00:00:00:00
          Bit Rate=72.2 Mb/s   Tx-Power=20 dBm
          Link Quality=70/70  Signal level=-40 dBm
"""
        with self.patch_file_command("/usr/bin/iwconfig", exists=True):
            with patch.object(
                network_manager,
                "_run_subprocess",
                return_value=Mock(returncode=0, stdout=output, stderr=""),
            ):
                signal = await network_manager._get_signal_strength()
                assert signal == -40

    @pytest.mark.asyncio()
    async def test_get_signal_strength_not_found(self, network_manager):
        """Test getting signal strength when not found in output."""
        with self.patch_file_command("/usr/bin/iwconfig", exists=True):
            with patch.object(
                network_manager,
                "_run_subprocess",
                return_value=Mock(returncode=0, stdout="No signal info", stderr=""),
            ):
                signal = await network_manager._get_signal_strength()
                assert signal is None

    @pytest.mark.asyncio()
    async def test_get_signal_strength_parse_error(self, network_manager):
        """Test getting signal strength with parse error."""
        output = "Signal level=invalid"
        with self.patch_file_command("/usr/bin/iwconfig", exists=True):
            with patch.object(
                network_manager,
                "_run_subprocess",
                return_value=Mock(returncode=0, stdout=output, stderr=""),
            ):
                signal = await network_manager._get_signal_strength()
                assert signal is None

    @pytest.mark.asyncio()
    async def test_ensure_connectivity_already_connected(self, network_manager):
        """Test ensure_connectivity when already connected."""
        with patch.object(network_manager, "_check_connectivity", return_value=True):
            with patch.object(
                network_manager, "_disable_wifi", new_callable=AsyncMock
            ) as mock_disable:
                async with network_manager.ensure_connectivity() as connected:
                    assert connected is True

                # WiFi should be disabled after context exit
                mock_disable.assert_called_once()

    @pytest.mark.asyncio()
    async def test_ensure_connectivity_connect_success(self, network_manager):
        """Test ensure_connectivity with successful connection."""
        # First check returns False, then True after enabling
        check_results = [False, True]
        check_call_count = 0

        async def mock_check() -> bool:
            nonlocal check_call_count
            result = check_results[min(check_call_count, len(check_results) - 1)]
            check_call_count += 1
            return result

        with patch.object(network_manager, "_check_connectivity", side_effect=mock_check):
            with patch.object(
                network_manager, "_enable_wifi", new_callable=AsyncMock
            ) as mock_enable:
                with patch.object(
                    network_manager, "_disable_wifi", new_callable=AsyncMock
                ) as mock_disable:
                    with patch.object(network_manager, "_try_connect", return_value=True):
                        async with network_manager.ensure_connectivity() as connected:
                            assert connected is True

                        mock_enable.assert_called_once()
                        mock_disable.assert_called_once()

    @pytest.mark.asyncio()
    async def test_ensure_connectivity_connect_failure(self, network_manager):
        """Test ensure_connectivity with connection failure."""
        with patch.object(network_manager, "_check_connectivity", return_value=False):
            with patch.object(network_manager, "_enable_wifi", new_callable=AsyncMock):
                with patch.object(network_manager, "_disable_wifi", new_callable=AsyncMock):
                    with patch.object(network_manager, "with_retry", return_value=None):
                        async with network_manager.ensure_connectivity() as connected:
                            assert connected is False

    @pytest.mark.asyncio()
    async def test_ensure_connectivity_debug_mode(self, network_manager, app_config):
        """Test ensure_connectivity in debug mode doesn't disable WiFi."""
        app_config.debug = True
        network_manager.set_app_config(app_config)

        with patch.object(network_manager, "_check_connectivity", return_value=True):
            with patch.object(
                network_manager, "_disable_wifi", new_callable=AsyncMock
            ) as mock_disable:
                async with network_manager.ensure_connectivity() as connected:
                    assert connected is True

                # WiFi should NOT be disabled in debug mode
                mock_disable.assert_not_called()

    @pytest.mark.asyncio()
    async def test_try_connect_success(self, network_manager):
        """Test _try_connect with successful connection."""
        with patch.object(network_manager, "_check_connectivity", return_value=True):
            result = await network_manager._try_connect()
            assert result is True

    @pytest.mark.asyncio()
    async def test_try_connect_timeout(self, network_manager):
        """Test _try_connect with timeout."""
        network_manager.config.wifi_timeout_seconds = 0.1  # Short timeout for test

        with patch.object(network_manager, "_check_connectivity", return_value=False):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ConnectionError):
                    await network_manager._try_connect()

    @pytest.mark.asyncio()
    async def test_enable_wifi_with_script(self, network_manager):
        """Test enabling WiFi with wifi-sleep.sh script."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                with patch.object(
                    network_manager, "_apply_power_save_mode", new_callable=AsyncMock
                ) as mock_power:
                    await network_manager._enable_wifi()

                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert "sudo" in args[0]
                    assert "wifi-sleep.sh" in args[1]
                    assert args[2] == "on"
                    mock_power.assert_called_once()

    @pytest.mark.asyncio()
    async def test_enable_wifi_script_not_found(self, network_manager):
        """Test enabling WiFi when script not found."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=False):
            with patch.object(
                network_manager, "_enable_wifi_legacy", new_callable=AsyncMock
            ) as mock_legacy:
                await network_manager._enable_wifi()
                mock_legacy.assert_called_once()

    @pytest.mark.asyncio()
    async def test_enable_wifi_script_error(self, network_manager):
        """Test enabling WiFi when script fails."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", side_effect=subprocess.SubprocessError("Failed")
            ):
                with patch.object(
                    network_manager, "_enable_wifi_legacy", new_callable=AsyncMock
                ) as mock_legacy:
                    await network_manager._enable_wifi()
                    mock_legacy.assert_called_once()

    @pytest.mark.asyncio()
    async def test_enable_wifi_legacy(self, network_manager):
        """Test enabling WiFi with legacy method."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                with patch.object(
                    network_manager, "_apply_power_save_mode", new_callable=AsyncMock
                ):
                    await network_manager._enable_wifi_legacy()

                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert "sudo" in args[0]
                    assert "ifconfig" in args[1]
                    assert WIFI_INTERFACE_NAME in args[2]
                    assert "up" in args[3]

    @pytest.mark.asyncio()
    async def test_apply_power_save_mode(self, network_manager):
        """Test applying power save mode."""
        network_manager.config.enable_battery_aware_wifi = True

        with patch.object(
            network_manager, "set_wifi_power_save_mode", new_callable=AsyncMock
        ) as mock_set:
            await network_manager._apply_power_save_mode()
            mock_set.assert_called_once()

    @pytest.mark.asyncio()
    async def test_disable_wifi_with_script(self, network_manager):
        """Test disabling WiFi with wifi-sleep.sh script."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                await network_manager._disable_wifi()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "sudo" in args[0]
                assert "wifi-sleep.sh" in args[1]
                assert args[2] == "off"

    @pytest.mark.asyncio()
    async def test_disable_wifi_legacy(self, network_manager):
        """Test disabling WiFi with legacy method."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                await network_manager._disable_wifi_legacy()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "sudo" in args[0]
                assert "ifconfig" in args[1]
                assert WIFI_INTERFACE_NAME in args[2]
                assert "down" in args[3]

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_default(self, network_manager):
        """Test setting WiFi power save mode with default."""
        network_manager.config.wifi_power_save_mode = "on"

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode()

                assert result is True
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "power_save" in args
                assert "on" in args

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_auto_critical(self, network_manager, battery_status):
        """Test setting WiFi power save mode auto with critical battery."""
        battery_status.level = 5  # Critical
        network_manager.update_battery_status(battery_status)
        network_manager.config.wifi_power_save_mode = "auto"

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode("auto")

                assert result is True
                # Should use aggressive mode
                assert mock_run.call_count >= 1  # May have additional calls for aggressive mode

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_auto_low(self, network_manager, battery_status):
        """Test setting WiFi power save mode auto with low battery."""
        battery_status.level = 15  # Low but not critical
        network_manager.update_battery_status(battery_status)

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode("auto")

                assert result is True
                args = mock_run.call_args[0][0]
                assert "on" in args  # Should use regular power saving

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_auto_good(self, network_manager, battery_status):
        """Test setting WiFi power save mode auto with good battery."""
        battery_status.level = 80  # Good battery
        network_manager.update_battery_status(battery_status)

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode("auto")

                assert result is True
                args = mock_run.call_args[0][0]
                assert "off" in args  # Should disable power saving

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_invalid(self, network_manager):
        """Test setting WiFi power save mode with invalid mode."""
        result = await network_manager.set_wifi_power_save_mode("invalid")
        assert result is False

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_command_not_found(self, network_manager):
        """Test setting WiFi power save mode when commands not found."""
        with self.patch_wifi_script(sudo_exists=False, script_exists=False):
            result = await network_manager.set_wifi_power_save_mode("on")
            assert result is False

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_error(self, network_manager):
        """Test setting WiFi power save mode with error."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", side_effect=subprocess.SubprocessError("Failed")
            ):
                result = await network_manager.set_wifi_power_save_mode("on")
                assert result is False

    @pytest.mark.asyncio()
    async def test_subprocess_semaphore_limits_concurrency(self, network_manager):
        """Test that subprocess semaphore limits concurrent operations."""
        # Set semaphore to limit of 1 for easier testing
        network_manager._subprocess_semaphore = asyncio.Semaphore(1)

        call_order = []

        async def mock_create_subprocess(*_args: str, **_kwargs: Any) -> Mock:
            call_order.append("start")
            await asyncio.sleep(0.1)  # Simulate work
            call_order.append("end")
            mock_proc = Mock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess):
            # Start two operations concurrently
            tasks = [
                network_manager._run_subprocess(["echo", "1"]),
                network_manager._run_subprocess(["echo", "2"]),
            ]
            await asyncio.gather(*tasks)

            # With semaphore limit of 1, operations should not overlap
            assert call_order == ["start", "end", "start", "end"]

    @pytest.mark.asyncio()
    async def test_disable_wifi_script_not_found(self, network_manager):
        """Test disabling WiFi when script not found."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=False):
            with patch.object(
                network_manager, "_disable_wifi_legacy", new_callable=AsyncMock
            ) as mock_legacy:
                await network_manager._disable_wifi()
                mock_legacy.assert_called_once()

    @pytest.mark.asyncio()
    async def test_disable_wifi_script_error(self, network_manager):
        """Test disabling WiFi when script fails."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", side_effect=subprocess.SubprocessError("Failed")
            ):
                with patch.object(
                    network_manager, "_disable_wifi_legacy", new_callable=AsyncMock
                ) as mock_legacy:
                    await network_manager._disable_wifi()
                    mock_legacy.assert_called_once()

    @pytest.mark.asyncio()
    async def test_enable_wifi_legacy_no_commands(self, network_manager):
        """Test enabling WiFi legacy when commands not found."""
        with self.patch_wifi_script(sudo_exists=False, script_exists=False):
            await network_manager._enable_wifi_legacy()
            # Should log warning but not raise exception

    @pytest.mark.asyncio()
    async def test_disable_wifi_legacy_no_commands(self, network_manager):
        """Test disabling WiFi legacy when commands not found."""
        with self.patch_wifi_script(sudo_exists=False, script_exists=False):
            await network_manager._disable_wifi_legacy()
            # Should log warning but not raise exception

    @pytest.mark.asyncio()
    async def test_enable_wifi_legacy_error(self, network_manager):
        """Test enabling WiFi legacy with error."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", side_effect=subprocess.SubprocessError("Failed")
            ):
                await network_manager._enable_wifi_legacy()
                # Should log error but not raise exception

    @pytest.mark.asyncio()
    async def test_disable_wifi_legacy_error(self, network_manager):
        """Test disabling WiFi legacy with error."""
        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", side_effect=subprocess.SubprocessError("Failed")
            ):
                await network_manager._disable_wifi_legacy()
                # Should log error but not raise exception

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_aggressive(self, network_manager):
        """Test setting WiFi power save mode to aggressive."""
        network_manager.config.wifi_power_save_mode = "aggressive"

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode("aggressive")

                assert result is True
                # Should have multiple calls for aggressive mode
                assert mock_run.call_count >= 2

    @pytest.mark.asyncio()
    async def test_set_wifi_power_save_mode_auto_no_battery(self, network_manager):
        """Test setting WiFi power save mode auto without battery status."""
        network_manager.current_battery_status = None

        with self.patch_wifi_script(sudo_exists=True, script_exists=True):
            with patch.object(
                network_manager, "_run_subprocess", new_callable=AsyncMock
            ) as mock_run:
                result = await network_manager.set_wifi_power_save_mode("auto")

                assert result is True
                args = mock_run.call_args[0][0]
                assert "on" in args  # Should default to on

    @pytest.mark.asyncio()
    async def test_get_ssid_subprocess_error(self, network_manager):
        """Test getting SSID with subprocess error."""
        with self.patch_file_command("/usr/bin/iwgetid", exists=True):
            with patch.object(
                network_manager, "_run_subprocess",
                side_effect=subprocess.SubprocessError("Failed")
            ):
                ssid = await network_manager._get_ssid()
                assert ssid is None

    @pytest.mark.asyncio()
    async def test_get_signal_strength_command_not_found(self, network_manager):
        """Test getting signal strength when command not found."""
        with self.patch_file_command("/usr/bin/iwconfig", exists=False):
            signal = await network_manager._get_signal_strength()
            assert signal is None

    @pytest.mark.asyncio()
    async def test_check_connectivity_timeout_error(self, network_manager):
        """Test connectivity check with timeout error."""
        with patch("socket.socket", side_effect=TimeoutError("Timeout")):
            result = await network_manager._check_connectivity()
            assert result is False

    @pytest.mark.asyncio()
    async def test_check_connectivity_unexpected_error(self, network_manager):
        """Test connectivity check with unexpected error from executor."""
        # The inner try_connect function catches all exceptions,
        # so we need to test an exception from run_in_executor itself
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = RuntimeError("Unexpected executor error")
            with pytest.raises(RuntimeError):
                await network_manager._check_connectivity()
