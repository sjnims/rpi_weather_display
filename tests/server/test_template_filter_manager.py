"""Tests for the TemplateFilterManager class."""

from unittest.mock import Mock

import jinja2
import pytest

from rpi_weather_display.models.weather import CurrentWeather, HourlyWeather
from rpi_weather_display.server.template_filter_manager import TemplateFilterManager


@pytest.fixture()
def jinja_env() -> jinja2.Environment:
    """Create a test Jinja2 environment."""
    return jinja2.Environment(autoescape=True)


@pytest.fixture()
def mock_icon_mapper() -> Mock:
    """Create a mock weather icon mapper."""
    mapper = Mock()
    mapper.get_icon_for_condition = Mock(return_value="wi-day-sunny")
    return mapper


@pytest.fixture()
def filter_manager(jinja_env: jinja2.Environment, mock_icon_mapper: Mock) -> TemplateFilterManager:
    """Create a TemplateFilterManager instance."""
    return TemplateFilterManager(jinja_env, mock_icon_mapper)


class TestTemplateFilterManager:
    """Tests for TemplateFilterManager."""

    def test_init(self, jinja_env: jinja2.Environment, mock_icon_mapper: Mock) -> None:
        """Test initialization."""
        manager = TemplateFilterManager(jinja_env, mock_icon_mapper)
        assert manager.jinja_env is jinja_env
        assert manager.icon_mapper is mock_icon_mapper

    def test_register_all_filters(self, filter_manager: TemplateFilterManager) -> None:
        """Test registering all filters."""
        # Register all filters
        filter_manager.register_all_filters()

        # Check that filters were registered
        assert "weather_icon" in filter_manager.jinja_env.filters
        assert "moon_phase_icon" in filter_manager.jinja_env.filters
        assert "moon_phase_label" in filter_manager.jinja_env.filters
        assert "wind_direction_angle" in filter_manager.jinja_env.filters
        assert "wind_direction_cardinal" in filter_manager.jinja_env.filters
        assert "get_precipitation_amount" in filter_manager.jinja_env.filters
        assert "get_hourly_precipitation" in filter_manager.jinja_env.filters

        # Check globals
        assert "get_precipitation_amount" in filter_manager.jinja_env.globals
        assert "get_hourly_precipitation" in filter_manager.jinja_env.globals

    def test_weather_icon_filter(
        self, filter_manager: TemplateFilterManager, mock_icon_mapper: Mock
    ) -> None:
        """Test the weather icon filter."""
        filter_manager._register_weather_filters()

        # Set up the mock to return a specific icon
        mock_icon_mapper.get_icon_for_condition.return_value = "sun-bold"

        # Test the filter by rendering a template instead of calling directly
        template = filter_manager.jinja_env.from_string("{{ weather | weather_icon }}")

        # Create a mock weather condition object
        weather_condition = Mock()
        weather_condition.id = 800
        weather_condition.icon = "01d"

        # Test with a day icon
        result = template.render(weather=weather_condition)
        mock_icon_mapper.get_icon_for_condition.assert_called_once_with(weather_condition)
        assert result == "sun-bold"

        # Test with a night icon
        mock_icon_mapper.get_icon_for_condition.reset_mock()
        mock_icon_mapper.get_icon_for_condition.return_value = "moon-bold"

        weather_condition.icon = "01n"
        result = template.render(weather=weather_condition)
        mock_icon_mapper.get_icon_for_condition.assert_called_once_with(weather_condition)
        assert result == "moon-bold"

        # Test with an invalid weather condition
        mock_icon_mapper.get_icon_for_condition.reset_mock()
        mock_icon_mapper.get_icon_for_condition.return_value = "cloud-unknown-bold"

        weather_condition.id = 999
        weather_condition.icon = "invalid"
        result = template.render(weather=weather_condition)
        mock_icon_mapper.get_icon_for_condition.assert_called_once_with(weather_condition)
        assert result == "cloud-unknown-bold"

    def test_moon_phase_filters(self, filter_manager: TemplateFilterManager) -> None:
        """Test moon phase filters registration."""
        filter_manager._register_moon_filters()

        # Check filters are registered with the correct functions
        assert "moon_phase_icon" in filter_manager.jinja_env.filters
        assert "moon_phase_label" in filter_manager.jinja_env.filters

        # The actual functions come from MoonPhaseHelper
        # Just verify they're callable
        assert callable(filter_manager.jinja_env.filters["moon_phase_icon"])
        assert callable(filter_manager.jinja_env.filters["moon_phase_label"])

    def test_wind_filters(self, filter_manager: TemplateFilterManager) -> None:
        """Test wind direction filters."""
        filter_manager._register_wind_filters()

        # Test wind angle filter by rendering a template
        angle_template = filter_manager.jinja_env.from_string("{{ degrees | wind_direction_angle }}")
        result = angle_template.render(degrees=45.0)
        # WindHelper.get_wind_direction_angle should return a float as string
        assert result == "45.0"

        # Test wind cardinal filter
        cardinal_template = filter_manager.jinja_env.from_string("{{ degrees | wind_direction_cardinal }}")
        result = cardinal_template.render(degrees=45.0)
        # WindHelper.get_wind_direction_cardinal returns cardinal directions
        assert isinstance(result, str)

    def test_precipitation_filters_with_rain(self, filter_manager: TemplateFilterManager) -> None:
        """Test precipitation filters with rain data."""
        filter_manager._register_precipitation_filters()

        # Test with rain data using template rendering
        weather_item = Mock(spec=CurrentWeather)
        weather_item.rain = {"1h": 2.5}
        weather_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ item | get_precipitation_amount }}")
        result = template.render(item=weather_item)
        assert result == "2.5"

        # Test hourly precipitation
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = {"1h": 1.2}
        hourly_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ item | get_hourly_precipitation }}")
        result = template.render(item=hourly_item)
        assert result == "1.2"

    def test_precipitation_filters_with_snow(self, filter_manager: TemplateFilterManager) -> None:
        """Test precipitation filters with snow data."""
        filter_manager._register_precipitation_filters()

        # Test with snow data
        weather_item = Mock(spec=CurrentWeather)
        weather_item.rain = None
        weather_item.snow = {"1h": 3.7}

        template = filter_manager.jinja_env.from_string("{{ item | get_precipitation_amount }}")
        result = template.render(item=weather_item)
        assert result == "3.7"

        # Test hourly with snow
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = None
        hourly_item.snow = {"1h": 4.8}

        template = filter_manager.jinja_env.from_string("{{ item | get_hourly_precipitation }}")
        result = template.render(item=hourly_item)
        assert result == "4.8"

    def test_precipitation_filters_no_precipitation(
        self, filter_manager: TemplateFilterManager
    ) -> None:
        """Test precipitation filters with no precipitation data."""
        filter_manager._register_precipitation_filters()

        # Test with no precipitation
        weather_item = Mock(spec=CurrentWeather)
        weather_item.rain = None
        weather_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ item | get_precipitation_amount }}")
        result = template.render(item=weather_item)
        assert result == "None"

        # Test hourly with probability of precipitation
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = None
        hourly_item.snow = None
        hourly_item.pop = 0.85

        template = filter_manager.jinja_env.from_string("{{ item | get_hourly_precipitation }}")
        result = template.render(item=hourly_item)
        assert result == "85%"

    def test_precipitation_filters_no_data(self, filter_manager: TemplateFilterManager) -> None:
        """Test precipitation filters with no data at all."""
        filter_manager._register_precipitation_filters()

        # Test hourly with no data
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = None
        hourly_item.snow = None
        # No pop attribute

        template = filter_manager.jinja_env.from_string("{{ item | get_hourly_precipitation }}")
        result = template.render(item=hourly_item)
        assert result == "0"

    def test_precipitation_filters_empty_dicts(self, filter_manager: TemplateFilterManager) -> None:
        """Test precipitation filters with empty rain/snow dictionaries."""
        filter_manager._register_precipitation_filters()

        # Test with empty rain dict (no "1h" key)
        weather_item = Mock(spec=CurrentWeather)
        weather_item.rain = {}  # Empty dict
        weather_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ item | get_precipitation_amount }}")
        result = template.render(item=weather_item)
        # Empty dict with no "1h" key should return None
        assert result == "None"

        # Test with empty snow dict
        weather_item.rain = None
        weather_item.snow = {}  # Empty dict

        result = template.render(item=weather_item)
        assert result == "None"

    def test_precipitation_globals_registration(
        self, filter_manager: TemplateFilterManager
    ) -> None:
        """Test that precipitation functions are registered as globals."""
        filter_manager._register_precipitation_filters()

        # Check that the functions are available as globals
        assert "get_precipitation_amount" in filter_manager.jinja_env.globals
        assert "get_hourly_precipitation" in filter_manager.jinja_env.globals

        # Test they work as globals
        weather_item = Mock(spec=CurrentWeather)
        weather_item.rain = {"1h": 5.0}
        weather_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ get_precipitation_amount(item) }}")
        result = template.render(item=weather_item)
        assert result == "5.0"

        # Test hourly as global
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = {"1h": 2.3}
        hourly_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ get_hourly_precipitation(item) }}")
        result = template.render(item=hourly_item)
        assert result == "2.3"

    def test_precipitation_with_missing_attributes(
        self, filter_manager: TemplateFilterManager
    ) -> None:
        """Test precipitation filters when weather objects don't have rain/snow attributes."""
        filter_manager._register_precipitation_filters()

        # Create object without rain or snow attributes
        weather_item = Mock(spec=CurrentWeather)
        # Explicitly remove attributes if they exist
        if hasattr(weather_item, "rain"):
            delattr(weather_item, "rain")
        if hasattr(weather_item, "snow"):
            delattr(weather_item, "snow")

        template = filter_manager.jinja_env.from_string("{{ item | get_precipitation_amount }}")
        result = template.render(item=weather_item)
        # Should return None
        assert result == "None"

    def test_hourly_precipitation_edge_cases(self, filter_manager: TemplateFilterManager) -> None:
        """Test hourly precipitation with edge cases."""
        filter_manager._register_precipitation_filters()

        # Test with 0 precipitation
        hourly_item = Mock(spec=HourlyWeather)
        hourly_item.rain = {"1h": 0.0}
        hourly_item.snow = None

        template = filter_manager.jinja_env.from_string("{{ item | get_hourly_precipitation }}")
        result = template.render(item=hourly_item)
        assert result == "0.0"

        # Test with very small precipitation
        hourly_item.rain = {"1h": 0.05}
        result = template.render(item=hourly_item)
        assert result == "0.1"  # Formatted to 1 decimal

        # Test with pop = 0
        hourly_item.rain = None
        hourly_item.snow = None
        hourly_item.pop = 0.0

        result = template.render(item=hourly_item)
        assert result == "0%"

        # Test with pop = 1.0 (100%)
        hourly_item.pop = 1.0
        result = template.render(item=hourly_item)
        assert result == "100%"
