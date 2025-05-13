import argparse
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from rpi_weather_display.client.display import EPaperDisplay
from rpi_weather_display.client.power import PowerManager
from rpi_weather_display.client.scheduler import Scheduler
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus, SystemStatus
from rpi_weather_display.utils.logging import setup_logging


class WeatherDisplayClient:
    """Main client application for the weather display."""

    def __init__(self, config_path: Path):
        """Initialize the client.

        Args:
            config_path: Path to configuration file.
        """
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "client")

        # Initialize components
        self.power_manager = PowerManager(self.config.power)
        self.display = EPaperDisplay(self.config.display)
        self.scheduler = Scheduler(self.config)

        # Image cache path
        self.cache_dir = Path(tempfile.gettempdir()) / "weather-display"
        self.cache_dir.mkdir(exist_ok=True)
        self.current_image_path = self.cache_dir / "current.png"

        self.logger.info("Weather Display Client initialized")

    def initialize(self) -> None:
        """Initialize hardware and subsystems."""
        self.logger.info("Initializing hardware")

        # Initialize power manager
        self.power_manager.initialize()

        # Initialize display
        self.display.initialize()

        self.logger.info("Hardware initialization complete")

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
                self.logger.info("Display refreshed successfully")
            else:
                # No image available, try to update first
                if self.update_weather():
                    self.display.display_image(self.current_image_path)
                    self.logger.info("Display refreshed successfully")
                else:
                    self.logger.error("No image available and failed to update")
        except Exception as e:
            self.logger.error(f"Error refreshing display: {e}")

    def run(self) -> None:
        """Run the client main loop."""
        self.logger.info("Starting Weather Display Client")

        try:
            # Initialize hardware
            self.initialize()

            # Initial update
            self.update_weather()

            # Initial display refresh
            self.refresh_display()

            # Run the scheduler
            self.scheduler.run(
                refresh_callback=self.refresh_display,
                update_callback=self.update_weather,
                battery_callback=self.power_manager.get_battery_status,
                sleep_callback=self._handle_sleep,
            )
        except KeyboardInterrupt:
            self.logger.info("Client interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in client main loop: {e}")
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

            # Schedule wakeup
            if self.power_manager.schedule_wakeup(minutes):
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
