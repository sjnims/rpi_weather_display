# pyright: reportMissingImports=false, reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnusedImport=false

"""Weather data rendering module for creating display images.

Provides functionality to render weather data into HTML and convert it to
images suitable for display on the e-paper screen using Playwright.
"""

import logging
from datetime import datetime
from pathlib import Path

import jinja2

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.models.weather import (
    CurrentWeather,
    HourlyWeather,
    WeatherCondition,
    WeatherData,
)
from rpi_weather_display.utils import get_battery_icon
from rpi_weather_display.utils.error_utils import get_error_location


class WeatherRenderer:
    """Renderer for weather data to e-paper display images."""

    def __init__(self, config: AppConfig, template_dir: Path) -> None:
        """Initialize the renderer.

        Args:
            config: Application configuration.
            template_dir: Path to the templates directory.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Set up Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir), autoescape=True
        )

        # Add custom filters
        self.jinja_env.filters["format_datetime"] = self._format_datetime
        self.jinja_env.filters["format_temp"] = self._format_temp
        self.jinja_env.filters["get_icon"] = self._get_weather_icon

    def _format_datetime(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a datetime object or Unix timestamp.

        Args:
            dt: Datetime object or Unix timestamp.
            format_str: Format string to use (or None to use default).

        Returns:
            Formatted datetime string.
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)

        if format_str is None:
            format_str = self.config.display.timestamp_format

        return dt.strftime(format_str)

    def _format_temp(self, temp: float, units: str | None = None) -> str:
        """Format a temperature value.

        Args:
            temp: Temperature value.
            units: Units to use (or None to use config).

        Returns:
            Formatted temperature string.
        """
        if units is None:
            units = self.config.weather.units

        if units == "metric":
            return f"{int(round(temp))}°C"
        elif units == "imperial":
            return f"{int(round(temp))}°F"
        else:
            return f"{int(round(temp))}K"

    async def generate_html(self, weather_data: WeatherData, battery_status: BatteryStatus) -> str:
        """Generate HTML for the weather display.

        Args:
            weather_data: Weather data to display.
            battery_status: Battery status information.

        Returns:
            HTML content as a string.
        """
        try:
            # Load the template
            template = self.jinja_env.get_template("dashboard.html.j2")

            # Get battery icon based on status
            battery_icon = self._get_battery_icon(battery_status)

            # Calculate current date and time info
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            last_refresh = now.strftime(self.config.display.timestamp_format)

            # Set up units based on config
            is_metric = self.config.weather.units == "metric"
            units_temp = "°C" if is_metric else "°F"
            units_wind = "m/s" if is_metric else "mph"
            units_precip = "mm" if is_metric else "in"
            units_pressure = "hPa"  # Standard unit regardless of system

            # Handle Beaufort scale for wind (simplified)
            bft = min(int(weather_data.current.wind_speed / 3.5) + 1, 12)

            # Prepare mock data for fields that require calculation
            daylight = "12h 30m"  # Mock value - would need calculation
            uvi_max = "5.2"  # Mock value - would need max calculation
            uvi_time = "12:00"  # Mock value - would need time calculation
            aqi = "Good"  # Mock value - would need air quality
            pressure = weather_data.current.pressure

            # Moon phase (placeholder - would need actual calculation)
            moon_phase = "moon-waxing-gibbous"

            # City name (from config or weather data)
            city = self.config.weather.city_name or "Unknown Location"

            # Helper function for precipitation amount
            def get_precipitation_amount(
                weather_item: CurrentWeather | HourlyWeather,
            ) -> float | None:
                """Extract precipitation amount from weather item."""
                # This would need proper implementation based on your data structure
                return None

            # Helper function for hourly precipitation
            def get_hourly_precipitation(hour: HourlyWeather) -> str:
                """Get precipitation amount for an hourly forecast."""
                # This would need proper implementation
                return "0"

            # Helper filter for weather icons
            def weather_icon_filter(weather_item: WeatherCondition) -> str:
                """Convert weather item to icon."""
                # Extract icon code and convert to your icon format
                return "cloud-bold"  # Default placeholder

            # Helper filter for moon phase
            def moon_phase_icon_filter(phase: float) -> str:
                """Convert moon phase to icon."""
                return "moon-waxing-gibbous"  # Default placeholder

            # Helper filter for moon phase label
            def moon_phase_label_filter(phase: float) -> str:
                """Get text label for moon phase."""
                return "Waxing Gibbous"  # Default placeholder

            # Helper filter for wind direction angle
            def wind_direction_angle_filter(deg: float) -> float:
                """Convert wind direction to rotation angle."""
                return deg  # Pass through as is

            # Register custom filters/functions for the template render
            template_env = self.jinja_env.overlay()
            template_env.filters["weather_icon"] = weather_icon_filter
            template_env.filters["moon_phase_icon"] = moon_phase_icon_filter
            template_env.filters["moon_phase_label"] = moon_phase_label_filter
            template_env.filters["wind_direction_angle"] = wind_direction_angle_filter  # type: ignore
            template_env.globals["get_precipitation_amount"] = get_precipitation_amount  # type: ignore
            template_env.globals["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore

            # Prepare context with all required variables
            context = {
                # Main data objects
                "weather": weather_data,
                "battery": battery_status,  # Pass the full battery status object
                "battery_status": battery_status,  # Full object if needed
                "battery_icon": battery_icon,
                "config": self.config,
                # Date and time
                "date": date_str,
                "last_updated": now,
                "last_refresh": last_refresh,
                # Units
                "is_metric": is_metric,
                "units_temp": units_temp,
                "units_wind": units_wind,
                "units_precip": units_precip,
                "units_pressure": units_pressure,
                # Location
                "city": city,
                # Weather details
                "bft": bft,
                "daylight": daylight,
                "uvi_max": uvi_max,
                "uvi_time": uvi_time,
                "aqi": aqi,
                "pressure": pressure,
                "moon_phase": moon_phase,
                # Forecast data
                "hourly": weather_data.hourly[:24],  # First 24 hours
                "daily": weather_data.daily,  # All daily forecasts
            }

            # Get the template with the extended environment
            template = template_env.get_template("dashboard.html.j2")

            # Render the template
            html = template.render(**context)

            return html
        except jinja2.exceptions.TemplateError as e:
            error_location = get_error_location()
            self.logger.error(f"Template error [{error_location}]: {e}")
            raise
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error generating HTML [{error_location}]: {e}")
            raise

    def _get_battery_icon(self, battery_status: BatteryStatus) -> str:
        """Get the appropriate battery icon ID from sprite.

        Args:
            battery_status: Battery status information.

        Returns:
            Icon ID from the sprite.
        """
        return get_battery_icon(battery_status)

    def _get_weather_icon(self, icon_code: str) -> str:
        """Convert OpenWeatherMap icon code to our sprite icon ID.

        Args:
            icon_code: OpenWeatherMap icon code (e.g., "01d").

        Returns:
            Icon ID from the sprite file.
        """
        # Map of OpenWeatherMap icon codes to sprite icon IDs
        icon_map = {
            "01d": "sun-bold",  # Clear sky (day)
            "01n": "moon-bold",  # Clear sky (night)
            "02d": "sun-cloud-bold",  # Few clouds (day)
            "02n": "moon-cloud-bold",  # Few clouds (night)
            "03d": "cloud-bold",  # Scattered clouds
            "03n": "cloud-bold",
            "04d": "clouds-bold",  # Broken clouds
            "04n": "clouds-bold",
            "09d": "cloud-drizzle-bold",  # Shower rain
            "09n": "cloud-drizzle-bold",
            "10d": "sun-cloud-rain-bold",  # Rain (day)
            "10n": "moon-cloud-rain-bold",  # Rain (night)
            "11d": "cloud-lightning-bold",  # Thunderstorm
            "11n": "cloud-lightning-bold",
            "13d": "cloud-snow-bold",  # Snow
            "13n": "cloud-snow-bold",
            "50d": "cloud-fog-bold",  # Mist
            "50n": "cloud-fog-bold",
        }

        return icon_map.get(icon_code, "cloud-bold")  # Default to cloud if icon not found

    async def render_image(
        self, html: str, width: int, height: int, output_path: Path | None = None
    ) -> bytes | Path:
        """Render HTML to an image.

        Args:
            html: HTML content to render.
            width: Width of the image.
            height: Height of the image.
            output_path: Path to save the image, or None to return bytes.

        Returns:
            Path to the rendered image file, or bytes if output_path is None.
        """
        try:
            from playwright.async_api import async_playwright

            # Use Playwright to render HTML to image
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})

                # Set content
                await page.set_content(html)

                # Wait for any rendering to complete
                await page.wait_for_load_state("networkidle")

                # Take screenshot
                if output_path:
                    await page.screenshot(path=str(output_path), type="png")
                    await browser.close()
                    return output_path
                else:
                    screenshot: bytes = await page.screenshot(type="png")
                    await browser.close()
                    return screenshot
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error rendering image [{error_location}]: {e}")
            raise

    async def render_weather_image(
        self,
        weather_data: WeatherData,
        battery_status: BatteryStatus,
        output_path: Path | None = None,
    ) -> bytes | Path:
        """Render weather data to an image.

        Args:
            weather_data: Weather data to display.
            battery_status: Battery status information.
            output_path: Path to save the image, or None to return bytes.

        Returns:
            Path to the rendered image file, or bytes if output_path is None.
        """
        # Generate HTML
        html = await self.generate_html(weather_data, battery_status)

        # Render to image
        return await self.render_image(
            html, self.config.display.width, self.config.display.height, output_path
        )
