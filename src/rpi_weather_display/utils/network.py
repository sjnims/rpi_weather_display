# pyright: reportGeneralTypeIssues=false
# security: ignore=subprocess

import logging
import socket
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from rpi_weather_display.models.config import AppConfig, PowerConfig
from rpi_weather_display.models.system import NetworkState, NetworkStatus

# Define absolute paths for executables to avoid partial path security issues
IWGETID_PATH = "/sbin/iwgetid"
IWCONFIG_PATH = "/sbin/iwconfig"
IFCONFIG_PATH = "/sbin/ifconfig"
SUDO_PATH = "/usr/bin/sudo"


class NetworkManager:
    """Utility for managing network connectivity."""

    def __init__(self, config: PowerConfig) -> None:
        """Initialize the network manager.

        Args:
            config: Power management configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.app_config = None  # Will hold reference to AppConfig if available

    def set_app_config(self, app_config: AppConfig) -> None:
        """Set reference to the app config for debug mode check.

        Args:
            app_config: The application configuration.
        """
        self.app_config = app_config

    def get_network_status(self) -> NetworkStatus:
        """Get current network status.

        Returns:
            NetworkStatus object with current network information.
        """
        try:
            # Check if we have network connectivity
            connected = self._check_connectivity()

            if connected:
                # Get network details
                ssid = self._get_ssid()
                ip_address = self._get_ip_address()
                signal_strength = self._get_signal_strength()

                return NetworkStatus(
                    state=NetworkState.CONNECTED,
                    ssid=ssid,
                    ip_address=ip_address,
                    signal_strength=signal_strength,
                    last_connection=datetime.fromtimestamp(time.time()),
                )
            else:
                return NetworkStatus(state=NetworkState.DISCONNECTED)
        except Exception as e:
            self.logger.error(f"Error getting network status: {e}")
            return NetworkStatus(state=NetworkState.ERROR)

    def _check_connectivity(self) -> bool:
        """Check if we have internet connectivity.

        Returns:
            True if connected, False otherwise.
        """
        try:
            # Try to connect to a reliable host (Google DNS)
            socket.create_connection(("8.8.8.8", 53), timeout=self.config.wifi_timeout_seconds)
            return True
        except (TimeoutError, OSError):
            return False

    def _get_ssid(self) -> str | None:
        """Get the current SSID.

        Returns:
            SSID as string, or None if not connected or error.
        """
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            cmd_path = Path(IWGETID_PATH)
            if not cmd_path.exists():
                self.logger.warning(f"Command not found: {IWGETID_PATH}")
                return None

            result = subprocess.run(  # nosec # noqa: S603
                [str(cmd_path), "-r"],  # Fixed command with full path
                capture_output=True,
                text=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None

    def _get_ip_address(self) -> str | None:
        """Get the current IP address.

        Returns:
            IP address as string, or None if not connected or error.
        """
        try:
            # Create a socket to get the IP address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Doesn't need to be reachable
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            return ip
        except Exception:
            return None

    def _get_signal_strength(self) -> int | None:
        """Get the current WiFi signal strength.

        Returns:
            Signal strength in dBm, or None if not connected or error.
        """
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            cmd_path = Path(IWCONFIG_PATH)
            if not cmd_path.exists():
                self.logger.warning(f"Command not found: {IWCONFIG_PATH}")
                return None

            result = subprocess.run(  # nosec # noqa: S603
                [str(cmd_path), "wlan0"],  # Fixed command with full path
                capture_output=True,
                text=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Signal level" in line:
                        # Extract signal level (dBm)
                        parts = line.split("Signal level=")
                        if len(parts) > 1:
                            signal = parts[1].split(" ")[0]
                            return int(signal.replace("dBm", ""))
            return None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError, IndexError):
            return None

    @contextmanager
    def ensure_connectivity(self) -> Generator[bool, None, None]:
        """Context manager to ensure network connectivity.

        Yields:
            True if connected, False otherwise.
        """
        # Try to enable WiFi if it's not already enabled
        connected = self._check_connectivity()

        if not connected:
            self.logger.info("Not connected, attempting to enable WiFi")
            self._enable_wifi()

            # Wait for connection
            start_time = time.time()
            while time.time() - start_time < self.config.wifi_timeout_seconds:
                if self._check_connectivity():
                    connected = True
                    self.logger.info("Successfully connected to WiFi")
                    break
                time.sleep(1)

        try:
            yield connected
        finally:
            # If we're in power-saving mode, disable WiFi after use
            # Only disable if app_config exists and debug mode is off
            if self.app_config is None or not self.app_config.debug:
                self._disable_wifi()

    def _enable_wifi(self) -> None:
        """Enable WiFi."""
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = Path(SUDO_PATH)
            ifconfig_path = Path(IFCONFIG_PATH)

            if not sudo_path.exists() or not ifconfig_path.exists():
                self.logger.warning("Commands not found for enabling WiFi")
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(ifconfig_path), "wlan0", "up"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface enabled")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to enable WiFi: {e}")

    def _disable_wifi(self) -> None:
        """Disable WiFi to save power."""
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = Path(SUDO_PATH)
            ifconfig_path = Path(IFCONFIG_PATH)

            if not sudo_path.exists() or not ifconfig_path.exists():
                self.logger.warning("Commands not found for disabling WiFi")
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(ifconfig_path), "wlan0", "down"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface disabled to save power")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to disable WiFi: {e}")
