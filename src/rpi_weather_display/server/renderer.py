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

            # Get battery icon based on status
            battery_icon = self._get_battery_icon(battery_status)

            # Calculate current date and time info
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            last_refresh = now.strftime(self.config.display.timestamp_format)

            # Format sunrise and sunset times
            time_format = "%H:%M"

            # Create dictionaries for formatted times with default empty values
            current_times = {"sunrise_local": "", "sunset_local": ""}

            # Only process if these attributes exist and have values
            if hasattr(weather_data.current, "sunrise") and weather_data.current.sunrise:
                sunrise_dt = datetime.fromtimestamp(weather_data.current.sunrise)
                current_times["sunrise_local"] = sunrise_dt.strftime(time_format)

            if hasattr(weather_data.current, "sunset") and weather_data.current.sunset:
                sunset_dt = datetime.fromtimestamp(weather_data.current.sunset)
                current_times["sunset_local"] = sunset_dt.strftime(time_format)

            # Format daily forecast times - simplified to improve coverage
            daily_times: list[dict[str, str]] = []
            for day in weather_data.daily:
                # Initialize with default empty values
                day_times = {"sunrise_local": "", "sunset_local": "", "weekday_short": ""}

                # Format sunrise time
                if hasattr(day, "sunrise") and day.sunrise:
                    day_times["sunrise_local"] = datetime.fromtimestamp(day.sunrise).strftime(
                        time_format
                    )

                # Format sunset time
                if hasattr(day, "sunset") and day.sunset:
                    day_times["sunset_local"] = datetime.fromtimestamp(day.sunset).strftime(
                        time_format
                    )

                # Add weekday for the day forecast
                if hasattr(day, "dt") and day.dt:
                    day_times["weekday_short"] = datetime.fromtimestamp(day.dt).strftime("%a")

                daily_times.append(day_times)

            # Format hourly forecast times
            hourly_times: list[dict[str, str]] = []
            hourly_count = self.config.weather.hourly_forecast_count
            for hour in weather_data.hourly[:hourly_count]:  # Use config value
                hour_dt = datetime.fromtimestamp(hour.dt)
                hourly_times.append(
                    {
                        "local_time": hour_dt.strftime("%H:%M"),
                        "hour": hour_dt.strftime("%H"),
                        "ampm": hour_dt.strftime("%p").lower(),
                    }
                )

            # Set up units based on config
            is_metric = self.config.weather.units == "metric"
            units_temp = "°C" if is_metric else "°F"
            units_wind = "m/s" if is_metric else "mph"
            units_precip = "mm" if is_metric else "in"
            units_pressure = "hPa"  # Standard unit regardless of system

            # Handle Beaufort scale for wind (simplified)
            bft = min(int(weather_data.current.wind_speed / 3.5) + 1, 12)

            # Prepare mock data for fields that require calculation
            # Calculate daylight hours from sunrise and sunset
            if hasattr(weather_data.current, "sunrise") and hasattr(weather_data.current, "sunset"):
                daylight_seconds = weather_data.current.sunset - weather_data.current.sunrise
                daylight_hours = daylight_seconds // 3600
                daylight_minutes = (daylight_seconds % 3600) // 60
                daylight = f"{daylight_hours}h {daylight_minutes}m"
            else:
                daylight = "12h 30m"  # Fallback value if sunrise/sunset not available

                # Calculate maximum UV index and its time from hourly forecast
            uvi_max = "0"
            uvi_time = "N/A"

            if weather_data.hourly:
                max_uvi = 0.0
                max_uvi_timestamp = 0

                # Find max UV index in the next 24 hours
                for hour in weather_data.hourly[:24]:  # Limit to 24 hours
                    if hasattr(hour, "uvi"):
                        if hour.uvi > max_uvi:
                            max_uvi = hour.uvi
                            max_uvi_timestamp = hour.dt

                if max_uvi > 0.0:
                    uvi_max = f"{max_uvi:.1f}"
                    uvi_time = datetime.fromtimestamp(max_uvi_timestamp).strftime(time_format)
            aqi = "Good"  # Mock value - would need air quality
            pressure = weather_data.current.pressure

            # City name (from config or weather data)
            city = self.config.weather.city_name or "Unknown Location"

            # Helper function for precipitation amount
            def get_precipitation_amount(
                weather_item: CurrentWeather | HourlyWeather,
            ) -> float | None:
                """Extract precipitation amount from weather item."""
                # Return None for now to keep it simple
                return None

            # Helper function for hourly precipitation
            def get_hourly_precipitation(hour: HourlyWeather) -> str:
                """Get precipitation amount for an hourly forecast."""
                # Return zero for simplicity
                return "0"

            # Helper filter for weather icons
            def weather_icon_filter(weather_item: WeatherCondition) -> str:
                """Convert weather item to icon."""
                if hasattr(weather_item, "id") and hasattr(weather_item, "icon"):
                    # Use the same icon mapping logic that _get_weather_icon uses
                    # Extract weather ID and icon code
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

                # Default fallback
                return "wi-cloud"

            # Helper filter for moon phase
            def moon_phase_icon_filter(phase: float | None) -> str:
                """Get moon phase icon filename based on phase value (0-1).

                The phase is a floating value between 0 and 1 representing the moon cycle:
                0: New Moon
                0.25: First Quarter
                0.5: Full Moon
                0.75: Last/Third Quarter

                Alt moon icons (wi-moon-alt-*) show the shadowed part of the moon with an outline.

                Args:
                    phase: Moon phase value (0-1)

                Returns:
                    Classname for the matching moon phase icon
                """
                if phase is None:
                    return "wi-moon-alt-new"

                phases = [
                    "new",  # 0
                    "waxing-crescent-1",  # 0.04
                    "waxing-crescent-2",  # 0.08
                    "waxing-crescent-3",  # 0.12
                    "waxing-crescent-4",  # 0.16
                    "waxing-crescent-5",  # 0.20
                    "waxing-crescent-6",  # 0.24
                    "first-quarter",  # 0.25
                    "waxing-gibbous-1",  # 0.29
                    "waxing-gibbous-2",  # 0.33
                    "waxing-gibbous-3",  # 0.37
                    "waxing-gibbous-4",  # 0.41
                    "waxing-gibbous-5",  # 0.45
                    "waxing-gibbous-6",  # 0.49
                    "full",  # 0.5
                    "waning-gibbous-1",  # 0.54
                    "waning-gibbous-2",  # 0.58
                    "waning-gibbous-3",  # 0.62
                    "waning-gibbous-4",  # 0.66
                    "waning-gibbous-5",  # 0.70
                    "waning-gibbous-6",  # 0.74
                    "third-quarter",  # 0.75
                    "waning-crescent-1",  # 0.79
                    "waning-crescent-2",  # 0.83
                    "waning-crescent-3",  # 0.87
                    "waning-crescent-4",  # 0.91
                    "waning-crescent-5",  # 0.95
                    "waning-crescent-6",  # 0.99
                ]
                index = min(int(phase * 28), 27)  # Ensure index is within bounds
                return f"wi-moon-alt-{phases[index]}"

            # Helper filter for moon phase label
            def moon_phase_label_filter(phase: float | None) -> str:
                """Get text label for moon phase based on phase value (0-1).

                Args:
                    phase: Moon phase value (0-1)

                Returns:
                    Text label describing the moon phase
                """
                if phase is None:
                    return "New Moon"

                # These labels match the key phase points in the 28-day cycle
                labels = [
                    "New Moon",  # 0
                    "Waxing Crescent",  # 0.04-0.24
                    "First Quarter",  # 0.25
                    "Waxing Gibbous",  # 0.29-0.49
                    "Full Moon",  # 0.5
                    "Waning Gibbous",  # 0.54-0.74
                    "Last Quarter",  # 0.75
                    "Waning Crescent",  # 0.79-0.99
                ]

                # Get the general phase category
                if phase == 0 or phase >= 0.97:
                    return labels[0]  # New Moon
                elif phase < 0.24:
                    return labels[1]  # Waxing Crescent
                elif phase < 0.27:
                    return labels[2]  # First Quarter
                elif phase < 0.49:
                    return labels[3]  # Waxing Gibbous
                elif phase < 0.52:
                    return labels[4]  # Full Moon
                elif phase < 0.74:
                    return labels[5]  # Waning Gibbous
                elif phase < 0.77:
                    return labels[6]  # Last Quarter
                else:
                    return labels[7]  # Waning Crescent

            # Moon phase - using the actual value from the first day's forecast
            moon_phase = (
                moon_phase_icon_filter(weather_data.daily[0].moon_phase)
                if weather_data.daily
                else "wi-moon-new"
            )

            # Helper filter for wind direction angle
            def wind_direction_angle_filter(deg: float) -> float:
                """Convert wind direction to rotation angle."""
                return deg  # Pass through as is

            # Register custom filters/functions for the template render
            # Use the original environment directly for better test coverage
            self.jinja_env.filters["weather_icon"] = weather_icon_filter
            self.jinja_env.filters["moon_phase_icon"] = moon_phase_icon_filter
            self.jinja_env.filters["moon_phase_label"] = moon_phase_label_filter
            self.jinja_env.filters["wind_direction_angle"] = wind_direction_angle_filter  # type: ignore

            # Register template globals
            self.jinja_env.globals["get_precipitation_amount"] = get_precipitation_amount  # type: ignore
            self.jinja_env.globals["get_hourly_precipitation"] = get_hourly_precipitation  # type: ignore

            # Get the template using the original environment
            template = self.jinja_env.get_template("dashboard.html.j2")

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

    def _ensure_weather_icon_map_loaded(self) -> None:
        """Ensure the weather icon mapping dictionaries are loaded."""
        # Load and parse the CSV file once
        if not hasattr(self, "_weather_icon_map"):
            self._weather_icon_map: dict[str, str] = {}
            self._weather_id_to_icon: dict[str, str] = {}

            try:
                import csv
                from pathlib import Path

                # Try different approaches to find the CSV file
                possible_paths = [
                    Path("owm_icon_map.csv"),  # Current working directory
                    Path(__file__).parent.parent.parent.parent / "owm_icon_map.csv",  # Project root
                ]

                csv_path = None
                for path in possible_paths:
                    if path.exists():
                        csv_path = path
                        break

                if csv_path is None:
                    self.logger.warning("Could not find owm_icon_map.csv file")
                    # Don't return here, continue to use the fallback mapping
                else:
                    try:
                        with open(csv_path) as f:
                            reader = csv.DictReader(f)
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
