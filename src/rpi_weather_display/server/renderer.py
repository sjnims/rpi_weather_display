"""Weather data rendering module for creating display images.

Provides functionality to render weather data into HTML and convert it to
images suitable for display on the e-paper screen using Playwright.
"""

import logging
from datetime import datetime
from pathlib import Path

import jinja2

from rpi_weather_display.constants import AQI_LEVELS
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.models.weather import (
    DailyWeather,
    HourlyWeather,
    WeatherData,
)
from rpi_weather_display.server.browser_manager import browser_manager
from rpi_weather_display.server.moon_phase_helper import MoonPhaseHelper
from rpi_weather_display.server.template_filter_manager import TemplateFilterManager
from rpi_weather_display.server.time_formatter import TimeFormatter
from rpi_weather_display.server.weather_calculator import WeatherCalculator
from rpi_weather_display.server.weather_icon_mapper import WeatherIconMapper
from rpi_weather_display.server.wind_helper import WindHelper
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
        
        # Initialize helper components
        self.time_formatter = TimeFormatter(config.display)
        self.weather_calculator = WeatherCalculator()
        self.icon_mapper = WeatherIconMapper()

        # Set up Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir), autoescape=True
        )
        
        # Set up template filters
        self.filter_manager = TemplateFilterManager(self.jinja_env, self.icon_mapper)

        # Register initial filters
        self._register_basic_filters()

    def _register_basic_filters(self) -> None:
        """Register basic Jinja2 filters."""
        # Time formatting filters
        self.jinja_env.filters["format_datetime"] = self.time_formatter.format_datetime
        self.jinja_env.filters["format_temp"] = self._format_temp
        self.jinja_env.filters["get_icon"] = self._get_weather_icon
        self.jinja_env.filters["weather_icon"] = self._get_weather_icon

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

    def _prepare_time_data(
        self, weather_data: WeatherData, now: datetime
    ) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
        """Prepare time-related data for the template.

        Args:
            weather_data: Weather data containing forecasts
            now: Current datetime (currently unused but kept for API compatibility)

        Returns:
            Tuple of (current_times, daily_times, hourly_times)
        """
        _ = now  # Mark as intentionally unused
        time_format = self.config.display.time_format

        # Prepare all time data
        current_times = self._prepare_current_times(weather_data.current, time_format)
        daily_times = self._prepare_daily_times(weather_data.daily, time_format)
        hourly_times = self._prepare_hourly_times(
            weather_data.hourly, time_format, self.config.weather.hourly_forecast_count
        )

        return current_times, daily_times, hourly_times

    def _prepare_current_times(self, current: object, time_format: str | None) -> dict[str, str]:
        """Prepare current weather time data.
        
        Args:
            current: Current weather data object
            time_format: Time format string
            
        Returns:
            Dictionary with sunrise and sunset times
        """
        return {
            "sunrise_local": self.time_formatter.format_timestamp_if_exists(
                current, "sunrise", time_format
            ),
            "sunset_local": self.time_formatter.format_timestamp_if_exists(
                current, "sunset", time_format
            ),
        }

    def _prepare_daily_times(
        self, daily_forecast: list[DailyWeather], time_format: str | None
    ) -> list[dict[str, str]]:
        """Prepare daily forecast time data.
        
        Args:
            daily_forecast: List of daily forecast objects
            time_format: Time format string
            
        Returns:
            List of dictionaries with daily time data
        """
        daily_times: list[dict[str, str]] = []
        for day in daily_forecast:
            weekday_short = ""
            if hasattr(day, "dt") and day.dt:
                weekday_short = self.time_formatter.get_weekday_short(day.dt)
            
            day_times: dict[str, str] = {
                "sunrise_local": self.time_formatter.format_timestamp_if_exists(
                    day, "sunrise", time_format
                ),
                "sunset_local": self.time_formatter.format_timestamp_if_exists(
                    day, "sunset", time_format
                ),
                "weekday_short": weekday_short,
            }
            daily_times.append(day_times)
        return daily_times

    def _prepare_hourly_times(
        self, hourly_forecast: list[HourlyWeather], time_format: str | None, count: int
    ) -> list[dict[str, str]]:
        """Prepare hourly forecast time data.
        
        Args:
            hourly_forecast: List of hourly forecast objects
            time_format: Time format string
            count: Number of hours to include
            
        Returns:
            List of dictionaries with hourly time data
        """
        hourly_times: list[dict[str, str]] = []
        for hour in hourly_forecast[:count]:
            hour_dt = datetime.fromtimestamp(hour.dt)
            hour_12 = hour_dt.hour if hour_dt.hour <= 12 else hour_dt.hour - 12
            hourly_times.append({
                "local_time": self.time_formatter.format_time(hour_dt, time_format),
                "hour": str(hour_12),
                "ampm": hour_dt.strftime("%p").lower(),
            })
        return hourly_times

    def _prepare_units(self) -> dict[str, str | bool]:
        """Prepare unit strings based on configuration.

        Returns:
            Dictionary with unit strings for temperature, wind, precipitation, and pressure
        """
        # Determine if using metric system based on weather units config
        is_metric = self.config.weather.units == "metric"
        
        return {
            "is_metric": is_metric,
            "units_temp": "°C" if is_metric else "°F",
            "units_wind": "m/s" if is_metric else "mph",
            "units_precip": "mm" if is_metric else "in",
            # Pressure units can be independently configured (hPa, mmHg, inHg)
            "units_pressure": self.config.display.pressure_units,
        }

    def _calculate_daylight(self, weather_data: WeatherData) -> str:
        """Calculate daylight hours from sunrise and sunset.

        Args:
            weather_data: Weather data with current conditions

        Returns:
            Formatted daylight duration string
        """
        if hasattr(weather_data.current, "sunrise") and hasattr(weather_data.current, "sunset"):
            return self.weather_calculator.calculate_daylight_hours(
                weather_data.current.sunrise, weather_data.current.sunset
            )
        return "12h 30m"  # Fallback value

    def _calculate_max_uvi(self, weather_data: WeatherData, now: datetime) -> tuple[str, str]:
        """Calculate maximum UV index and its time.

        Args:
            weather_data: Weather data with hourly forecast
            now: Current datetime

        Returns:
            Tuple of (max_uvi_string, time_string)
        """
        uvi_max = "0"
        uvi_time = "N/A"

        if weather_data.hourly:
            max_uvi, max_uvi_timestamp = self.weather_calculator.get_daily_max_uvi(
                weather_data, now
            )
            if max_uvi > 0.0:
                uvi_max = f"{max_uvi:.1f}"
                uvi_time = self.time_formatter.format_time(
                    datetime.fromtimestamp(max_uvi_timestamp), self.config.display.time_format
                )

        return uvi_max, uvi_time

    def _get_air_quality_label(self, weather_data: WeatherData) -> str:
        """Get air quality label from weather data.

        Args:
            weather_data: Weather data potentially containing air pollution info

        Returns:
            Air quality label string
        """
        # Air pollution data is optional and may not be included in the response
        if hasattr(weather_data, "air_pollution") and weather_data.air_pollution is not None:
            aqi_value = weather_data.air_pollution.aqi
            # AQI_LEVELS maps numeric AQI values (1-5) to descriptive labels
            return AQI_LEVELS.get(aqi_value, "Unknown")
        return "Unknown"

    def _build_template_context(
        self, weather_data: WeatherData, battery_status: BatteryStatus
    ) -> dict[str, object]:
        """Build the complete template context.
        
        Args:
            weather_data: Weather data to display
            battery_status: Battery status information
            
        Returns:
            Dictionary containing all template variables
        """
        # Current date and time
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        last_refresh = self.time_formatter.format_datetime_display(now)
        
        # Prepare time data
        current_times, daily_times, hourly_times = self._prepare_time_data(weather_data, now)
        
        # Prepare units
        units = self._prepare_units()
        
        # Calculate weather metrics
        weather_metrics = self._calculate_weather_metrics(weather_data, now, units)
        
        # Get display elements
        display_elements = self._get_display_elements(weather_data, battery_status)
        
        # Build and return complete context
        hourly_count = self.config.weather.hourly_forecast_count
        return {
            # Main data objects
            "weather": weather_data,
            "battery": battery_status,
            "battery_status": battery_status,
            "battery_icon": display_elements["battery_icon"],
            "config": self.config,
            # Date and time
            "date": date_str,
            "last_updated": now,
            "last_refresh": last_refresh,
            # Units
            **units,
            # Location
            "city": display_elements["city"],
            # Weather metrics
            **weather_metrics,
            # Display elements
            "moon_phase": display_elements["moon_phase"],
            # Forecast data
            "hourly": weather_data.hourly[:hourly_count],
            "daily": weather_data.daily,
            # Formatted times
            "current_times": current_times,
            "daily_times": daily_times,
            "hourly_times": hourly_times,
        }
    
    def _calculate_weather_metrics(
        self, weather_data: WeatherData, now: datetime, units: dict[str, str | bool]
    ) -> dict[str, object]:
        """Calculate various weather metrics.
        
        Args:
            weather_data: Weather data
            now: Current datetime
            units: Units configuration
            
        Returns:
            Dictionary of calculated metrics
        """
        # Calculate Beaufort wind force scale (0-12) from wind speed
        bft = WindHelper.get_beaufort_scale(weather_data.current.wind_speed)
        
        # Calculate total daylight hours for today
        daylight = self._calculate_daylight(weather_data)
        
        # Find maximum UV index for today (cached to persist across API calls)
        uvi_max, uvi_time = self._calculate_max_uvi(weather_data, now)
        
        # Get air quality description from AQI value
        aqi = self._get_air_quality_label(weather_data)
        
        # Convert pressure to user's preferred units
        raw_pressure = weather_data.current.pressure  # Always in hPa from API
        pressure_units = units["units_pressure"]
        if isinstance(pressure_units, str):
            # Convert from hPa to mmHg or inHg if configured
            pressure = round(
                self.weather_calculator.convert_pressure(raw_pressure, pressure_units), 1
            )
        else:
            # Fallback to raw hPa value if units not properly configured
            pressure = float(raw_pressure)
            
        return {
            "bft": bft,
            "daylight": daylight,
            "uvi_max": uvi_max,
            "uvi_time": uvi_time,
            "aqi": aqi,
            "pressure": pressure,
        }
    
    def _get_display_elements(
        self, weather_data: WeatherData, battery_status: BatteryStatus
    ) -> dict[str, str]:
        """Get various display elements.
        
        Args:
            weather_data: Weather data
            battery_status: Battery status
            
        Returns:
            Dictionary of display elements
        """
        return {
            "battery_icon": self._get_battery_icon(battery_status),
            "city": self.config.weather.city_name or "Unknown Location",
            "moon_phase": (
                MoonPhaseHelper.get_moon_phase_icon(weather_data.daily[0].moon_phase)
                if weather_data.daily
                else "wi-moon-new"
            ),
        }

    def _setup_jinja_filters(self) -> None:
        """Set up custom Jinja2 filters and globals."""
        # Delegate to the filter manager
        self.filter_manager.register_all_filters()

    async def generate_html(self, weather_data: WeatherData, battery_status: BatteryStatus) -> str:
        """Generate HTML for the weather display.

        Args:
            weather_data: Weather data to display.
            battery_status: Battery status information.

        Returns:
            HTML content as a string.
        """
        try:
            # Set up Jinja filters
            self._setup_jinja_filters()

            # Build template context
            context = self._build_template_context(weather_data, battery_status)

            # Get and render template
            template = self.jinja_env.get_template("dashboard.html.j2")
            html = template.render(**context)

            return html
        except jinja2.exceptions.TemplateError as e:
            error_location = get_error_location()
            self.logger.error(f"Template error [{error_location}]: {e}")
            raise
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error generating HTML [{error_location}]: {e}")
            raise RuntimeError("Failed to generate HTML for weather display") from e

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
        return self.icon_mapper.get_icon_for_code(icon_code)

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
        page = None
        try:
            # Get a page instance from the browser pool (managed for performance)
            page = await browser_manager.get_page(width, height)

            # Load the HTML content into the page
            await page.set_content(html)

            # Wait for all network resources to load (fonts, images, etc.)
            await page.wait_for_load_state("networkidle")

            # Capture screenshot - either to file or memory
            if output_path:
                await page.screenshot(path=str(output_path), type="png")
                return output_path
            else:
                # Return raw bytes for direct transmission
                screenshot: bytes = await page.screenshot(type="png")
                return screenshot
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error rendering image [{error_location}]: {e}")
            raise RuntimeError("Failed to render image with Playwright") from e
        finally:
            # Critical: Always close the page to prevent memory leaks
            if page:
                await page.close()

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


