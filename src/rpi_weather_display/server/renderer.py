import logging
from datetime import datetime
from pathlib import Path

import jinja2

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.models.weather import WeatherData


class WeatherRenderer:
    """Renderer for weather data to e-paper display images."""

    def __init__(self, config: AppConfig, template_dir: Path):
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
            template = self.jinja_env.get_template("weather.html.j2")

            # Get battery icon based on status
            battery_icon = self._get_battery_icon(battery_status)

            # Prepare template context
            context = {
                "weather": weather_data,
                "battery": battery_status,
                "battery_icon": battery_icon,
                "config": self.config,
                "last_updated": datetime.now(),
                "is_metric": self.config.weather.units == "metric",
            }

            # Render the template
            html = template.render(**context)

            return html
        except jinja2.exceptions.TemplateError as e:
            self.logger.error(f"Template error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error generating HTML: {e}")
            raise

    def _get_battery_icon(self, battery_status: BatteryStatus) -> str:
        """Get the appropriate battery icon ID from sprite.

        Args:
            battery_status: Battery status information.

        Returns:
            Icon ID from the sprite.
        """
        if battery_status.state == "charging":
            return "battery-charging-bold"
        elif battery_status.level == 0:
            return "battery-empty-bold"
        elif battery_status.level > 80:
            return "battery-full-bold"
        elif battery_status.level > 30:
            return "battery-high-bold"
        else:
            return "battery-low-bold"

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
                    screenshot = await page.screenshot(type="png")
                    await browser.close()
                    return screenshot
        except Exception as e:
            self.logger.error(f"Error rendering image: {e}")
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
