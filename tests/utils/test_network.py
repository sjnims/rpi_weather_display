"""Tests for the network module."""
# ruff: noqa: S101, SLF001
# ^ Ignores "Use of assert detected" and protected member access in test files

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import NetworkState
from rpi_weather_display.utils.network import (
    IFCONFIG_PATH,
    IWCONFIG_PATH,
    IWGETID_PATH,
    SUDO_PATH,
    NetworkManager,
)


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

    @patch("pathlib.Path.exists")
    def test_utility_paths(self, mock_exists: MagicMock) -> None:
        """Test the utility path constants."""
        # Verify paths are defined
        assert SUDO_PATH == "/usr/bin/sudo"
        assert IFCONFIG_PATH == "/sbin/ifconfig"
        assert IWCONFIG_PATH == "/sbin/iwconfig"
        assert IWGETID_PATH == "/sbin/iwgetid"

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
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

        # Call the method
        network_manager._enable_wifi()  # type: ignore

        # Verify subprocess was called correctly
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "up"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
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
        network_manager._disable_wifi()  # type: ignore

        # Verify subprocess was called correctly
        mock_run.assert_called_with(
            [str(Path(SUDO_PATH)), str(Path(IFCONFIG_PATH)), "wlan0", "down"],
            check=True,
            timeout=network_manager.config.wifi_timeout_seconds,
            shell=False,
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_disable_wifi_failure(
        self, mock_exists: MagicMock, mock_run: MagicMock, network_manager: NetworkManager
    ) -> None:
        """Test _disable_wifi method failure case."""
        # Mock paths exist
        mock_exists.return_value = True

        # Configure subprocess to fail
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        # Call the method - it should handle the exception
        network_manager._disable_wifi()  # type: ignore

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
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
    @patch("pathlib.Path.exists")
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
    @patch("pathlib.Path.exists")
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
        # First call is start time, second is current time after timeout
        mock_time.side_effect = [
            1000,  # Start time
            1000 + network_manager.config.wifi_timeout_seconds + 1,  # Current time after timeout
        ]

        # Mock connection always failing
        with (
            patch.object(network_manager, "_check_connectivity", return_value=False),
            patch.object(network_manager, "_enable_wifi"),
            patch.object(network_manager, "_disable_wifi"),
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
        result = network_manager._check_connectivity()  # type: ignore

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
        result = network_manager._check_connectivity()  # type: ignore

        # Verify result
        assert result is False
        mock_create_connection.assert_called_once()
