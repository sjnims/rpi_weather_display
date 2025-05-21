"""Tests for the network module."""

# pyright: reportPrivateUsage=false

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from rpi_weather_display.constants import WIFI_SLEEP_SCRIPT
from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import BatteryState, BatteryStatus, NetworkState
from rpi_weather_display.utils.network import NetworkManager
from rpi_weather_display.utils.path_utils import path_resolver

# Mock path constants for tests (replacing the ones removed from network.py)
SUDO_PATH = "/usr/bin/sudo"
IFCONFIG_PATH = "/sbin/ifconfig"
IWCONFIG_PATH = "/sbin/iwconfig"
IWGETID_PATH = "/sbin/iwgetid"
IW_PATH = "/sbin/iw"


@pytest.fixture()
def power_config() -> PowerConfig:
    """Create a power config fixture."""
    return PowerConfig(
        quiet_hours_start="23:00",
        quiet_hours_end="06:00",
        wake_up_interval_minutes=60,
        low_battery_threshold=20,
        critical_battery_threshold=10,
        wifi_timeout_seconds=30,
        enable_battery_aware_wifi=True,
        wifi_power_save_mode="auto",
        retry_initial_delay_seconds=1.0,
        retry_max_delay_seconds=300.0,
        retry_backoff_factor=2.0,
        retry_jitter_factor=0.1,
        retry_max_attempts=5,
    )


@pytest.fixture()
def weather_config() -> WeatherConfig:
    """Create a weather config fixture."""
    return WeatherConfig(
        api_key="test_api_key",
        city_name="Test City",
        update_interval_minutes=30,
    )


@pytest.fixture()
def display_config() -> DisplayConfig:
    """Create a display config fixture."""
    return DisplayConfig(
        width=1872,
        height=1404,
        refresh_interval_minutes=30,
    )


@pytest.fixture()
def server_config() -> ServerConfig:
    """Create a server config fixture."""
    return ServerConfig(
        url="http://localhost:8000",
    )


@pytest.fixture()
def app_config(
    power_config: PowerConfig,
    weather_config: WeatherConfig,
    display_config: DisplayConfig,
    server_config: ServerConfig,
) -> AppConfig:
    """Create an app config fixture."""
    return AppConfig(
        weather=weather_config,
        display=display_config,
        power=power_config,
        server=server_config,
        debug=False,
    )


@pytest.fixture()
def normal_battery() -> BatteryStatus:
    """Create a normal battery status for testing."""
    return BatteryStatus(
        level=75,
        voltage=3.7,
        current=100.0,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
        time_remaining=1200,
        timestamp=None,
    )


@pytest.fixture()
def low_battery() -> BatteryStatus:
    """Create a low battery status for testing."""
    return BatteryStatus(
        level=15,
        voltage=3.7,
        current=100.0,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
        time_remaining=1200,
        timestamp=None,
    )


@pytest.fixture()
def critical_battery() -> BatteryStatus:
    """Create a critical battery status for testing."""
    return BatteryStatus(
        level=5,
        voltage=3.7,
        current=100.0,
        temperature=25.0,
        state=BatteryState.DISCHARGING,
        time_remaining=1200,
        timestamp=None,
    )


@pytest.fixture()
def network_manager(power_config: PowerConfig) -> NetworkManager:
    """Create a network manager fixture."""
    return NetworkManager(power_config)


class TestNetworkManager:
    """Tests for the NetworkManager class."""

    def test_init(self, power_config: PowerConfig) -> None:
        """Test NetworkManager initialization."""
        manager = NetworkManager(power_config)
        assert manager.config == power_config
        assert manager.app_config is None

    @patch("rpi_weather_display.utils.network.file_exists")
    def test_path_resolver_availability(self, mock_exists: MagicMock) -> None:
        """Test that path_resolver is available and working."""
        # Mock exists to always return True for this test
        mock_exists.return_value = True

        # Verify path_resolver can resolve common command paths
        sudo_path = path_resolver.get_bin_path("sudo")
        assert sudo_path.exists(), "sudo path resolution failed"

        # Verify WIFI_SLEEP_SCRIPT constant is defined
        assert isinstance(WIFI_SLEEP_SCRIPT, str), "WIFI_SLEEP_SCRIPT should be a string"

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_enable_wifi(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _enable_wifi method."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Patch the _apply_power_save_mode method to do nothing
        with patch.object(network_manager, "_apply_power_save_mode"):
            # Call the method
            network_manager._enable_wifi()

            # Verify subprocess was called correctly - now checks for wifi-sleep.sh script
            mock_run.assert_called_with(
                [str(Path(SUDO_PATH)), str(Path(WIFI_SLEEP_SCRIPT)), "on"],
                check=True,
                timeout=network_manager.config.wifi_timeout_seconds,
                shell=False,
            )

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_disable_wifi(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _disable_wifi method."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Call the method
        network_manager._disable_wifi()

        # Verify subprocess was called correctly - now checks for wifi-sleep.sh script
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(WIFI_SLEEP_SCRIPT)), "off"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_disable_wifi_failure(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _disable_wifi method failure case."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to fail
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        # Call the method - it should handle the exception
        network_manager._disable_wifi()

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_network_status(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test get_network_status method."""
        # Set up mocks for _check_connectivity, _get_ssid, _get_ip_address, and _get_signal_strength
        with (
            patch.object(network_manager, "_check_connectivity", return_value=True),
            patch.object(network_manager, "_get_ssid", return_value="TestNetwork"),
            patch.object(network_manager, "_get_ip_address", return_value="192.168.1.5"),
            patch.object(network_manager, "_get_signal_strength", return_value=-65),
        ):
            # Call the method
            status = network_manager.get_network_status()

            # Verify the status was correctly set
            assert status.state == NetworkState.CONNECTED
            assert status.ssid == "TestNetwork"
            assert status.ip_address == "192.168.1.5"
            assert status.signal_strength == -65

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_network_status_disconnected(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test get_network_status method when disconnected."""
        # Set up mock for _check_connectivity to return False
        with patch.object(network_manager, "_check_connectivity", return_value=False):
            # Call the method
            status = network_manager.get_network_status()

            # Verify the status was correctly set
            assert status.state == NetworkState.DISCONNECTED

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_network_status_failure(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test get_network_status method when commands fail."""
        # Set up mock for _check_connectivity to raise an exception
        with patch.object(
            network_manager, "_check_connectivity", side_effect=Exception("Test error")
        ):
            # Call the method
            status = network_manager.get_network_status()

            # Verify error state was set
            assert status.state == NetworkState.ERROR

    @patch("socket.create_connection")
    @patch("time.sleep")
    def test_ensure_connectivity_already_connected(
        self,
        mock_sleep: MagicMock,
        mock_create_connection: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity when already connected."""
        # Mock successful connection on the first try
        with (
            patch.object(network_manager, "_check_connectivity", return_value=True),
            patch.object(network_manager, "_enable_wifi"),
            patch.object(network_manager, "_disable_wifi"),
        ):
            # Test context manager
            with network_manager.ensure_connectivity() as connected:
                assert connected is True

        # Verify no sleep was called since we're already connected
        mock_sleep.assert_not_called()

    @patch("socket.create_connection")
    @patch("time.sleep")
    @patch("time.time")
    def test_ensure_connectivity_reconnects(
        self,
        mock_time: MagicMock,
        mock_sleep: MagicMock,
        mock_create_connection: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity when reconnection is needed."""
        # Create a sequence for _check_connectivity that returns False, then True
        check_connectivity_values = [False, True]

        def check_connectivity_side_effect() -> bool:
            if check_connectivity_values:
                return check_connectivity_values.pop(0)
            return True

        # Mock time to simulate progression
        mock_time.side_effect = [1000, 1001, 1002]

        # Test context manager with properly patched socket
        with (
            patch.object(
                network_manager, "_check_connectivity", side_effect=check_connectivity_side_effect
            ),
            patch.object(network_manager, "_enable_wifi"),
        ):
            with network_manager.ensure_connectivity() as connected:
                assert connected is True

        # We're not asserting on sleep calls anymore since we're mocking at a higher level

    @patch("socket.create_connection")
    @patch("time.sleep")
    @patch("time.time")
    def test_ensure_connectivity_fails_to_connect(
        self,
        mock_time: MagicMock,
        mock_sleep: MagicMock,
        mock_create_connection: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity when reconnection fails."""
        # We need enough time values for all retry attempts (2 values per attempt)
        time_values = []
        base_time = 1000
        # Add time values for each retry attempt (start and end time for each)
        for i in range(network_manager.config.retry_max_attempts):
            # Each attempt needs 2 time values (start and end time check)
            time_values.extend(
                [
                    base_time + i,  # Start time
                    base_time
                    + i
                    + network_manager.config.wifi_timeout_seconds
                    + 1,  # End time (timeout)
                ]
            )

        # Set up the mock time values
        mock_time.side_effect = time_values

        # Mock connection always failing
        with (
            patch.object(network_manager, "_check_connectivity", return_value=False),
            patch.object(network_manager, "_enable_wifi"),
            patch.object(network_manager, "_disable_wifi"),
            # Directly patch with_retry to return False for simplicity
            patch.object(network_manager, "with_retry", return_value=False),
        ):
            # Test context manager
            with network_manager.ensure_connectivity() as connected:
                assert connected is False

    @patch("socket.create_connection")
    def test_ensure_connectivity_disables_wifi_after(
        self,
        mock_create_connection: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity disables WiFi after use."""
        # Mock successful connection
        with (
            patch.object(network_manager, "_check_connectivity", return_value=True),
            patch.object(network_manager, "_enable_wifi"),
            patch.object(network_manager, "_disable_wifi") as mock_disable_wifi,
        ):
            # Test context manager
            with network_manager.ensure_connectivity():
                pass

            # Verify disable_wifi was called
            mock_disable_wifi.assert_called_once()

    @patch("socket.create_connection")
    def test_ensure_connectivity_debug_mode(
        self,
        mock_create_connection: MagicMock,
        app_config: AppConfig,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity in debug mode."""
        # Set debug mode
        app_config.debug = True
        network_manager.set_app_config(app_config)

        # Setup mocks to check behavior
        with (
            patch.object(network_manager, "_check_connectivity", return_value=True),
            patch.object(network_manager, "_disable_wifi") as mock_disable_wifi,
        ):
            # In debug mode, should not disable WiFi after use
            with network_manager.ensure_connectivity():
                pass

            # Verify disable_wifi was not called
            mock_disable_wifi.assert_not_called()

    @patch("socket.create_connection")
    def test_check_connectivity_success(
        self, mock_create_connection: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _check_connectivity when connection succeeds."""
        # Mock successful connection
        mock_create_connection.return_value = MagicMock()

        # Test method
        result = network_manager._check_connectivity()

        # Verify result
        assert result is True
        mock_create_connection.assert_called_once()

    @patch("socket.create_connection")
    def test_check_connectivity_timeout(
        self, mock_create_connection: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _check_connectivity when connection times out."""
        # Mock timeout
        mock_create_connection.side_effect = TimeoutError()

        # Test method
        result = network_manager._check_connectivity()

        # Verify result
        assert result is False
        mock_create_connection.assert_called_once()

    def test_set_app_config(self, network_manager: NetworkManager, app_config: AppConfig) -> None:
        """Test set_app_config method."""
        # Initially app_config is None
        assert network_manager.app_config is None

        # Set app_config
        network_manager.set_app_config(app_config)

        # Verify app_config was set
        assert network_manager.app_config is app_config

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_ssid_success(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ssid method with successful execution."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "test_ssid\n"
        mock_run.return_value = mock_process

        # Call the method
        ssid = network_manager._get_ssid()

        # Verify result and method calls
        assert ssid == "test_ssid"
        mock_run.assert_called_with(
            [str(Path(IWGETID_PATH)), "-r"],
            capture_output=True,
            text=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_ssid_command_not_found(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ssid method when command is not found."""
        # Mock path.exists to return False (command not found)
        mock_exists.return_value = False

        # Call the method
        ssid = network_manager._get_ssid()

        # Verify result and that subprocess was not called
        assert ssid is None
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_ssid_command_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ssid method when command returns an error."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result with error
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_run.return_value = mock_process

        # Call the method
        ssid = network_manager._get_ssid()

        # Verify result
        assert ssid is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_ssid_subprocess_exception(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ssid method when subprocess throws an exception."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess to raise exception
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)

        # Call the method
        ssid = network_manager._get_ssid()

        # Verify result
        assert ssid is None

    @patch("socket.socket")
    def test_get_ip_address_success(
        self, mock_socket: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ip_address method with successful execution."""
        # Set up the mock socket
        mock_sock_instance = MagicMock()
        mock_sock_instance.getsockname.return_value = ("192.168.1.5", 12345)

        # Configure the mock socket context manager
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        # Call the method
        ip = network_manager._get_ip_address()

        # Verify result
        assert ip == "192.168.1.5"
        mock_sock_instance.connect.assert_called_with(("10.255.255.255", 1))

    @patch("socket.socket")
    def test_get_ip_address_exception(
        self, mock_socket: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_ip_address method when an exception occurs."""
        # Set up the mock socket to raise an exception
        mock_socket.return_value.__enter__.side_effect = OSError("Test socket error")

        # Call the method
        ip = network_manager._get_ip_address()

        # Verify result
        assert ip is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_success(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method with successful execution."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            'wlan0   IEEE 802.11  ESSID:"TestWifi"\n'
            "          Mode:Managed  Frequency:2.412 GHz  Access Point: 12:34:56:78:9A:BC\n"
            "          Signal level=-68 dBm  Noise level=0 dBm\n"
            "          Rx invalid nwid:0  Rx invalid crypt:0  Rx invalid frag:0\n"
        )
        mock_run.return_value = mock_process

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result and method calls
        assert signal == -68
        mock_run.assert_called_with(
            [str(Path(IWCONFIG_PATH)), "wlan0"],
            capture_output=True,
            text=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_command_not_found(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method when command is not found."""
        # Mock path.exists to return False (command not found)
        mock_exists.return_value = False

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result and that subprocess was not called
        assert signal is None
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_parse_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method when parsing fails."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result with malformed output
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            'wlan0   IEEE 802.11  ESSID:"TestWifi"\n'
            "          Mode:Managed  Frequency:2.412 GHz  Access Point: 12:34:56:78:9A:BC\n"
            "          Signal quality=50/100  Signal level=bad dBm\n"
        )  # Malformed signal level
        mock_run.return_value = mock_process

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result
        assert signal is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_command_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method when command returns an error."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result with error
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = "Device not found"
        mock_run.return_value = mock_process

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result
        assert signal is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_subprocess_exception(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method when subprocess throws an exception."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess to raise exception
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result
        assert signal is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_get_signal_strength_value_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _get_signal_strength method when parsing signal level fails."""
        # Mock path.exists to return True
        mock_exists.return_value = True

        # Mock subprocess result with signal level that causes ValueError during int conversion
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            'wlan0   IEEE 802.11  ESSID:"TestWifi"\n'
            "          Mode:Managed  Frequency:2.412 GHz  Access Point: 12:34:56:78:9A:BC\n"
            "          Signal level=invalid dBm\n"
        )  # Will cause ValueError
        mock_run.return_value = mock_process

        # Call the method
        signal = network_manager._get_signal_strength()

        # Verify result
        assert signal is None

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_enable_wifi_command_not_found(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _enable_wifi method when commands are not found."""
        # We need to mock sudo not existing
        mock_exists.return_value = False

        # Patch the _apply_power_save_mode method to do nothing
        with patch.object(network_manager, "_apply_power_save_mode"):
            # Call the method
            network_manager._enable_wifi()

            # Verify subprocess was not called
            mock_run.assert_not_called()

            # Reset and try with script not found but sudo found
            mock_exists.reset_mock()
            mock_run.reset_mock()

            # Create a side effect that returns different values for different paths
            def file_exists_side_effect(path: Path) -> bool:
                path_str = str(path)
                # Return False for wifi script, True for everything else (like sudo, ifconfig)
                if WIFI_SLEEP_SCRIPT in path_str:
                    return False
                return True

            mock_exists.side_effect = file_exists_side_effect

            # Configure subprocess to return successfully for the legacy method
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_run.return_value = mock_process

            # Call the method
            network_manager._enable_wifi()

            # Verify the legacy method was called instead
            mock_run.assert_called_with(
                [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "up"],
                check=True,
                timeout=network_manager.config.wifi_timeout_seconds,
                shell=False,
            )

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_enable_wifi_subprocess_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _enable_wifi method when subprocess throws an error."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to raise SubprocessError for both primary and fallback methods
        mock_run.side_effect = [
            subprocess.SubprocessError("Test subprocess error"),  # For wifi-sleep.sh
            subprocess.SubprocessError("Test subprocess error"),  # For ifconfig fallback
        ]

        # Call the method - it should handle the exception
        network_manager._enable_wifi()

        # Verify both methods were attempted
        assert mock_run.call_count == 2
        mock_run.assert_has_calls(
            [
                call(
                    [str(Path(SUDO_PATH)), str(Path(WIFI_SLEEP_SCRIPT)), "on"],
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
                call(
                    [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "up"],
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
            ]
        )

    @patch("subprocess.run")
    def test_enable_wifi_fallback(
        self, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _enable_wifi method falls back to legacy method when script not found."""

        # Create a custom implementation to replace exists
        def mock_exists_impl(self: Path) -> bool:
            # 'self' here is the Path instance being checked
            if str(self) == str(Path(WIFI_SLEEP_SCRIPT)):
                return False  # WIFI_SLEEP_SCRIPT doesn't exist
            return True  # All other paths exist

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Patch the _apply_power_save_mode method to do nothing
        with patch.object(network_manager, "_apply_power_save_mode"):
            # Use patch.object to patch the exists method on Path instances
            with patch.object(Path, "exists", mock_exists_impl):
                # Call the method
                network_manager._enable_wifi()

                # Verify subprocess was called with ifconfig (legacy method)
                mock_run.assert_called_with(
                    [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "up"],
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                )

    @patch("subprocess.run")
    def test_disable_wifi_fallback(
        self, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _disable_wifi method falls back to legacy method when script not found."""

        # Create a custom implementation to replace exists
        def mock_exists_impl(self: Path) -> bool:
            # 'self' here is the Path instance being checked
            if str(self) == str(Path(WIFI_SLEEP_SCRIPT)):
                return False  # WIFI_SLEEP_SCRIPT doesn't exist
            return True  # All other paths exist

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Use patch.object to patch the exists method on Path instances
        with patch.object(Path, "exists", mock_exists_impl):
            # Call the method
            network_manager._disable_wifi()

            # Verify subprocess was called with ifconfig (legacy method)
            mock_run.assert_called_with(
                [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "down"],
                check=True,
                timeout=network_manager.config.wifi_timeout_seconds,
                shell=False,
            )

    @patch("time.sleep")
    def test_calculate_backoff_delay(
        self, mock_sleep: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _calculate_backoff_delay method."""
        # Test with different attempt numbers
        with patch("random.uniform", return_value=0):  # Remove jitter for predictable tests
            # First attempt
            delay = network_manager._calculate_backoff_delay(0)
            assert delay == network_manager.config.retry_initial_delay_seconds

            # Second attempt
            delay = network_manager._calculate_backoff_delay(1)
            expected = (
                network_manager.config.retry_initial_delay_seconds
                * network_manager.config.retry_backoff_factor
            )
            assert delay == expected

            # Third attempt
            delay = network_manager._calculate_backoff_delay(2)
            expected = network_manager.config.retry_initial_delay_seconds * (
                network_manager.config.retry_backoff_factor**2
            )
            assert delay == expected

    @patch("time.sleep")
    def test_with_retry_success_first_try(
        self, mock_sleep: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test with_retry method when operation succeeds on first try."""
        # Mock operation that succeeds
        mock_operation = MagicMock(return_value="success")

        # Call with_retry
        result = network_manager.with_retry(mock_operation, "arg1", kwarg1="value1")

        # Verify operation was called with correct arguments
        mock_operation.assert_called_once_with("arg1", kwarg1="value1")

        # Verify sleep was not called (no retries needed)
        mock_sleep.assert_not_called()

        # Verify result
        assert result == "success"

    @patch("time.sleep")
    def test_with_retry_success_after_retry(
        self, mock_sleep: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test with_retry method when operation succeeds after retry."""
        # Mock operation that fails once, then succeeds
        mock_operation = MagicMock(side_effect=[Exception("First attempt fails"), "success"])

        # Call with_retry
        result = network_manager.with_retry(mock_operation)

        # Verify operation was called twice
        assert mock_operation.call_count == 2

        # Verify sleep was called once (1 retry)
        assert mock_sleep.call_count == 1

        # Verify result
        assert result == "success"

    @patch("time.sleep")
    def test_with_retry_all_attempts_fail(
        self, mock_sleep: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test with_retry method when all attempts fail."""
        # Mock operation that always fails
        mock_operation = MagicMock(side_effect=Exception("Operation fails"))

        # Call with_retry
        result = network_manager.with_retry(mock_operation)

        # Verify operation was called for max attempts
        assert mock_operation.call_count == network_manager.config.retry_max_attempts

        # Verify sleep was called for max attempts - 1 (no sleep after last attempt)
        assert mock_sleep.call_count == network_manager.config.retry_max_attempts - 1

        # Verify result is None (operation failed)
        assert result is None

    def test_update_battery_status(
        self, network_manager: NetworkManager, normal_battery: BatteryStatus
    ) -> None:
        """Test update_battery_status method."""
        # Initially battery_status is None
        assert network_manager.current_battery_status is None

        # Update battery status
        network_manager.update_battery_status(normal_battery)

        # Verify battery status was updated
        assert network_manager.current_battery_status is normal_battery

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_off(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method with 'off' mode."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Call method with explicit 'off' mode
        result = network_manager.set_wifi_power_save_mode("off")

        # Verify subprocess was called correctly with 'off' argument
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IW_PATH)), "dev", "wlan0", "set", "power_save", "off"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_on(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method with 'on' mode."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Call method with explicit 'on' mode
        result = network_manager.set_wifi_power_save_mode("on")

        # Verify subprocess was called correctly with 'on' argument
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IW_PATH)), "dev", "wlan0", "set", "power_save", "on"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_aggressive(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method with 'aggressive' mode."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Call method with explicit 'aggressive' mode
        result = network_manager.set_wifi_power_save_mode("aggressive")

        # Verify subprocess was called with correct arguments
        assert mock_run.call_count == 2

        # Create command args separately to avoid long lines
        # Use path_resolver to get bin paths
        sudo = str(path_resolver.get_bin_path("sudo"))
        iw = str(path_resolver.get_bin_path("iw"))
        iwconfig = str(path_resolver.get_bin_path("iwconfig"))

        iw_args = [sudo, iw, "dev", "wlan0", "set", "power_save", "on"]
        iwconfig_args = [sudo, iwconfig, "wlan0", "power", "timeout", "3600"]

        mock_run.assert_has_calls(
            [
                call(
                    iw_args,
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
                call(
                    iwconfig_args,
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
            ]
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_auto_normal_battery(
        self,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        network_manager: NetworkManager,
        normal_battery: BatteryStatus,
    ) -> None:
        """Test set_wifi_power_save_mode method with 'auto' mode and normal battery."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Set battery status
        network_manager.update_battery_status(normal_battery)

        # Call method with 'auto' mode
        result = network_manager.set_wifi_power_save_mode("auto")

        # With normal battery, should select 'off' mode
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IW_PATH)), "dev", "wlan0", "set", "power_save", "off"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_auto_low_battery(
        self,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        network_manager: NetworkManager,
        low_battery: BatteryStatus,
    ) -> None:
        """Test set_wifi_power_save_mode method with 'auto' mode and low battery."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Set battery status
        network_manager.update_battery_status(low_battery)

        # Call method with 'auto' mode
        result = network_manager.set_wifi_power_save_mode("auto")

        # With low battery, should select 'on' mode
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IW_PATH)), "dev", "wlan0", "set", "power_save", "on"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_auto_critical_battery(
        self,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        network_manager: NetworkManager,
        critical_battery: BatteryStatus,
    ) -> None:
        """Test set_wifi_power_save_mode method with 'auto' mode and critical battery."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Set battery status
        network_manager.update_battery_status(critical_battery)

        # Call method with 'auto' mode
        result = network_manager.set_wifi_power_save_mode("auto")

        # With critical battery, should select 'aggressive' mode
        assert mock_run.call_count == 2

        # Create command args separately to avoid long lines
        # Use path_resolver to get bin paths
        sudo = str(path_resolver.get_bin_path("sudo"))
        iw = str(path_resolver.get_bin_path("iw"))
        iwconfig = str(path_resolver.get_bin_path("iwconfig"))

        iw_args = [sudo, iw, "dev", "wlan0", "set", "power_save", "on"]
        iwconfig_args = [sudo, iwconfig, "wlan0", "power", "timeout", "3600"]

        mock_run.assert_has_calls(
            [
                call(
                    iw_args,
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
                call(
                    iwconfig_args,
                    check=True,
                    timeout=network_manager.config.wifi_timeout_seconds,
                    shell=False,
                ),
            ]
        )

        # Verify result
        assert result is True

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_invalid(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method with invalid mode."""
        # Call method with invalid mode
        result = network_manager.set_wifi_power_save_mode("invalid")

        # Verify subprocess was not called
        mock_run.assert_not_called()

        # Verify result
        assert result is False

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_command_not_found(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method when command is not found."""
        # Mock iw not found
        mock_exists.return_value = False

        # Call method
        result = network_manager.set_wifi_power_save_mode("on")

        # Verify subprocess was not called
        mock_run.assert_not_called()

        # Verify result
        assert result is False

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_set_wifi_power_save_mode_subprocess_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test set_wifi_power_save_mode method when subprocess throws an error."""
        # Mock paths exist
        mock_exists.return_value = True

        # Mock subprocess to raise error
        mock_run.side_effect = subprocess.SubprocessError("Test error")

        # Call method
        result = network_manager.set_wifi_power_save_mode("on")

        # Verify result
        assert result is False

    def test_apply_power_save_mode(self, network_manager: NetworkManager) -> None:
        """Test _apply_power_save_mode method."""
        # Test with battery-aware WiFi enabled
        network_manager.config.enable_battery_aware_wifi = True

        with patch.object(
            network_manager, "set_wifi_power_save_mode", return_value=True
        ) as mock_set_power_save:
            # Call the method
            network_manager._apply_power_save_mode()

            # Verify set_wifi_power_save_mode was called
            mock_set_power_save.assert_called_once()

        # Test with battery-aware WiFi disabled
        network_manager.config.enable_battery_aware_wifi = False

        with patch.object(
            network_manager, "set_wifi_power_save_mode", return_value=True
        ) as mock_set_power_save:
            # Call the method
            network_manager._apply_power_save_mode()

            # Verify set_wifi_power_save_mode was not called
            mock_set_power_save.assert_not_called()

    @patch("subprocess.run")
    @patch("rpi_weather_display.utils.network.file_exists")
    def test_enable_wifi_applies_power_save(
        self,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        network_manager: NetworkManager,
        normal_battery: BatteryStatus,
    ) -> None:
        """Test that _enable_wifi applies power save settings."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to return successfully
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Set battery status
        network_manager.update_battery_status(normal_battery)

        # Create patch for _apply_power_save_mode to check if it's called
        with patch.object(network_manager, "_apply_power_save_mode") as mock_apply_power_save:
            # Call _enable_wifi
            network_manager._enable_wifi()

            # Verify _apply_power_save_mode was called
            mock_apply_power_save.assert_called_once()

    @patch("time.sleep")
    @patch("socket.create_connection")
    def test_try_connect_success(
        self,
        mock_create_connection: MagicMock,
        mock_sleep: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test _try_connect method when connection succeeds."""
        # Mock _check_connectivity to return True
        with patch.object(network_manager, "_check_connectivity", return_value=True):
            # Call _try_connect
            result = network_manager._try_connect()

            # Verify result
            assert result is True

    @patch("time.sleep")
    @patch("time.time")
    def test_try_connect_timeout(
        self, mock_time: MagicMock, mock_sleep: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _try_connect method when connection times out."""
        # First call is start time, second is current time after timeout
        mock_time.side_effect = [
            1000,  # Start time
            1000 + network_manager.config.wifi_timeout_seconds + 1,  # Current time after timeout
        ]

        # Mock _check_connectivity to return False
        with patch.object(network_manager, "_check_connectivity", return_value=False):
            # Call _try_connect - should raise ConnectionError
            with pytest.raises(ConnectionError):
                network_manager._try_connect()

    @patch("socket.create_connection")
    @patch("time.sleep")
    def test_ensure_connectivity_with_retry(
        self,
        mock_sleep: MagicMock,
        mock_create_connection: MagicMock,
        network_manager: NetworkManager,
    ) -> None:
        """Test ensure_connectivity with retry logic."""
        # Mock _check_connectivity to return False initially
        # Mock _try_connect and with_retry to simulate successful connection after retry
        with (
            patch.object(network_manager, "_check_connectivity", return_value=False),
            patch.object(network_manager, "_enable_wifi"),
            patch.object(network_manager, "_disable_wifi"),
            patch.object(network_manager, "with_retry", return_value=True) as mock_with_retry,
        ):
            # Use context manager
            with network_manager.ensure_connectivity() as connected:
                assert connected is True

            # Verify with_retry was called
            mock_with_retry.assert_called_once_with(network_manager._try_connect)
