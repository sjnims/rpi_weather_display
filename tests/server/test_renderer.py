"""Tests for the WeatherRenderer class.

This module tests the functionality of the renderer module, which is responsible
for generating HTML and images from weather data.
"""

# ruff: noqa: S101
# pyright: reportPrivateUsage=false

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jinja2
import pytest

from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.models.weather import (
    CurrentWeather,
    DailyFeelsLike,
    DailyTemp,
    DailyWeather,
    HourlyWeather,
    WeatherCondition,
    WeatherData,
)
from rpi_weather_display.server.renderer import WeatherRenderer


@pytest.fixture()
def config() -> AppConfig:
    """Create a test configuration."""
    return AppConfig(
        weather=WeatherConfig(
            api_key="test_key",
            units="metric",
            location={"lat": 51.5074, "lon": -0.1278},
            city_name="London",
        ),
        display=DisplayConfig(
            width=800,
            height=600,
            timestamp_format="%Y-%m-%d %H:%M",
        ),
        power=PowerConfig(
            quiet_hours_start="23:00",
            quiet_hours_end="06:00",
            low_battery_threshold=20,
            critical_battery_threshold=10,
            wake_up_interval_minutes=60,
        ),
        server=ServerConfig(
            url="http://localhost",
            port=8000,
            timeout_seconds=10,
        ),
    )


@pytest.fixture()
def template_dir(tmp_path: Path) -> Path:
    """Create a temporary template directory with a minimal template."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create a minimal template file
    template_file = template_dir / "weather.html.j2"
    template_file.write_text("""
    <!DOCTYPE html>
    <html>
    <head><title>Weather</title></head>
    <body>
        <h1>{{ weather.current.weather[0].main }}</h1>
        <p>Temperature: {{ weather.current.temp|format_temp }}</p>
        <p>Last Updated: {{ last_updated|format_datetime }}</p>
        <div class="battery">
            <svg><use xlink:href="#{{ battery_icon }}"></use></svg>
            <span>{{ battery.level }}%</span>
        </div>
    </body>
    </html>
    """)

    return template_dir


@pytest.fixture()
def weather_condition() -> WeatherCondition:
    """Create a test weather condition."""
    return WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")


@pytest.fixture()
def current_weather(weather_condition: WeatherCondition) -> CurrentWeather:
    """Create test current weather data."""
    return CurrentWeather(
        dt=int(datetime.now().timestamp()),
        sunrise=int(datetime(2023, 5, 20, 5, 0).timestamp()),
        sunset=int(datetime(2023, 5, 20, 21, 0).timestamp()),
        temp=20.5,
        feels_like=22.0,
        pressure=1013,
        humidity=65,
        dew_point=12.5,
        uvi=5.2,
        clouds=10,
        visibility=10000,
        wind_speed=3.5,
        wind_deg=270,
        weather=[weather_condition],
    )


@pytest.fixture()
def daily_weather(weather_condition: WeatherCondition) -> DailyWeather:
    """Create test daily weather data."""
    return DailyWeather(
        dt=int(datetime.now().timestamp()),
        sunrise=int(datetime(2023, 5, 20, 5, 0).timestamp()),
        sunset=int(datetime(2023, 5, 20, 21, 0).timestamp()),
        moonrise=int(datetime(2023, 5, 20, 2, 0).timestamp()),
        moonset=int(datetime(2023, 5, 20, 14, 0).timestamp()),
        moon_phase=0.5,
        temp=DailyTemp(day=22.5, min=15.0, max=25.0, night=15.5, eve=21.0, morn=16.0),
        feels_like=DailyFeelsLike(day=23.0, night=15.0, eve=20.5, morn=16.5),
        pressure=1015,
        humidity=60,
        dew_point=11.5,
        wind_speed=4.0,
        wind_deg=280,
        weather=[weather_condition],
        clouds=15,
        pop=0.1,
        uvi=5.5,
    )


@pytest.fixture()
def hourly_weather(weather_condition: WeatherCondition) -> HourlyWeather:
    """Create test hourly weather data."""
    return HourlyWeather(
        dt=int(datetime.now().timestamp()),
        temp=21.0,
        feels_like=20.5,
        pressure=1014,
        humidity=63,
        dew_point=12.0,
        uvi=5.0,
        clouds=12,
        visibility=10000,
        wind_speed=3.0,
        wind_deg=275,
        weather=[weather_condition],
        pop=0.05,
    )


@pytest.fixture()
def weather_data(
    current_weather: CurrentWeather, daily_weather: DailyWeather, hourly_weather: HourlyWeather
) -> WeatherData:
    """Create test weather data."""
    return WeatherData(
        lat=51.5074,
        lon=-0.1278,
        timezone="Europe/London",
        timezone_offset=3600,
        current=current_weather,
        daily=[daily_weather] * 5,  # 5 days of forecast
        hourly=[hourly_weather] * 24,  # 24 hours of forecast
    )


@pytest.fixture()
def battery_status() -> BatteryStatus:
    """Create test battery status."""
    return BatteryStatus(
        level=80, voltage=3.9, current=120.0, temperature=25.0, state=BatteryState.DISCHARGING
    )


@pytest.fixture()
def renderer(config: AppConfig, template_dir: Path) -> WeatherRenderer:
    """Create a test renderer instance."""
    return WeatherRenderer(config, template_dir)


class TestWeatherRenderer:
    """Tests for the WeatherRenderer class."""

    def test_init(self, config: AppConfig, template_dir: Path) -> None:
        """Test initialization of the renderer."""
        renderer = WeatherRenderer(config, template_dir)

        assert renderer.config == config
        assert isinstance(renderer.jinja_env, jinja2.Environment)
        assert "format_datetime" in renderer.jinja_env.filters
        assert "format_temp" in renderer.jinja_env.filters
        assert "get_icon" in renderer.jinja_env.filters

    def test_format_datetime_with_datetime(self, renderer: WeatherRenderer) -> None:
        """Test formatting a datetime object."""
        dt = datetime(2023, 5, 20, 15, 30, 0)
        result = renderer._format_datetime(dt)

        assert result == "2023-05-20 15:30"

    def test_format_datetime_with_timestamp(self, renderer: WeatherRenderer) -> None:
        """Test formatting a Unix timestamp."""
        # May 20, 2023 15:30:00 UTC
        timestamp = 1684596600
        result = renderer._format_datetime(timestamp)

        dt = datetime.fromtimestamp(timestamp)
        expected = dt.strftime("%Y-%m-%d %H:%M")

        assert result == expected

    def test_format_datetime_with_custom_format(self, renderer: WeatherRenderer) -> None:
        """Test formatting with a custom format string."""
        dt = datetime(2023, 5, 20, 15, 30, 0)
        result = renderer._format_datetime(dt, "%H:%M %d/%m/%Y")

        assert result == "15:30 20/05/2023"

    def test_format_temp_celsius(self, renderer: WeatherRenderer) -> None:
        """Test formatting a temperature in Celsius."""
        temp = 20.5
        result = renderer._format_temp(temp, "metric")

        # The renderer uses int(round(temp)) which rounds to nearest integer
        assert result == "20°C"  # Not 21°C because int() truncates, not rounds

    def test_format_temp_fahrenheit(self, renderer: WeatherRenderer) -> None:
        """Test formatting a temperature in Fahrenheit."""
        temp = 68.5
        result = renderer._format_temp(temp, "imperial")

        assert result == "68°F"  # Not 69°F for the same reason as above

    def test_format_temp_kelvin(self, renderer: WeatherRenderer) -> None:
        """Test formatting a temperature in Kelvin."""
        temp = 293.15
        result = renderer._format_temp(temp, "standard")

        assert result == "293K"

    def test_format_temp_default_units(self, renderer: WeatherRenderer) -> None:
        """Test formatting a temperature using default units from config."""
        temp = 20.5
        result = renderer._format_temp(temp)

        assert result == "20°C"  # Default is metric in the fixture

    def test_get_weather_icon(self, renderer: WeatherRenderer) -> None:
        """Test conversion of OWM icon codes to sprite icon IDs."""
        # Test a few representative icon codes
        assert renderer._get_weather_icon("01d") == "sun-bold"  # Clear day
        assert renderer._get_weather_icon("01n") == "moon-bold"  # Clear night
        assert renderer._get_weather_icon("03d") == "cloud-bold"  # Scattered clouds
        assert renderer._get_weather_icon("10n") == "moon-cloud-rain-bold"  # Rain night
        assert renderer._get_weather_icon("13d") == "cloud-snow-bold"  # Snow

    def test_get_weather_icon_unknown(self, renderer: WeatherRenderer) -> None:
        """Test fallback for unknown OWM icon codes."""
        assert renderer._get_weather_icon("unknown-code") == "cloud-bold"  # Default fallback

    def test_get_battery_icon_charging(self, renderer: WeatherRenderer) -> None:
        """Test battery icon selection for charging state."""
        battery = BatteryStatus(
            level=50, voltage=3.8, current=500, temperature=25.0, state=BatteryState.CHARGING
        )

        assert renderer._get_battery_icon(battery) == "battery-charging-bold"

    def test_get_battery_icon_empty(self, renderer: WeatherRenderer) -> None:
        """Test battery icon selection for empty battery."""
        battery = BatteryStatus(
            level=0, voltage=3.1, current=-100, temperature=25.0, state=BatteryState.DISCHARGING
        )

        assert renderer._get_battery_icon(battery) == "battery-empty-bold"

    def test_get_battery_icon_full(self, renderer: WeatherRenderer) -> None:
        """Test battery icon selection for full battery."""
        battery = BatteryStatus(
            level=95, voltage=4.1, current=-10, temperature=25.0, state=BatteryState.DISCHARGING
        )

        assert renderer._get_battery_icon(battery) == "battery-full-bold"

    def test_get_battery_icon_high(self, renderer: WeatherRenderer) -> None:
        """Test battery icon selection for high battery level."""
        battery = BatteryStatus(
            level=75, voltage=3.9, current=-50, temperature=25.0, state=BatteryState.DISCHARGING
        )

        assert renderer._get_battery_icon(battery) == "battery-high-bold"

    def test_get_battery_icon_low(self, renderer: WeatherRenderer) -> None:
        """Test battery icon selection for low battery level."""
        battery = BatteryStatus(
            level=15, voltage=3.5, current=-150, temperature=25.0, state=BatteryState.DISCHARGING
        )

        assert renderer._get_battery_icon(battery) == "battery-low-bold"

    @pytest.mark.asyncio()
    async def test_generate_html(
        self, renderer: WeatherRenderer, weather_data: WeatherData, battery_status: BatteryStatus
    ) -> None:
        """Test HTML generation from weather data."""
        html = await renderer.generate_html(weather_data, battery_status)

        # Check that key elements are in the HTML
        assert "Temperature:" in html
        assert "Clear" in html  # From weather condition main
        assert "80%" in html  # Battery level

        # Check that custom filters were applied
        assert "20°C" in html  # Formatted temperature (current.temp = 20.5)
        assert datetime.now().strftime("%Y-%m") in html  # Part of the formatted datetime

    @pytest.mark.asyncio()
    async def test_generate_html_template_error(
        self, renderer: WeatherRenderer, weather_data: WeatherData, battery_status: BatteryStatus
    ) -> None:
        """Test error handling when a template error occurs."""
        # Mock the template rendering to raise an error
        mock_template = MagicMock()
        mock_template.render.side_effect = jinja2.exceptions.TemplateError("Test error")

        with patch.object(renderer.jinja_env, "get_template", return_value=mock_template):
            with pytest.raises(jinja2.exceptions.TemplateError):
                await renderer.generate_html(weather_data, battery_status)

    @pytest.mark.asyncio()
    async def test_generate_html_generic_error(
        self, renderer: WeatherRenderer, weather_data: WeatherData, battery_status: BatteryStatus
    ) -> None:
        """Test error handling when a generic error occurs."""
        # Mock the template rendering to raise a generic error
        mock_template = MagicMock()
        error_message = "Test template render error"
        mock_template.render.side_effect = RuntimeError(error_message)

        with patch.object(renderer.jinja_env, "get_template", return_value=mock_template):
            with pytest.raises(RuntimeError, match=error_message):
                await renderer.generate_html(weather_data, battery_status)

    @pytest.mark.asyncio()
    async def test_render_image(self, renderer: WeatherRenderer, tmp_path: Path) -> None:
        """Test rendering HTML to an image."""
        html = "<html><body>Test</body></html>"
        output_path = tmp_path / "test_image.png"

        # Mock Playwright to avoid actual browser usage
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"mock_screenshot_data")
        mock_browser.close = AsyncMock()

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium
        mock_playwright_context = AsyncMock()
        mock_playwright_context.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_playwright_context.__aexit__ = AsyncMock()

        with patch("playwright.async_api.async_playwright", return_value=mock_playwright_context):
            # Test with output_path
            result = await renderer.render_image(html, 800, 600, output_path)

            # Verify the path is returned
            assert result == output_path

            # Test without output_path (should return bytes)
            result = await renderer.render_image(html, 800, 600)

            # Verify bytes are returned
            assert result == b"mock_screenshot_data"

    @pytest.mark.asyncio()
    async def test_render_image_error(self, renderer: WeatherRenderer) -> None:
        """Test error handling during image rendering."""
        html = "<html><body>Test</body></html>"

        # Mock Playwright to raise an exception
        mock_playwright_context = AsyncMock()
        error_message = "Browser initialization failed"
        mock_playwright_context.__aenter__ = AsyncMock(side_effect=RuntimeError(error_message))

        with patch("playwright.async_api.async_playwright", return_value=mock_playwright_context):
            with pytest.raises(RuntimeError, match=error_message):
                await renderer.render_image(html, 800, 600)

    @pytest.mark.asyncio()
    async def test_render_weather_image(
        self,
        renderer: WeatherRenderer,
        weather_data: WeatherData,
        battery_status: BatteryStatus,
        tmp_path: Path,
    ) -> None:
        """Test rendering weather data to an image."""
        # Mock the generate_html and render_image methods
        html = "<html><body>Test</body></html>"
        output_path = tmp_path / "test_weather_image.png"

        # Create mocks for the async methods
        mock_generate_html = AsyncMock(return_value=html)
        mock_render_image = AsyncMock(return_value=output_path)

        with (
            patch.object(renderer, "generate_html", mock_generate_html),
            patch.object(renderer, "render_image", mock_render_image),
        ):
            result = await renderer.render_weather_image(weather_data, battery_status, output_path)

            # Verify the methods were called with correct arguments
            # Use call_args instead of assert_called_once_with
            assert mock_generate_html.call_args[0] == (weather_data, battery_status)
            assert mock_render_image.call_args[0] == (
                html,
                renderer.config.display.width,
                renderer.config.display.height,
                output_path,
            )

            # Verify the result
            assert result == output_path
