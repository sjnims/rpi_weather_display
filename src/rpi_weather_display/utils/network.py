"""Network management utilities for the Raspberry Pi weather display.

Provides functionality for checking network connectivity, managing WiFi power
states, and retrieving network information for power-efficient operation.
"""

import logging
import random
import socket
import subprocess
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from rpi_weather_display.constants import (
    BROADCAST_IP,
    BROADCAST_PORT,
    GOOGLE_DNS,
    GOOGLE_DNS_PORT,
    WIFI_SLEEP_SCRIPT,
)
from rpi_weather_display.models.config import AppConfig, PowerConfig
from rpi_weather_display.models.system import BatteryStatus, NetworkState, NetworkStatus
from rpi_weather_display.utils.file_utils import file_exists
from rpi_weather_display.utils.path_utils import path_resolver


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
        self.current_battery_status = None  # Will hold current battery status if available

    def set_app_config(self, app_config: AppConfig) -> None:
        """Set reference to the app config for debug mode check.

        Args:
            app_config: The application configuration.
        """
        self.app_config = app_config

    def update_battery_status(self, battery_status: BatteryStatus) -> None:
        """Update the current battery status for battery-aware WiFi management.

        Args:
            battery_status: Current battery status information
        """
        self.current_battery_status = battery_status

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
            socket.create_connection(
                (GOOGLE_DNS, GOOGLE_DNS_PORT), timeout=self.config.wifi_timeout_seconds
            )
            return True
        except (TimeoutError, OSError):
            return False

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff.

        Implements an exponential backoff algorithm with jitter to determine the
        wait time between retry attempts. The algorithm uses the formula:
        delay = initial_delay * (backoff_factor ^ attempt) * (1 + random_jitter)

        This approach helps prevent multiple clients from retrying simultaneously
        (avoiding the "thundering herd" problem) and gradually increases wait times
        for persistent failures.

        Args:
            attempt: The current attempt number (0-based)

        Returns:
            Delay in seconds for the next retry, with an upper limit defined by
            retry_max_delay_seconds from the config and a lower limit of 0.1 seconds.
        """
        # Calculate base delay with exponential backoff
        delay = self.config.retry_initial_delay_seconds * (
            self.config.retry_backoff_factor**attempt
        )

        # Apply maximum delay cap
        delay = min(delay, self.config.retry_max_delay_seconds)

        # Add jitter to avoid thundering herd problem
        jitter = random.uniform(  # noqa: S311
            -self.config.retry_jitter_factor, self.config.retry_jitter_factor
        )
        delay = delay * (1 + jitter)

        return max(0.1, delay)  # Ensure delay is positive

    def with_retry(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        """Execute an operation with exponential backoff retries.

        Attempts to execute the provided function repeatedly until it succeeds
        or the maximum number of retry attempts is reached. Uses exponential
        backoff between attempts to avoid overwhelming the system.

        Args:
            operation: The function to retry
            *args: Positional arguments to pass to the operation function
            **kwargs: Keyword arguments to pass to the operation function

        Returns:
            Result of the operation if successful, or None if all attempts fail
        """
        attempt = 0

        while attempt < self.config.retry_max_attempts:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                attempt += 1
                if attempt >= self.config.retry_max_attempts:
                    self.logger.error(f"Operation failed after {attempt} attempts: {e!s}")
                    return None

                delay = self._calculate_backoff_delay(attempt)
                self.logger.info(
                    f"Retry attempt {attempt}/{self.config.retry_max_attempts} "
                    f"after {delay:.2f}s: {e!s}"
                )
                time.sleep(delay)

        return None

    def _get_ssid(self) -> str | None:
        """Get the current SSID.

        Returns:
            SSID as string, or None if not connected or error.
        """
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            cmd_path = path_resolver.get_bin_path("iwgetid")
            if not file_exists(cmd_path):
                self.logger.warning(f"Command not found: {cmd_path}")
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
                s.connect((BROADCAST_IP, BROADCAST_PORT))
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
            cmd_path = path_resolver.get_bin_path("iwconfig")
            if not file_exists(cmd_path):
                self.logger.warning(f"Command not found: {cmd_path}")
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

            # Try to establish connection with exponential backoff
            connected = self.with_retry(self._try_connect)
            if connected:
                self.logger.info("Successfully connected to WiFi")
            else:
                self.logger.warning("Failed to connect to WiFi after multiple attempts")

        try:
            yield connected
        finally:
            # If we're in power-saving mode, disable WiFi after use
            # Only disable if app_config exists and debug mode is off
            if self.app_config is None or not self.app_config.debug:
                self._disable_wifi()

    def _try_connect(self) -> bool:
        """Try to establish network connectivity.

        Attempts to establish a network connection by repeatedly checking for
        connectivity within the timeout period specified in the configuration.

        Returns:
            True if connected, False otherwise.

        Raises:
            ConnectionError: If connection cannot be established within the timeout period.
        """
        # Wait for connection
        start_time = time.time()
        while time.time() - start_time < self.config.wifi_timeout_seconds:
            if self._check_connectivity():
                return True
            time.sleep(1)

        # If we reach here, connection failed
        raise ConnectionError("Failed to establish network connection")

    def _enable_wifi(self) -> None:
        """Enable WiFi."""
        try:
            # Use wifi-sleep.sh script for better power management
            sudo_path = path_resolver.get_bin_path("sudo")
            wifi_script = path_resolver.normalize_path(WIFI_SLEEP_SCRIPT)

            if not file_exists(sudo_path) or not file_exists(wifi_script):
                self.logger.warning(
                    f"Required commands not found: sudo={file_exists(sudo_path)}, "
                    f"wifi-sleep.sh={file_exists(wifi_script)}"
                )
                # Fall back to old method if script doesn't exist
                self._enable_wifi_legacy()
                return

            # Call the wifi-sleep.sh script to enable WiFi
            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(wifi_script), "on"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface enabled with power saving")

            # Apply battery-aware power save mode if enabled
            # We do this in a separate method call to avoid test failures
            self._apply_power_save_mode()

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to enable WiFi: {e}")
            # Try legacy method as fallback
            self._enable_wifi_legacy()

    def _enable_wifi_legacy(self) -> None:
        """Enable WiFi using legacy ifconfig method as fallback."""
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = path_resolver.get_bin_path("sudo")
            ifconfig_path = path_resolver.get_bin_path("ifconfig")

            if not file_exists(sudo_path) or not file_exists(ifconfig_path):
                self.logger.warning("Commands not found for enabling WiFi")
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(ifconfig_path), "wlan0", "up"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface enabled (legacy method)")

            # Apply battery-aware power save mode if enabled
            # We do this in a separate method call to avoid test failures
            self._apply_power_save_mode()

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to enable WiFi (legacy method): {e}")

    def _apply_power_save_mode(self) -> None:
        """Apply battery-aware power save mode if enabled.

        This is separated from the enable methods to help with testing.
        """
        if self.config.enable_battery_aware_wifi:
            self.set_wifi_power_save_mode()

    def _disable_wifi(self) -> None:
        """Disable WiFi to save power."""
        try:
            # Use wifi-sleep.sh script for better power management
            sudo_path = path_resolver.get_bin_path("sudo")
            wifi_script = path_resolver.normalize_path(WIFI_SLEEP_SCRIPT)

            if not file_exists(sudo_path) or not file_exists(wifi_script):
                self.logger.warning(
                    f"Required commands not found: sudo={file_exists(sudo_path)}, "
                    f"wifi-sleep.sh={file_exists(wifi_script)}"
                )
                # Fall back to old method if script doesn't exist
                self._disable_wifi_legacy()
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(wifi_script), "off"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface disabled with rfkill to save power")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to disable WiFi: {e}")
            # Try legacy method as fallback
            self._disable_wifi_legacy()

    def _disable_wifi_legacy(self) -> None:
        """Disable WiFi using legacy ifconfig method as fallback."""
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = path_resolver.get_bin_path("sudo")
            ifconfig_path = path_resolver.get_bin_path("ifconfig")

            if not file_exists(sudo_path) or not file_exists(ifconfig_path):
                self.logger.warning("Commands not found for disabling WiFi")
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(ifconfig_path), "wlan0", "down"],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )
            self.logger.info("WiFi interface disabled to save power (legacy method)")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to disable WiFi (legacy method): {e}")

    def set_wifi_power_save_mode(self, mode: str | None = None) -> bool:
        """Set WiFi power save mode based on battery level.

        This method configures the power save mode of the WiFi adapter using
        the iw command. Different power save modes have different power/performance
        tradeoffs:

        - "off": Disables power saving (best performance, highest power consumption)
        - "on": Basic power saving (good performance, medium power consumption)
        - "aggressive": Aggressive power saving (reduced performance, lowest power consumption)
        - "auto": Automatically select based on battery status

        Args:
            mode: Power save mode to set, or None to use the configured default

        Returns:
            True if power save mode was set successfully, False otherwise
        """
        # Default to config if not specified
        if mode is None:
            mode = self.config.wifi_power_save_mode

        # If mode is "auto", select appropriate mode based on battery status
        if mode == "auto" and self.config.enable_battery_aware_wifi:
            # Default to "on" if battery status is not available
            if self.current_battery_status is None:
                mode = "on"
            # Use aggressive power saving when battery is critically low
            elif self.current_battery_status.level <= self.config.critical_battery_threshold:
                mode = "aggressive"
            # Use regular power saving when battery is low
            elif self.current_battery_status.level <= self.config.low_battery_threshold:
                mode = "on"
            # Disable power saving when battery is good
            else:
                mode = "off"

        # Ensure mode is valid
        if mode not in ["off", "on", "aggressive"]:
            self.logger.error(f"Invalid power save mode: {mode}")
            return False

        try:
            # Check if iw command is available
            iw_path = path_resolver.get_bin_path("iw")
            sudo_path = path_resolver.get_bin_path("sudo")

            if not file_exists(iw_path) or not file_exists(sudo_path):
                self.logger.warning(
                    f"Required commands not found: sudo={file_exists(sudo_path)}, "
                    f"iw={file_exists(iw_path)}"
                )
                return False

            # Map modes to iw command arguments
            mode_arg = "off" if mode == "off" else "on"

            # Run iw command to set power save mode
            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(iw_path), "dev", "wlan0", "set", "power_save", mode_arg],
                check=True,
                timeout=self.config.wifi_timeout_seconds,
                shell=False,  # Explicitly disable shell
            )

            # If using aggressive mode, we need additional settings
            if mode == "aggressive":
                # Set beacon interval to maximum to reduce wakeups
                iwconfig_path = path_resolver.get_bin_path("iwconfig")
                subprocess.run(  # nosec # noqa: S603
                    [str(sudo_path), str(iwconfig_path), "wlan0", "power", "timeout", "3600"],
                    check=True,
                    timeout=self.config.wifi_timeout_seconds,
                    shell=False,
                )

            self.logger.info(f"WiFi power save mode set to '{mode}'")
            return True

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to set WiFi power save mode: {e}")
            return False
