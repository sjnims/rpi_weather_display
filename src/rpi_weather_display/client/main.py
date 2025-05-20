"""Main entry point for the Raspberry Pi weather display client.

Manages the client lifecycle including hardware initialization, display updates,
power management, and scheduled deep sleep operations for the e-paper weather display.
This module contains the main client application class responsible for coordinating
the various subsystems and implementing the core logic of the weather display.
"""

import argparse
import tempfile
import time
from pathlib import Path

import requests

from rpi_weather_display.client.display import EPaperDisplay
from rpi_weather_display.constants import (
    CLIENT_CACHE_DIR_NAME,
    DEFAULT_CONFIG_PATH,
    SLEEP_BEFORE_SHUTDOWN,
    TEN_MINUTES,
    TWELVE_HOURS_IN_MINUTES,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.utils import PowerStateManager
from rpi_weather_display.utils.battery_utils import is_charging
from rpi_weather_display.utils.logging import setup_logging
from rpi_weather_display.utils.power_manager import PowerState


class WeatherDisplayClient:
    """Main client application for the weather display.
    
    Manages the lifecycle of the weather display client, including initialization,
    update scheduling, power management, and hardware control. Implements an
    event-driven architecture with callbacks for power state changes to enable
    battery-aware behavior.
    
    Attributes:
        config: Application configuration loaded from YAML
        logger: Configured logger instance
        power_manager: Manager for power state and battery monitoring
        display: E-paper display controller
        cache_dir: Directory for caching weather images
        current_image_path: Path to the most recently downloaded weather image
        _running: Flag indicating if the main loop is active
    """

    def __init__(self, config_path: Path) -> None:
        """Initialize the client with configuration.

        Args:
            config_path: Path to the YAML configuration file.
        """
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "client")

        # Initialize components
        self.power_manager = PowerStateManager(self.config)
        self.display = EPaperDisplay(self.config.display)

        # Image cache path
        self.cache_dir = Path(tempfile.gettempdir()) / CLIENT_CACHE_DIR_NAME
        self.cache_dir.mkdir(exist_ok=True)
        self.current_image_path = self.cache_dir / "current.png"

        self.logger.info("Weather Display Client initialized")
        self._running = False

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

    def _handle_power_state_change(self, old_state: PowerState, new_state: PowerState) -> None:
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

                # Initiate shutdown
                self.shutdown()
                self.power_manager.shutdown_system()

            except Exception as e:
                self.logger.error(f"Error during critical shutdown: {e}")
                # Still try to shut down even if there was an error
                try:
                    self.power_manager.shutdown_system()
                except Exception as shutdown_error:
                    self.logger.error(f"Final shutdown attempt failed: {shutdown_error}")

    def update_weather(self) -> bool:
        """Update weather data from server.

        Requests a new weather image from the server, sending battery status
        and system metrics as part of the request to inform server-side
        optimizations. The received image is saved to the local cache for
        display.

        Returns:
            True if update was successful, False otherwise.
            
        Raises:
            requests.RequestException: If there is an error communicating with the server.
        """
        self.logger.info("Updating weather data from server")

        try:
            # Get battery status for the request
            battery = self.power_manager.get_battery_status()

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

            # Send request to server
            response = requests.post(
                server_url, json=payload, timeout=self.config.server.timeout_seconds
            )

            if response.status_code != 200:
                self.logger.error(
                    f"Server returned error: {response.status_code} - {response.text}"
                )
                return False

            # Save the image to cache
            with open(self.current_image_path, "wb") as f:
                f.write(response.content)

            # Record that we updated the weather data
            self.power_manager.record_weather_update()

            self.logger.info("Weather data updated successfully")
            return True
        except requests.RequestException as e:
            self.logger.error(f"Error communicating with server: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating weather data: {e}")
            return False

    def refresh_display(self) -> None:
        """Refresh the e-paper display with the latest weather data.
        
        Updates the display with the most recently cached weather image.
        If no cached image is available, attempts to request a new one
        from the server first. The display refresh considers battery status
        for power-efficient partial updates.
        
        Raises:
            Exception: If there is an error refreshing the display.
        """
        self.logger.info("Refreshing display")

        try:
            # Update the battery status in the display for threshold adjustment
            battery_status = self.power_manager.get_battery_status()
            self.display.update_battery_status(battery_status)

            # Check if we have a cached image
            if self.current_image_path.exists():
                # Display the image
                self.display.display_image(self.current_image_path)
                # Record that we refreshed the display
                self.power_manager.record_display_refresh()
                self.logger.info("Display refreshed successfully")
            else:
                # No image available, try to update first
                if self.update_weather():
                    self.display.display_image(self.current_image_path)
                    # Record that we refreshed the display
                    self.power_manager.record_display_refresh()
                    self.logger.info("Display refreshed successfully")
                else:
                    self.logger.error("No image available and failed to update")
        except Exception as e:
            self.logger.error(f"Error refreshing display: {e}")

    def run(self) -> None:
        """Run the client main loop.
        
        Implements the main operational loop of the client application, including:
        - Hardware initialization
        - Initial weather update and display
        - Regular checks for update conditions
        - Quiet hours handling with display sleep
        - Deep sleep scheduling for power efficiency
        
        The loop continues until interrupted or a critical battery condition
        triggers a shutdown.
        """
        self.logger.info("Starting Weather Display Client")
        self._running = True
        display_sleeping = False

        try:
            # Initialize hardware
            self.initialize()

            # Initial update
            self.update_weather()

            # Initial display refresh
            self.refresh_display()

            # Main loop using PowerStateManager for scheduling
            while self._running:
                # Check current power state for quiet hours
                current_state = self.power_manager.get_current_state()
                battery_status = self.power_manager.get_battery_status()
                is_in_quiet_hours = current_state == PowerState.QUIET_HOURS

                # Handle display sleep during quiet hours
                if is_in_quiet_hours and not is_charging(battery_status) and not display_sleeping:
                    self.logger.info("Quiet hours active and not charging - display sleeping")
                    self.display.sleep()
                    display_sleeping = True
                elif display_sleeping and (not is_in_quiet_hours or is_charging(battery_status)):
                    self.logger.info("Quiet hours ended or charging - waking display")
                    self.refresh_display()
                    display_sleeping = False

                # Check if we should update weather
                if self.power_manager.should_update_weather():
                    self.update_weather()

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

                # Regular sleep
                self.logger.info(f"Sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Client interrupted by user")
            self._running = False
        except Exception as e:
            self.logger.error(f"Error in client main loop: {e}")
            self._running = False
        finally:
            # Clean up
            self.shutdown()

    def _handle_sleep(self, minutes: int) -> bool:
        """Handle deep sleep request for extended idle periods.

        For longer sleep intervals, uses the PiJuice's hardware wake-up timer
        to completely shut down the system and save power, rather than keeping
        the CPU running. This approach dramatically reduces power consumption
        during long idle periods by turning off the entire system except for
        the PiJuice RTC (Real-Time Clock) that will wake the system at the 
        scheduled time.

        Deep sleep is only triggered for intervals longer than 10 minutes
        and when not in debug mode, as specified in the configuration.
        When activated, it performs these steps:
        1. Schedules a wakeup time with the PiJuice RTC
        2. Puts the e-paper display into sleep mode
        3. Initiates system shutdown

        Args:
            minutes: Number of minutes to schedule for deep sleep.
                    This may be adjusted dynamically based on battery status.

        Returns:
            bool: True if the system will be shut down for deep sleep
                 False if normal sleep is used instead (shorter duration or debug mode)
            
        Raises:
            RuntimeError: If there is a critical error during the sleep process
                         that prevents proper shutdown.
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

    def shutdown(self) -> None:
        """Clean up resources and shut down the client.
        
        Performs an orderly shutdown of all hardware components and subsystems,
        ensuring that resources are properly released and that the e-paper
        display is put into sleep mode to conserve power.
        """
        self.logger.info("Shutting down Weather Display Client")

        # Close the display
        if self.display:
            self.display.close()


def main() -> None:
    """Main entry point for the weather display client application.
    
    Parses command line arguments, loads configuration, and starts the client.
    This is the function called when the client is invoked from the command line.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Weather Display Client")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG_PATH),
        help="Path to configuration file",
    )
    args = parser.parse_args()

    # Check if config file exists
    if not args.config.exists():
        print(f"Error: Configuration file not found at {args.config}")
        return

    # Create and run client
    client = WeatherDisplayClient(args.config)
    client.run()


if __name__ == "__main__":
    main()