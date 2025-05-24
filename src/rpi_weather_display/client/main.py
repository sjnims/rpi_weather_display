"""Async-enabled main entry point for the Raspberry Pi weather display client.

This module provides an async version of the weather display client that uses
non-blocking I/O operations for improved power efficiency. The async implementation
allows the CPU to enter low-power states while waiting for network operations,
reducing overall power consumption.
"""

import argparse
import asyncio
import time
from pathlib import Path

import httpx

from rpi_weather_display.client.display import EPaperDisplay
from rpi_weather_display.constants import (
    CONNECTION_TIMEOUT,
    DEFAULT_CONFIG_PATH,
    DEFAULT_IMAGE_FILENAME,
    KEEPALIVE_EXPIRY,
    MAX_CONCURRENT_OPERATIONS,
    MAX_CONNECTIONS,
    MAX_KEEPALIVE_CONNECTIONS,
    POOL_TIMEOUT,
    SLEEP_BEFORE_SHUTDOWN,
    TEN_MINUTES,
    TWELVE_HOURS_IN_MINUTES,
    WRITE_TIMEOUT,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.utils import PowerStateManager, path_resolver
from rpi_weather_display.utils.battery_utils import is_charging
from rpi_weather_display.utils.file_utils import file_exists, write_bytes
from rpi_weather_display.utils.logging import setup_logging
from rpi_weather_display.utils.network import AsyncNetworkManager
from rpi_weather_display.utils.path_utils import validate_config_path
from rpi_weather_display.utils.power_manager import PowerState


class AsyncWeatherDisplayClient:
    """Async-enabled weather display client.

    This class provides the same functionality as WeatherDisplayClient but uses
    async/await patterns for network operations. This enables better power
    efficiency by allowing the CPU to sleep during I/O wait times.

    Key improvements over synchronous version:
    - Non-blocking network operations
    - Concurrent request capabilities
    - Better timeout handling
    - Reduced CPU wake time during network waits

    Attributes:
        config: Application configuration loaded from YAML
        logger: Configured logger instance
        power_manager: Manager for power state and battery monitoring
        display: E-paper display controller
        cache_dir: Directory for caching weather images
        current_image_path: Path to the most recently downloaded weather image
        _running: Flag indicating if the main loop is active
        _http_client: Reusable async HTTP client instance
        _semaphore: Concurrency limiter for resource protection
    """

    def __init__(self, config_path: Path) -> None:
        """Initialize the async client with configuration.

        Args:
            config_path: Path to the YAML configuration file.
        """
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "async_client")

        # Initialize components
        self.power_manager = PowerStateManager(self.config)
        self.display = EPaperDisplay(self.config.display)
        
        # Initialize network manager for WiFi power management
        self.network_manager = AsyncNetworkManager(self.config.power)
        self.network_manager.set_app_config(self.config)

        # Image cache path using the path resolver
        self.cache_dir = path_resolver.cache_dir
        self.current_image_path = path_resolver.get_cache_file(DEFAULT_IMAGE_FILENAME)

        # Async HTTP client with connection pooling
        self._http_client: httpx.AsyncClient | None = None

        # Semaphore for limiting concurrent operations
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_OPERATIONS)

        self.logger.info("Async Weather Display Client initialized")
        self._running = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client.

        Uses a single persistent client with connection pooling for efficiency.
        The client is configured with appropriate timeouts and retry behavior.

        Returns:
            Configured async HTTP client instance.
        """
        if self._http_client is None:
            # Configure the client with connection pooling and timeouts
            timeout = httpx.Timeout(
                connect=CONNECTION_TIMEOUT,
                read=self.config.server.timeout_seconds,  # Read timeout from config
                write=WRITE_TIMEOUT,
                pool=POOL_TIMEOUT,
            )

            # Create client with retry-friendly settings
            self._http_client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
                    max_connections=MAX_CONNECTIONS,
                    keepalive_expiry=KEEPALIVE_EXPIRY,
                ),
                # HTTP/2 is optional - will use HTTP/1.1 if not available
                http2=False,
            )

        return self._http_client

    def initialize(self) -> None:
        """Initialize hardware and subsystems.

        Sets up the power manager, registers callbacks for power state changes,
        and initializes the e-paper display hardware. This method should be called
        once at the start of the client application.

        Raises:
            RuntimeError: If hardware initialization fails.
        """
        self.logger.info("Initializing hardware")

        # Initialize power manager
        self.power_manager.initialize()

        # Register power state change callback for critical battery events
        self.power_manager.register_state_change_callback(self._handle_power_state_change)

        # Initialize display
        self.display.initialize()

        self.logger.info("Hardware initialization complete")

    def _handle_power_state_change(self, _old_state: PowerState, new_state: PowerState) -> None:
        """Handle power state changes, particularly for critical battery events.

        Manages transitions between power states, with special handling for the
        CRITICAL state which initiates an emergency shutdown to protect the battery.

        Args:
            old_state: Previous power state
            new_state: New power state
        """
        # If transitioning to CRITICAL state, initiate safe shutdown
        if new_state == PowerState.CRITICAL:
            self.logger.warning("CRITICAL BATTERY STATE DETECTED - Initiating safe shutdown")

            try:
                # Display a warning message if possible
                self.display.display_text("CRITICAL BATTERY", "Shutting down to preserve battery")

                # Give a brief pause to allow warning to be displayed
                time.sleep(SLEEP_BEFORE_SHUTDOWN)

                # Halt the main loop
                self._running = False

                # Schedule a dynamic wakeup based on battery level
                # Using 12 hours as base duration, but it will be adjusted dynamically
                self.power_manager.schedule_wakeup(TWELVE_HOURS_IN_MINUTES, dynamic=True)

                # Initiate shutdown - run async method in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.shutdown())
                finally:
                    loop.close()
                    
                self.power_manager.shutdown_system()

            except Exception as e:
                self.logger.error(f"Error during critical shutdown: {e}")
                # Still try to shut down even if there was an error
                try:
                    self.power_manager.shutdown_system()
                except Exception as shutdown_error:
                    self.logger.error(f"Final shutdown attempt failed: {shutdown_error}")
                    raise RuntimeError("Failed to perform critical shutdown") from shutdown_error

    async def update_weather(self) -> bool:
        """Update weather data from server using async operations.

        Requests a new weather image from the server, sending battery status
        and system metrics as part of the request to inform server-side
        optimizations. Uses async HTTP operations to avoid blocking.

        Key improvements:
        - Non-blocking network I/O
        - Better timeout handling
        - Allows CPU to sleep during network wait
        - Automatic WiFi power management

        Returns:
            True if update was successful, False otherwise.
        """
        # Use semaphore to limit concurrent operations
        async with self._semaphore:
            self.logger.info("Updating weather data from server (async)")

            # Get battery status and update network manager
            battery = self.power_manager.get_battery_status()
            self.network_manager.update_battery_status(battery)

            # Use network manager to ensure WiFi connectivity
            # WiFi will be automatically disabled when we exit this context
            async with self.network_manager.ensure_connectivity() as connected:
                if not connected:
                    self.logger.error("Failed to establish network connection")
                    return False

                try:
                    # Get system metrics
                    metrics = self.power_manager.get_system_metrics()

                    # Create request payload
                    payload = {
                        "battery": {
                            "level": battery.level,
                            "state": battery.state,
                            "voltage": battery.voltage,
                            "current": battery.current,
                            "temperature": battery.temperature,
                        },
                        "metrics": metrics,
                    }

                    # Construct server URL
                    server_url = f"{self.config.server.url}:{self.config.server.port}/render"

                    # Get the HTTP client
                    client = await self._get_http_client()

                    # Send async request to server
                    response = await client.post(server_url, json=payload)

                    if response.status_code != 200:
                        self.logger.error(
                            f"Server returned error: {response.status_code} - {response.text}"
                        )
                        return False

                    # Save the image to cache using file_utils
                    # Note: For a production system, we might want to make this async too
                    write_bytes(self.current_image_path, response.content)

                    # Record that we updated the weather data
                    self.power_manager.record_weather_update()

                    self.logger.info("Weather data updated successfully (async)")
                    return True

                except httpx.TimeoutException as e:
                    self.logger.error(f"Request timeout: {e}")
                    return False
                except httpx.NetworkError as e:
                    self.logger.error(f"Network error: {e}")
                    return False
                except httpx.HTTPError as e:
                    self.logger.error(f"HTTP error: {e}")
                    return False
                except Exception as e:
                    self.logger.error(f"Error updating weather data: {e}")
                    return False
            # WiFi is automatically disabled here when we exit the context manager

    def refresh_display(self) -> None:
        """Refresh the e-paper display with the latest weather data.

        Updates the display with the most recently cached weather image.
        If no cached image is available, attempts to request a new one
        from the server first. The display refresh considers battery status
        for power-efficient partial updates.

        Note: Display operations remain synchronous as they are hardware-bound
        and don't benefit from async patterns.

        Raises:
            Exception: If there is an error refreshing the display.
        """
        self.logger.info("Refreshing display")

        try:
            # Update the battery status in the display for threshold adjustment
            battery_status = self.power_manager.get_battery_status()
            self.display.update_battery_status(battery_status)

            # Check if we have a cached image
            if file_exists(self.current_image_path):
                # Display the image
                self.display.display_image(self.current_image_path)
                # Record that we refreshed the display
                self.power_manager.record_display_refresh()
                self.logger.info("Display refreshed successfully")
            else:
                # No image available, try to update first
                # We need to run the async update in a sync context
                # Create a new event loop for this sync method
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    update_success = loop.run_until_complete(self.update_weather())
                finally:
                    loop.close()
                
                if update_success:
                    self.display.display_image(self.current_image_path)
                    # Record that we refreshed the display
                    self.power_manager.record_display_refresh()
                    self.logger.info("Display refreshed successfully")
                else:
                    self.logger.error("No image available and failed to update")
        except Exception as e:
            self.logger.error(f"Error refreshing display: {e}")

    async def run(self) -> None:
        """Run the async client main loop.

        Implements the main operational loop of the client application using
        async patterns for improved power efficiency:
        - Hardware initialization
        - Initial weather update and display
        - Regular checks for update conditions
        - Quiet hours handling with display sleep
        - Deep sleep scheduling for power efficiency

        The loop continues until interrupted or a critical battery condition
        triggers a shutdown.
        """
        self.logger.info("Starting Async Weather Display Client")
        self._running = True
        display_sleeping = False

        try:
            # Initialize hardware
            self.initialize()

            # Initial update (async)
            await self.update_weather()

            # Initial display refresh
            self.refresh_display()

            # Main loop using PowerStateManager for scheduling
            while self._running:
                # Check current power state for quiet hours
                current_state = self.power_manager.get_current_state()
                battery_status = self.power_manager.get_battery_status()
                is_in_quiet_hours = current_state == PowerState.QUIET_HOURS

                # Handle display sleep during quiet hours using pattern matching
                match (is_in_quiet_hours, is_charging(battery_status), display_sleeping):
                    case (True, False, False):
                        # Quiet hours active, not charging, display awake -> sleep display
                        self.logger.info("Quiet hours active and not charging - display sleeping")
                        self.display.sleep()
                        display_sleeping = True
                    case (False, _, True) | (_, True, True):
                        # Quiet hours ended OR charging while display sleeping -> wake display
                        self.logger.info("Quiet hours ended or charging - waking display")
                        self.refresh_display()
                        display_sleeping = False
                    case _:
                        # No change needed
                        pass

                # Check if we should update weather (async)
                if self.power_manager.should_update_weather():
                    await self.update_weather()

                # Check if we should refresh display (but skip if display is sleeping)
                if self.power_manager.should_refresh_display() and not display_sleeping:
                    self.refresh_display()

                # Calculate sleep time
                sleep_time = self.power_manager.calculate_sleep_time()

                # If sleep time is long, consider deep sleep
                if sleep_time > TEN_MINUTES:  # More than 10 minutes
                    minutes = sleep_time // 60
                    if self._handle_sleep(minutes):
                        break  # Exit loop if we're doing deep sleep

                # Async sleep (allows other coroutines to run)
                self.logger.info(f"Sleeping for {sleep_time} seconds")
                await asyncio.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Client interrupted by user")
            self._running = False
        except Exception as e:
            self.logger.error(f"Error in async client main loop: {e}")
            self._running = False
        finally:
            # Clean up
            await self.shutdown()

    def _handle_sleep(self, minutes: int) -> bool:
        """Handle deep sleep request for extended idle periods.

        Identical to synchronous version as hardware operations don't benefit
        from async patterns.

        Args:
            minutes: Number of minutes to schedule for deep sleep.

        Returns:
            bool: True if the system will be shut down for deep sleep
        """
        # For battery conservation, only schedule wakeup and shutdown if:
        # 1. The sleep duration is significant (more than 10 minutes)
        # 2. We're not in debug mode
        if minutes > TEN_MINUTES // 60 and not self.config.debug:
            self.logger.info(f"Preparing for deep sleep ({minutes} minutes)")

            # Schedule dynamic wakeup based on battery level
            if self.power_manager.schedule_wakeup(minutes, dynamic=True):
                # Close the display
                self.display.sleep()

                # Shutdown the system
                self.power_manager.shutdown_system()
                return True

        return False

    async def shutdown(self) -> None:
        """Clean up resources and shut down the async client.

        Performs an orderly shutdown of all hardware components and subsystems,
        ensuring that resources are properly released. Also closes the async
        HTTP client to free network resources.
        """
        self.logger.info("Shutting down Async Weather Display Client")

        # Close the HTTP client if it exists
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        # Close the display
        if self.display:
            self.display.close()


def main() -> None:
    """Main entry point for the async weather display client application.

    Parses command line arguments, loads configuration, and starts the async client.
    This is the function called when the async client is invoked from the command line.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Async Weather Display Client")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    # Validate and resolve the config path
    config_path = validate_config_path(args.config)

    # Create and run async client
    client = AsyncWeatherDisplayClient(config_path)

    # Run the async main loop
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
