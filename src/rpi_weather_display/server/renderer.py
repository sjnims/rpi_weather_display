"""Weather data rendering module for creating display images.

Provides functionality to render weather data into HTML and convert it to
images suitable for display on the e-paper screen using Playwright.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import jinja2

from rpi_weather_display.constants import (
    AQI_LEVELS,
    HPA_TO_INHG,
    HPA_TO_MMHG,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    UVI_CACHE_FILENAME,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.models.weather import (
    CurrentWeather,
    HourlyWeather,
    WeatherCondition,
    WeatherData,
)
from rpi_weather_display.server.browser_manager import browser_manager
from rpi_weather_display.server.moon_phase_helper import MoonPhaseHelper
from rpi_weather_display.server.wind_helper import WindHelper
from rpi_weather_display.utils import file_utils, get_battery_icon, path_resolver
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
        self.last_weather_data = None  # Store the last weather data for icon lookup

        # Set up Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir), autoescape=True
        )

        # Add custom filters
        self.jinja_env.filters["format_datetime"] = self._format_datetime
        self.jinja_env.filters["format_temp"] = self._format_temp
        self.jinja_env.filters["get_icon"] = self._get_weather_icon
        self.jinja_env.filters["weather_icon"] = self._get_weather_icon

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

    def _format_time(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a datetime object or Unix timestamp as a time string.

        Uses AM/PM format without leading zeros for hours by default,
        or the specified format from config if provided.

        Args:
            dt: Datetime object or Unix timestamp.
            format_str: Format string to use (or None to use config's time_format or default).
                        Should be a valid strftime format string like "%H:%M" or "%I:%M %p".

        Returns:
            Formatted time string.
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)

            # Use format from config, or default to AM/PM without leading zeros
        if format_str is None:
            # Check if config has a time_format setting
            if (
                hasattr(self.config.display, "time_format")
                and self.config.display.time_format is not None
            ):
                format_str = self.config.display.time_format
                return dt.strftime(format_str)
            else:
                # Default to AM/PM format without leading zeros
                hour = dt.hour % 12
                if hour == 0:
                    hour = 12  # 12-hour clock shows 12 for noon/midnight, not 0
                return f"{hour}:{dt.minute:02d} {dt.strftime('%p')}"
        else:
            # Use the provided format
            return dt.strftime(format_str)

    def _format_datetime_display(self, dt: datetime | int, format_str: str | None = None) -> str:
        """Format a datetime for display using config or a default format without leading zeros.

        Args:
            dt: Datetime object or Unix timestamp
            format_str: Optional format string to override config. Should be a valid strftime
                       format string like "%m/%d/%Y %I:%M %p"

        Returns:
            Formatted datetime string in the format specified by
            config.display.display_datetime_format,
            or if not configured, defaults to "MM/DD/YYYY HH:MM AM/PM" format without leading zeros
        """
        if isinstance(dt, int):
            dt = datetime.fromtimestamp(dt)

        # Check for format in arguments, then config, then use default
        if format_str is not None:
            return dt.strftime(format_str)

        # Check for display_datetime_format in config
        if (
            hasattr(self.config.display, "display_datetime_format")
            and self.config.display.display_datetime_format
        ):
            return dt.strftime(self.config.display.display_datetime_format)

        # Default format: MM/DD/YYYY HH:MM AM/PM without leading zeros
        month = dt.month
        day = dt.day
        year = dt.year
        hour = dt.hour % 12
        if hour == 0:
            hour = 12  # 12-hour clock shows 12 for noon/midnight, not 0
        minute = dt.minute
        am_pm = dt.strftime("%p")

        return f"{month}/{day}/{year} {hour}:{minute:02d} {am_pm}"

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

        # Current times (sunrise/sunset)
        current_times = {"sunrise_local": "", "sunset_local": ""}
        if hasattr(weather_data.current, "sunrise") and weather_data.current.sunrise:
            sunrise_dt = datetime.fromtimestamp(weather_data.current.sunrise)
            current_times["sunrise_local"] = self._format_time(sunrise_dt, time_format)
        if hasattr(weather_data.current, "sunset") and weather_data.current.sunset:
            sunset_dt = datetime.fromtimestamp(weather_data.current.sunset)
            current_times["sunset_local"] = self._format_time(sunset_dt, time_format)

        # Daily forecast times
        daily_times: list[dict[str, str]] = []
        for day in weather_data.daily:
            day_times = {"sunrise_local": "", "sunset_local": "", "weekday_short": ""}
            if hasattr(day, "sunrise") and day.sunrise:
                sunrise_dt = datetime.fromtimestamp(day.sunrise)
                day_times["sunrise_local"] = self._format_time(sunrise_dt, time_format)
            if hasattr(day, "sunset") and day.sunset:
                sunset_dt = datetime.fromtimestamp(day.sunset)
                day_times["sunset_local"] = self._format_time(sunset_dt, time_format)
            if hasattr(day, "dt") and day.dt:
                day_dt = datetime.fromtimestamp(day.dt)
                day_times["weekday_short"] = day_dt.strftime("%a")
            daily_times.append(day_times)

        # Hourly forecast times
        hourly_times: list[dict[str, str]] = []
        hourly_count = self.config.weather.hourly_forecast_count
        for hour in weather_data.hourly[:hourly_count]:
            hour_dt = datetime.fromtimestamp(hour.dt)
            hourly_times.append(
                {
                    "local_time": self._format_time(hour_dt, time_format),
                    "hour": str(hour_dt.hour if hour_dt.hour <= 12 else hour_dt.hour - 12),
                    "ampm": hour_dt.strftime("%p").lower(),
                }
            )

        return current_times, daily_times, hourly_times

    def _prepare_units(self) -> dict[str, str | bool]:
        """Prepare unit strings based on configuration.

        Returns:
            Dictionary with unit strings for temperature, wind, precipitation, and pressure
        """
        is_metric = self.config.weather.units == "metric"
        return {
            "is_metric": is_metric,
            "units_temp": "°C" if is_metric else "°F",
            "units_wind": "m/s" if is_metric else "mph",
            "units_precip": "mm" if is_metric else "in",
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
            daylight_seconds = weather_data.current.sunset - weather_data.current.sunrise
            daylight_hours = daylight_seconds // SECONDS_PER_HOUR
            daylight_minutes = (daylight_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
            return f"{daylight_hours}h {daylight_minutes}m"
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
            max_uvi, max_uvi_timestamp = self._get_daily_max_uvi(weather_data, now)
            if max_uvi > 0.0:
                uvi_max = f"{max_uvi:.1f}"
                uvi_time = self._format_time(
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
        if hasattr(weather_data, "air_pollution") and weather_data.air_pollution is not None:
            aqi_value = weather_data.air_pollution.aqi
            return AQI_LEVELS.get(aqi_value, "Unknown")
        return "Unknown"

    def _setup_jinja_filters(self) -> None:
        """Set up custom Jinja2 filters and globals."""
        # Weather icon filter
        def weather_icon_filter(weather_item: WeatherCondition) -> str:
            """Convert weather item to icon."""
            if hasattr(weather_item, "id") and hasattr(weather_item, "icon"):
                weather_id = str(weather_item.id)
                icon_code = weather_item.icon

                # For IDs 800-804, use the day/night variant
                if weather_id in ["800", "801", "802", "803", "804"]:
                    is_day = icon_code.endswith("d")
                    variant = "d" if is_day else "n"
                    key = f"{weather_id}_{weather_id[0:2]}{variant}"
                    if key in self._weather_icon_map:
                        return self._weather_icon_map[key]

                # Try the exact match first
                key = f"{weather_id}_{icon_code}"
                if key in self._weather_icon_map:
                    return self._weather_icon_map[key]

                # Fall back to just the ID
                if weather_id in self._weather_id_to_icon:
                    return self._weather_id_to_icon[weather_id]

                # Try the icon code as a last resort
                if icon_code in self._weather_icon_map:
                    return self._get_weather_icon(icon_code)

            return "wi-cloud"  # Default fallback

        # Helper functions for precipitation
        def get_precipitation_amount(weather_item: CurrentWeather | HourlyWeather) -> float | None:
            """Extract precipitation amount from weather item."""
            # Check for rain/snow data in the weather item
            # The API returns rain/snow as dicts with "1h" key for current/hourly
            if hasattr(weather_item, "rain") and weather_item.rain:
                return weather_item.rain.get("1h", 0.0)
            if hasattr(weather_item, "snow") and weather_item.snow:
                return weather_item.snow.get("1h", 0.0)
            return None

        def get_hourly_precipitation(hour: HourlyWeather) -> str:
            """Get precipitation amount for an hourly forecast."""
            # First try to get actual precipitation amount
            amount = get_precipitation_amount(hour)
            if amount is not None:
                return f"{amount:.1f}"
            # Fall back to probability of precipitation if available
            if hasattr(hour, "pop"):
                return f"{int(hour.pop * 100)}%"
            return "0"

        # Register filters
        self.jinja_env.filters["weather_icon"] = weather_icon_filter
        self.jinja_env.filters["moon_phase_icon"] = MoonPhaseHelper.get_moon_phase_icon
        self.jinja_env.filters["moon_phase_label"] = MoonPhaseHelper.get_moon_phase_label
        # Wind helper methods need to be wrapped for Jinja compatibility
        def wind_direction_angle_filter(degrees: float) -> float:
            """Wrapper for wind direction angle calculation."""
            return WindHelper.get_wind_direction_angle(degrees)
        
        def wind_direction_cardinal_filter(degrees: float) -> str:
            """Wrapper for wind direction cardinal calculation."""
            return WindHelper.get_wind_direction_cardinal(degrees)
        
        self.jinja_env.filters["wind_direction_angle"] = wind_direction_angle_filter  # type: ignore[assignment]
        self.jinja_env.filters["wind_direction_cardinal"] = wind_direction_cardinal_filter  # type: ignore[assignment]
        # Register precipitation helpers as filters too
        self.jinja_env.filters["get_precipitation_amount"] = get_precipitation_amount  # type: ignore[assignment]
        self.jinja_env.filters["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore[assignment]
        
        # Also register as globals for use in template expressions
        # Type ignore needed due to Jinja2's typing limitations
        self.jinja_env.globals["get_precipitation_amount"] = get_precipitation_amount  # type: ignore[assignment]
        self.jinja_env.globals["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore[assignment]

    async def generate_html(self, weather_data: WeatherData, battery_status: BatteryStatus) -> str:
        """Generate HTML for the weather display.

        Args:
            weather_data: Weather data to display.
            battery_status: Battery status information.

        Returns:
            HTML content as a string.
        """
        try:
            # Store the weather data for icon lookup
            self.last_weather_data = weather_data

            # Ensure weather icon mappings are loaded
            self._ensure_weather_icon_map_loaded()

            # Set up Jinja filters
            self._setup_jinja_filters()

            # Get battery icon based on status
            battery_icon = self._get_battery_icon(battery_status)

            # Calculate current date and time info
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            last_refresh = self._format_datetime_display(now)

            # Prepare time data
            current_times, daily_times, hourly_times = self._prepare_time_data(weather_data, now)

            # Prepare units
            units = self._prepare_units()

            # Calculate weather details
            bft = WindHelper.get_beaufort_scale(weather_data.current.wind_speed)
            daylight = self._calculate_daylight(weather_data)
            uvi_max, uvi_time = self._calculate_max_uvi(weather_data, now)
            aqi = self._get_air_quality_label(weather_data)

            # Convert pressure to the configured units
            raw_pressure = weather_data.current.pressure
            # Ensure pressure units is a string
            pressure_units = units["units_pressure"]
            if isinstance(pressure_units, str):
                pressure = round(self._convert_pressure(raw_pressure, pressure_units), 1)
            else:
                pressure = float(raw_pressure)  # Default to hPa

            # City name (from config or weather data)
            city = self.config.weather.city_name or "Unknown Location"

            # Moon phase - using the actual value from the first day's forecast
            moon_phase = (
                MoonPhaseHelper.get_moon_phase_icon(weather_data.daily[0].moon_phase)
                if weather_data.daily
                else "wi-moon-new"
            )

            # Get template
            template = self.jinja_env.get_template("dashboard.html.j2")

            # Prepare context with all required variables
            hourly_count = self.config.weather.hourly_forecast_count
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
                **units,  # Unpack all unit values
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
                "hourly": weather_data.hourly[:hourly_count],  # Use config value
                "daily": weather_data.daily,  # All daily forecasts
                # Formatted times
                "current_times": current_times,
                "daily_times": daily_times,
                "hourly_times": hourly_times,
            }

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
        # Ensure the weather icon mappings are loaded
        self._ensure_weather_icon_map_loaded()

        # Special handling for conditions with day/night variants (800-804)
        if hasattr(self, "last_weather_data") and self.last_weather_data:
            # Get the weather condition ID from the current weather data
            try:
                weather_id = str(self.last_weather_data.current.weather[0].id)

                # Determine if it's day or night from the icon code
                is_day = icon_code.endswith("d")
                variant = "d" if is_day else "n"

                # For IDs 800-804, use the day/night variant
                if weather_id in ["800", "801", "802", "803", "804"]:
                    key = f"{weather_id}_{weather_id[0:2]}{variant}"
                    if key in self._weather_icon_map:
                        return self._weather_icon_map[key]

                # Try the exact match first
                key = f"{weather_id}_{icon_code}"
                if key in self._weather_icon_map:
                    return self._weather_icon_map[key]

                # Fall back to just the ID
                if weather_id in self._weather_id_to_icon:
                    return self._weather_id_to_icon[weather_id]
            except (AttributeError, IndexError, KeyError):
                # Handle cases where the weather data structure doesn't match expectations
                pass

        # Default mapping as fallback
        icon_map = {
            "01d": "wi-day-sunny",  # Clear sky (day)
            "01n": "wi-night-clear",  # Clear sky (night)
            "02d": "wi-day-cloudy",  # Few clouds (day)
            "02n": "wi-night-cloudy",  # Few clouds (night)
            "03d": "wi-cloud",  # Scattered clouds
            "03n": "wi-cloud",
            "04d": "wi-cloudy",  # Broken clouds
            "04n": "wi-cloudy",
            "09d": "wi-showers",  # Shower rain
            "09n": "wi-showers",
            "10d": "wi-day-rain",  # Rain (day)
            "10n": "wi-night-rain",  # Rain (night)
            "11d": "wi-thunderstorm",  # Thunderstorm
            "11n": "wi-thunderstorm",
            "13d": "wi-snow",  # Snow
            "13n": "wi-snow",
            "50d": "wi-fog",  # Mist
            "50n": "wi-fog",
        }

        return icon_map.get(icon_code, "wi-cloud")  # Default to cloud if icon not found

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
            # Get a page from the browser manager
            page = await browser_manager.get_page(width, height)

            # Set content
            await page.set_content(html)

            # Wait for any rendering to complete
            await page.wait_for_load_state("networkidle")

            # Take screenshot
            if output_path:
                await page.screenshot(path=str(output_path), type="png")
                return output_path
            else:
                screenshot: bytes = await page.screenshot(type="png")
                return screenshot
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error rendering image [{error_location}]: {e}")
            raise RuntimeError("Failed to render image with Playwright") from e
        finally:
            # Always close the page to free memory
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

    def _ensure_weather_icon_map_loaded(self) -> None:
        """Ensure the weather icon mapping dictionaries are loaded."""
        # Load and parse the CSV file once
        if not hasattr(self, "_weather_icon_map"):
            self._weather_icon_map: dict[str, str] = {}
            self._weather_id_to_icon: dict[str, str] = {}

            try:
                import csv
                from io import StringIO

                # Use path_resolver to find the CSV file consistently
                csv_path = path_resolver.get_data_file("owm_icon_map.csv")

                # Check if the CSV file exists
                if not file_utils.file_exists(csv_path):
                    self.logger.warning("Could not find owm_icon_map.csv file")
                    # Don't return here, continue to use the fallback mapping
                else:
                    try:
                        # Read the CSV file content
                        csv_content = file_utils.read_text(csv_path)

                        # Parse using csv reader
                        reader = csv.DictReader(StringIO(csv_content))
                        for row in reader:
                            weather_id = row["API response: id"].strip()
                            icon_code_from_csv = row["API response: icon"].strip()
                            weather_icon_class = row["Weather Icons Class"].strip()

                            # Store by ID and icon code
                            key = f"{weather_id}_{icon_code_from_csv}"
                            self._weather_icon_map[key] = weather_icon_class

                            # Also store just by ID for fallback
                            self._weather_id_to_icon[weather_id] = weather_icon_class
                    except Exception as e:
                        self.logger.error(f"Error reading weather icon mapping: {e}")
            except Exception as e:
                self.logger.error(f"Error loading weather icon mapping: {e}")
                # Fall back to the default mapping
                self._weather_icon_map = {}
                self._weather_id_to_icon = {}

    def _get_daily_max_uvi(self, weather_data: WeatherData, now: datetime) -> tuple[float, int]:
        """Calculate the max UVI for today, persisting between API calls.

        Finds the maximum UV index value from hourly forecasts for the current day
        and persists it in a cache file to maintain the max value between API calls.
        This ensures we track the highest UV value even as it passes.

        Args:
            weather_data: Current weather data object containing hourly forecasts
            now: Current datetime representing the time of the API call

        Returns:
            Tuple of (max_uvi, max_uvi_timestamp) where max_uvi is the maximum UV index
            value for today and max_uvi_timestamp is the Unix timestamp when that maximum
            value is expected
        """
        cache_file = path_resolver.get_cache_file(UVI_CACHE_FILENAME)
        today = now.date()

        # Initialize with current API data
        max_uvi = 0.0
        max_uvi_timestamp = 0

        if hasattr(weather_data.current, "uvi"):
            max_uvi = weather_data.current.uvi
            max_uvi_timestamp = int(now.timestamp())

        # Get today's date range
        today_start_dt = datetime.combine(today, datetime.min.time())
        today_end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time()) - timedelta(
            seconds=1
        )
        today_start = int(today_start_dt.timestamp())
        today_end = int(today_end_dt.timestamp())

        # Check hourly forecast for today's max UVI
        for hour in weather_data.hourly:
            if today_start <= hour.dt <= today_end and hasattr(hour, "uvi") and hour.uvi > max_uvi:
                max_uvi = hour.uvi
                max_uvi_timestamp = hour.dt

        # Try to load cached max UVI for today
        cached_uvi: float | None = None
        cached_timestamp: int | None = None
        should_update_cache = True

        if file_utils.file_exists(cache_file):
            try:
                cache_data = file_utils.read_json(cache_file)
                # Type guard for the JSON data
                if (
                    isinstance(cache_data, dict)
                    and "date" in cache_data
                    and isinstance(cache_data["date"], str)
                ):
                    cache_date = datetime.fromisoformat(cache_data["date"]).date()

                    # If cache is from today, compare with current max
                    if cache_date == today:
                        # Type guards for the cache values
                        max_uvi_value = cache_data.get("max_uvi")
                        timestamp_value = cache_data.get("timestamp")
                        if isinstance(max_uvi_value, int | float) and isinstance(
                            timestamp_value, int
                        ):
                            cached_uvi = float(max_uvi_value)
                            cached_timestamp = timestamp_value

                            # Use the higher value
                            if cached_uvi > max_uvi:
                                max_uvi = cached_uvi
                                max_uvi_timestamp = cached_timestamp
                                # Don't update cache when using cached value
                                should_update_cache = False
            except Exception as e:
                self.logger.debug(f"Error reading UVI cache: {e}")

        # Save the current max for today only if we have a new higher value
        if should_update_cache:
            try:
                cache_data = {
                    "date": today.isoformat(),
                    "max_uvi": max_uvi,
                    "timestamp": max_uvi_timestamp,
                }
                file_utils.write_json(cache_file, cache_data)  # type: ignore[arg-type]
            except Exception as e:
                self.logger.warning(f"Failed to cache max UVI: {e}")

        # Ensure we never return None values
        return max_uvi or 0.0, max_uvi_timestamp or 0

    def _convert_pressure(self, pressure_hpa: float, target_units: str) -> float:
        """Convert pressure from hPa to the target units.

        Args:
            pressure_hpa: Pressure in hectopascals (hPa)
            target_units: Target units ("hPa", "mmHg", or "inHg")

        Returns:
            Converted pressure value
        """
        if target_units == "mmHg":
            return pressure_hpa * HPA_TO_MMHG
        elif target_units == "inHg":
            return pressure_hpa * HPA_TO_INHG
        else:  # hPa
            return pressure_hpa