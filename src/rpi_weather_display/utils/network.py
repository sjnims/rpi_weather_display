"""Async network management utilities for the Raspberry Pi weather display.

Provides async/await functionality for checking network connectivity, managing
WiFi power states, and retrieving network information for power-efficient operation.
This module enables non-blocking network operations that allow the CPU to enter
low-power states while waiting for network I/O.
"""

import asyncio
import logging
import random
import socket
import subprocess
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TypeVar

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

# Type variable for generic retry operations
T = TypeVar("T")


class AsyncNetworkManager:
    """Async utility for managing network connectivity.

    This class provides async versions of network management operations,
    allowing for non-blocking I/O that improves power efficiency by letting
    the CPU sleep during network waits.

    Key improvements over synchronous version:
    - Async context managers for automatic resource management
    - Non-blocking network checks
    - Concurrent operation support
    - Better integration with async client code
    """

    def __init__(self, config: PowerConfig) -> None:
        """Initialize the async network manager.

        Args:
            config: Power management configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.app_config = None  # Will hold reference to AppConfig if available
        self.current_battery_status = None  # Will hold current battery status if available

        # Semaphore to limit concurrent subprocess operations
        self._subprocess_semaphore = asyncio.Semaphore(3)

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

    async def get_network_status(self) -> NetworkStatus:
        """Get current network status asynchronously.

        Returns:
            NetworkStatus object with current network information.
        """
        try:
            # Check if we have network connectivity (async)
            connected = await self._check_connectivity()

            match connected:
                case True:
                    # Get network details concurrently
                    ssid_task = asyncio.create_task(self._get_ssid())
                    ip_task = asyncio.create_task(self._get_ip_address())
                    signal_task = asyncio.create_task(self._get_signal_strength())

                    # Wait for all tasks to complete
                    ssid, ip_address, signal_strength = await asyncio.gather(
                        ssid_task, ip_task, signal_task
                    )

                    return NetworkStatus(
                        state=NetworkState.CONNECTED,
                        ssid=ssid,
                        ip_address=ip_address,
                        signal_strength=signal_strength,
                        last_connection=datetime.fromtimestamp(time.time()),
                    )
                case False:
                    return NetworkStatus(state=NetworkState.DISCONNECTED)
        except Exception as e:
            self.logger.error(f"Error getting network status: {e}")
            return NetworkStatus(state=NetworkState.ERROR)

    async def _check_connectivity(self) -> bool:
        """Check if we have internet connectivity asynchronously.

        Uses asyncio's socket operations for non-blocking connectivity checks.

        Returns:
            True if connected, False otherwise.
        """
        try:
            # Create a socket and attempt connection asynchronously
            loop = asyncio.get_event_loop()

            # Run socket connection in executor to make it async
            def try_connect() -> bool:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.config.wifi_timeout_seconds)
                    result = sock.connect_ex((GOOGLE_DNS, GOOGLE_DNS_PORT))
                    sock.close()
                    return result == 0
                except Exception:
                    return False

            # Run in thread pool to avoid blocking
            return await loop.run_in_executor(None, try_connect)

        except Exception as e:
            match type(e).__name__:
                case "TimeoutError" | "OSError":
                    return False
                case _:
                    # Re-raise unexpected exceptions
                    raise

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff.

        Same implementation as synchronous version as this is a pure calculation.

        Args:
            attempt: The current attempt number (0-based)

        Returns:
            Delay in seconds for the next retry.
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

    async def with_retry(
        self, operation: Callable[..., Awaitable[T]], *args: object, **kwargs: object
    ) -> T | None:
        """Execute an async operation with exponential backoff retries.

        Attempts to execute the provided async function repeatedly until it succeeds
        or the maximum number of retry attempts is reached. Uses exponential
        backoff between attempts to avoid overwhelming the system.

        Args:
            operation: The async function to retry
            *args: Positional arguments to pass to the operation function
            **kwargs: Keyword arguments to pass to the operation function

        Returns:
            Result of the operation if successful, or None if all attempts fail
        """
        attempt = 0

        while attempt < self.config.retry_max_attempts:
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                attempt += 1
                match attempt >= self.config.retry_max_attempts:
                    case True:
                        self.logger.error(f"Operation failed after {attempt} attempts: {e!s}")
                        return None
                    case False:
                        delay = self._calculate_backoff_delay(attempt)
                        self.logger.info(
                            f"Retry attempt {attempt}/{self.config.retry_max_attempts} "
                            f"after {delay:.2f}s: {e!s}"
                        )
                        await asyncio.sleep(delay)

        return None

    async def _run_subprocess(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a subprocess command asynchronously.

        Uses asyncio's subprocess support for non-blocking command execution.

        Args:
            cmd: Command and arguments to execute

        Returns:
            Completed process result
        """
        async with self._subprocess_semaphore:
            # Create subprocess
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.config.wifi_timeout_seconds
                )

                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=proc.returncode or 0,
                    stdout=stdout.decode() if stdout else "",
                    stderr=stderr.decode() if stderr else "",
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                raise subprocess.TimeoutExpired(cmd, self.config.wifi_timeout_seconds) from None

    async def _get_ssid(self) -> str | None:
        """Get the current SSID asynchronously.

        Returns:
            SSID as string, or None if not connected or error.
        """
        try:
            cmd_path = path_resolver.get_bin_path("iwgetid")
            if not file_exists(cmd_path):
                self.logger.warning(f"Command not found: {cmd_path}")
                return None

            result = await self._run_subprocess([str(cmd_path), "-r"])

            match (result.returncode, result.stdout.strip()):
                case (0, ssid) if ssid:
                    return ssid
                case _:
                    return None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None

    async def _get_ip_address(self) -> str | None:
        """Get the current IP address asynchronously.

        Returns:
            IP address as string, or None if not connected or error.
        """
        try:
            loop = asyncio.get_event_loop()

            def get_ip() -> str | None:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.connect((BROADCAST_IP, BROADCAST_PORT))
                        return s.getsockname()[0]
                except Exception:
                    return None

            return await loop.run_in_executor(None, get_ip)
        except Exception:
            return None

    async def _get_signal_strength(self) -> int | None:
        """Get the current WiFi signal strength asynchronously.

        Returns:
            Signal strength in dBm, or None if not connected or error.
        """
        try:
            cmd_path = path_resolver.get_bin_path("iwconfig")
            if not file_exists(cmd_path):
                self.logger.warning(f"Command not found: {cmd_path}")
                return None

            result = await self._run_subprocess([str(cmd_path), "wlan0"])

            match result.returncode:
                case 0:
                    for line in result.stdout.split("\n"):
                        if "Signal level" in line:
                            # Extract signal level (dBm)
                            parts = line.split("Signal level=")
                            if len(parts) > 1:
                                signal = parts[1].split(" ")[0]
                                return int(signal.replace("dBm", ""))
                    return None
                case _:
                    return None
        except Exception as e:
            match type(e).__name__:
                case "SubprocessError" | "TimeoutExpired" | "ValueError" | "IndexError":
                    return None
                case _:
                    # Re-raise unexpected exceptions
                    raise

    @asynccontextmanager
    async def ensure_connectivity(self) -> AsyncGenerator[bool, None]:
        """Async context manager to ensure network connectivity.

        This context manager automatically manages WiFi power states,
        enabling WiFi when needed and disabling it afterwards to save power.
        The async implementation allows other coroutines to run while waiting
        for network operations.

        Yields:
            True if connected, False otherwise.

        Example:
            async with network_manager.ensure_connectivity() as connected:
                if connected:
                    # Perform network operations
                    await fetch_data()
                # WiFi automatically disabled on exit
        """
        # Try to enable WiFi if it's not already enabled
        connected = await self._check_connectivity()

        if not connected:
            self.logger.info("Not connected, attempting to enable WiFi")
            await self._enable_wifi()

            # Try to establish connection with exponential backoff
            connected_result = await self.with_retry(self._try_connect)
            connected = connected_result if connected_result is not None else False
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
                await self._disable_wifi()

    async def _try_connect(self) -> bool:
        """Try to establish network connectivity asynchronously.

        Returns:
            True if connected, False otherwise.

        Raises:
            ConnectionError: If connection cannot be established within the timeout period.
        """
        # Wait for connection with async sleep
        start_time = time.time()
        while time.time() - start_time < self.config.wifi_timeout_seconds:
            if await self._check_connectivity():
                return True
            await asyncio.sleep(1)

        # If we reach here, connection failed
        raise ConnectionError("Failed to establish network connection")

    async def _enable_wifi(self) -> None:
        """Enable WiFi asynchronously."""
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
                await self._enable_wifi_legacy()
                return

            # Call the wifi-sleep.sh script to enable WiFi
            await self._run_subprocess([str(sudo_path), str(wifi_script), "on"])
            self.logger.info("WiFi interface enabled with power saving")

            # Apply battery-aware power save mode if enabled
            await self._apply_power_save_mode()

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to enable WiFi: {e}")
            # Try legacy method as fallback
            await self._enable_wifi_legacy()

    async def _enable_wifi_legacy(self) -> None:
        """Enable WiFi using legacy ifconfig method as fallback (async)."""
        try:
            sudo_path = path_resolver.get_bin_path("sudo")
            ifconfig_path = path_resolver.get_bin_path("ifconfig")

            if not file_exists(sudo_path) or not file_exists(ifconfig_path):
                self.logger.warning("Commands not found for enabling WiFi")
                return

            await self._run_subprocess([str(sudo_path), str(ifconfig_path), "wlan0", "up"])
            self.logger.info("WiFi interface enabled (legacy method)")

            # Apply battery-aware power save mode if enabled
            await self._apply_power_save_mode()

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to enable WiFi (legacy method): {e}")

    async def _apply_power_save_mode(self) -> None:
        """Apply battery-aware power save mode if enabled (async)."""
        if self.config.enable_battery_aware_wifi:
            await self.set_wifi_power_save_mode()

    async def _disable_wifi(self) -> None:
        """Disable WiFi to save power (async)."""
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
                await self._disable_wifi_legacy()
                return

            await self._run_subprocess([str(sudo_path), str(wifi_script), "off"])
            self.logger.info("WiFi interface disabled with rfkill to save power")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to disable WiFi: {e}")
            # Try legacy method as fallback
            await self._disable_wifi_legacy()

    async def _disable_wifi_legacy(self) -> None:
        """Disable WiFi using legacy ifconfig method as fallback (async)."""
        try:
            sudo_path = path_resolver.get_bin_path("sudo")
            ifconfig_path = path_resolver.get_bin_path("ifconfig")

            if not file_exists(sudo_path) or not file_exists(ifconfig_path):
                self.logger.warning("Commands not found for disabling WiFi")
                return

            await self._run_subprocess([str(sudo_path), str(ifconfig_path), "wlan0", "down"])
            self.logger.info("WiFi interface disabled to save power (legacy method)")
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to disable WiFi (legacy method): {e}")

    async def set_wifi_power_save_mode(self, mode: str | None = None) -> bool:
        """Set WiFi power save mode based on battery level (async).

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
            match self.current_battery_status:
                case None:
                    # Default to "on" if battery status is not available
                    mode = "on"
                case status if status.level <= self.config.critical_battery_threshold:
                    # Use aggressive power saving when battery is critically low
                    mode = "aggressive"
                case status if status.level <= self.config.low_battery_threshold:
                    # Use regular power saving when battery is low
                    mode = "on"
                case _:
                    # Disable power saving when battery is good
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
            await self._run_subprocess(
                [str(sudo_path), str(iw_path), "dev", "wlan0", "set", "power_save", mode_arg]
            )

            # If using aggressive mode, we need additional settings
            if mode == "aggressive":
                # Set beacon interval to maximum to reduce wakeups
                iwconfig_path = path_resolver.get_bin_path("iwconfig")
                await self._run_subprocess(
                    [str(sudo_path), str(iwconfig_path), "wlan0", "power", "timeout", "3600"]
                )

            self.logger.info(f"WiFi power save mode set to '{mode}'")
            return True

        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to set WiFi power save mode: {e}")
            return False
