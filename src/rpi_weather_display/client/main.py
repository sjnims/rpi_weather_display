"""Main entry point for the Raspberry Pi weather display client.

Manages the client lifecycle including hardware initialization, display updates,
power management, and scheduled operations for the e-paper weather display.
"""

import argparse
import tempfile
import time
from pathlib import Path

import requests

from rpi_weather_display.client.display import EPaperDisplay
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.utils import PowerStateManager
from rpi_weather_display.utils.logging import setup_logging
from rpi_weather_display.utils.power_manager import PowerState


class WeatherDisplayClient:
    """Main client application for the weather display."""

    def __init__(self, config_path: Path) -> None:
        """Initialize the client.

        Args:
            config_path: Path to configuration file.
        """
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "client")

        # Initialize components
        self.power_manager = PowerStateManager(self.config)
        self.display = EPaperDisplay(self.config.display)

        # Image cache path
        self.cache_dir = Path(tempfile.gettempdir()) / "rpi-weather-display"
        self.cache_dir.mkdir(exist_ok=True)
        self.current_image_path = self.cache_dir / "current.png"

        self.logger.info("Weather Display Client initialized")
        self._running = False

    def initialize(self) -> None:
        """Initialize hardware and subsystems."""
        self.logger.info("Initializing hardware")

        # Initialize power manager
        self.power_manager.initialize()
        
        # Register power state change callback for critical battery events
        self.power_manager.register_state_change_callback(self._handle_power_state_change)

        # Initialize display
        self.display.initialize()

        self.logger.info("Hardware initialization complete")
        
    def _handle_power_state_change(self, old_state: PowerState, new_state: PowerState) -> None:
        """Handle power state changes, particularly for critical events.
        
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
                time.sleep(5)
                
                # Halt the main loop
                self._running = False
                
                # Schedule a dynamic wakeup based on battery level
                # Using 12 hours as base duration, but it will be adjusted dynamically
                self.power_manager.schedule_wakeup(12 * 60, dynamic=True)  # 12 hours as base
                
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

        Returns:
            True if update was successful, False otherwise.
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
        """Refresh the e-paper display with the latest weather data."""
        self.logger.info("Refreshing display")

        try:
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
        """Run the client main loop."""
        self.logger.info("Starting Weather Display Client")
        self._running = True

        try:
            # Initialize hardware
            self.initialize()

            # Initial update
            self.update_weather()

            # Initial display refresh
            self.refresh_display()

            # Main loop using PowerStateManager for scheduling
            while self._running:
                # Check if we should update weather
                if self.power_manager.should_update_weather():
                    self.update_weather()

                # Check if we should refresh display
                if self.power_manager.should_refresh_display():
                    self.refresh_display()

                # Calculate sleep time
                sleep_time = self.power_manager.calculate_sleep_time()

                # If sleep time is long, consider deep sleep
                if sleep_time > 10 * 60:  # More than 10 minutes
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
        """Handle sleep request.

        Args:
            minutes: Number of minutes to sleep.

        Returns:
            True if the system will be shut down for deep sleep, False otherwise.
        """
        # For battery conservation, only schedule wakeup and shutdown if:
        # 1. The sleep duration is significant (more than 10 minutes)
        # 2. We're not in debug mode
        if minutes > 10 and not self.config.debug:
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
        """Clean up resources and shut down."""
        self.logger.info("Shutting down Weather Display Client")

        # Close the display
        if self.display:
            self.display.close()


def main() -> None:
    """Main entry point for the client."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Weather Display Client")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/rpi-weather-display/config.yaml"),
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
