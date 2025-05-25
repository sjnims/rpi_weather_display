"""Tests for the WeatherIconMapper class."""

from unittest.mock import Mock, patch

import pytest

from rpi_weather_display.server.weather_icon_mapper import WeatherIconMapper


@pytest.fixture()
def mapper() -> WeatherIconMapper:
    """Create a WeatherIconMapper instance."""
    return WeatherIconMapper()


@pytest.fixture()
def sample_csv_content() -> str:
    """Sample CSV content for testing."""
    return """API response: id,API response: icon,Weather Icons Class
200,11d,wi-thunderstorm
201,11d,wi-thunderstorm
202,11d,wi-thunderstorm
210,11d,wi-lightning
300,09d,wi-sprinkle
500,10d,wi-rain
501,10d,wi-rain
502,10d,wi-rain-wind
503,10d,wi-rain-wind
504,10d,wi-rain-wind
800,01d,wi-day-sunny
800,01n,wi-night-clear
801,02d,wi-day-cloudy
801,02n,wi-night-cloudy
802,03d,wi-cloud
802,03n,wi-cloud
803,04d,wi-cloudy
803,04n,wi-cloudy
804,04d,wi-cloudy
804,04n,wi-cloudy"""


class TestWeatherIconMapper:
    """Tests for WeatherIconMapper."""

    def test_init(self, mapper: WeatherIconMapper) -> None:
        """Test initialization."""
        assert mapper._weather_icon_map == {}
        assert mapper._weather_id_to_icon == {}
        assert mapper._loaded is False

    def test_ensure_mappings_loaded_once(self, mapper: WeatherIconMapper) -> None:
        """Test that mappings are only loaded once."""
        # Set loaded to True
        mapper._loaded = True
        
        # Mock path_resolver and file_utils to ensure they're not called
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils") as mock_file:
                mapper._ensure_mappings_loaded()
                
                # Should not call any file operations
                mock_path.get_data_file.assert_not_called()
                mock_file.file_exists.assert_not_called()

    def test_ensure_mappings_loaded_no_file(self, mapper: WeatherIconMapper) -> None:
        """Test loading when CSV file doesn't exist."""
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                mock_path.return_value = "/path/to/owm_icon_map.csv"
                mock_exists.return_value = False
                
                mapper._ensure_mappings_loaded()
                
                assert mapper._loaded is True
                assert mapper._weather_icon_map == {}
                assert mapper._weather_id_to_icon == {}

    def test_ensure_mappings_loaded_with_csv(
        self, mapper: WeatherIconMapper, sample_csv_content: str
    ) -> None:
        """Test loading mappings from CSV file."""
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.read_text") as mock_read:
                    mock_path.return_value = "/path/to/owm_icon_map.csv"
                    mock_exists.return_value = True
                    mock_read.return_value = sample_csv_content
                    
                    mapper._ensure_mappings_loaded()
                    
                    assert mapper._loaded is True
                    assert len(mapper._weather_icon_map) > 0
                    assert len(mapper._weather_id_to_icon) > 0
                    
                    # Check specific mappings
                    assert mapper._weather_icon_map["200_11d"] == "wi-thunderstorm"
                    assert mapper._weather_icon_map["800_01d"] == "wi-day-sunny"
                    assert mapper._weather_icon_map["800_01n"] == "wi-night-clear"
                    assert mapper._weather_id_to_icon["200"] == "wi-thunderstorm"

    def test_ensure_mappings_loaded_with_exception(self, mapper: WeatherIconMapper) -> None:
        """Test loading with an exception."""
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.read_text") as mock_read:
                    mock_path.return_value = "/path/to/owm_icon_map.csv"
                    mock_exists.return_value = True
                    mock_read.side_effect = Exception("Read error")
                    
                    mapper._ensure_mappings_loaded()
                    
                    assert mapper._loaded is True
                    assert mapper._weather_icon_map == {}
                    assert mapper._weather_id_to_icon == {}

    def test_get_icon_for_code(self, mapper: WeatherIconMapper) -> None:
        """Test getting icon for OpenWeatherMap icon codes."""
        # Test known codes
        assert mapper.get_icon_for_code("01d") == "wi-day-sunny"
        assert mapper.get_icon_for_code("01n") == "wi-night-clear"
        assert mapper.get_icon_for_code("02d") == "wi-day-cloudy"
        assert mapper.get_icon_for_code("02n") == "wi-night-cloudy"
        assert mapper.get_icon_for_code("03d") == "wi-cloud"
        assert mapper.get_icon_for_code("03n") == "wi-cloud"
        assert mapper.get_icon_for_code("04d") == "wi-cloudy"
        assert mapper.get_icon_for_code("04n") == "wi-cloudy"
        assert mapper.get_icon_for_code("09d") == "wi-showers"
        assert mapper.get_icon_for_code("09n") == "wi-showers"
        assert mapper.get_icon_for_code("10d") == "wi-day-rain"
        assert mapper.get_icon_for_code("10n") == "wi-night-rain"
        assert mapper.get_icon_for_code("11d") == "wi-thunderstorm"
        assert mapper.get_icon_for_code("11n") == "wi-thunderstorm"
        assert mapper.get_icon_for_code("13d") == "wi-snow"
        assert mapper.get_icon_for_code("13n") == "wi-snow"
        assert mapper.get_icon_for_code("50d") == "wi-fog"
        assert mapper.get_icon_for_code("50n") == "wi-fog"
        
        # Test unknown code
        assert mapper.get_icon_for_code("99x") == "wi-cloud"

    def test_get_icon_for_condition_no_attributes(self, mapper: WeatherIconMapper) -> None:
        """Test getting icon for condition without required attributes."""
        # Mock weather condition without id or icon
        weather_condition = Mock()
        delattr(weather_condition, "id")
        delattr(weather_condition, "icon")
        
        result = mapper.get_icon_for_condition(weather_condition)
        assert result == "wi-cloud"

    def test_get_icon_for_condition_with_csv_mapping(
        self, mapper: WeatherIconMapper, sample_csv_content: str
    ) -> None:
        """Test getting icon for condition with CSV mappings loaded."""
        # Load CSV mappings
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.read_text") as mock_read:
                    mock_path.return_value = "/path/to/owm_icon_map.csv"
                    mock_exists.return_value = True
                    mock_read.return_value = sample_csv_content
                    
                    # Test exact match
                    weather_condition = Mock()
                    weather_condition.id = 200
                    weather_condition.icon = "11d"
                    
                    result = mapper.get_icon_for_condition(weather_condition)
                    assert result == "wi-thunderstorm"
                    
                    # Test ID-only fallback
                    weather_condition.id = 500
                    weather_condition.icon = "99x"  # Unknown icon code
                    
                    result = mapper.get_icon_for_condition(weather_condition)
                    assert result == "wi-rain"

    def test_get_icon_for_condition_clear_cloudy_variants(
        self, mapper: WeatherIconMapper, sample_csv_content: str
    ) -> None:
        """Test getting icon for clear/cloudy conditions with day/night variants."""
        # Load CSV mappings
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.read_text") as mock_read:
                    mock_path.return_value = "/path/to/owm_icon_map.csv"
                    mock_exists.return_value = True
                    mock_read.return_value = sample_csv_content
                    
                    # Test day variant
                    weather_condition = Mock()
                    weather_condition.id = 800
                    weather_condition.icon = "01d"
                    
                    result = mapper.get_icon_for_condition(weather_condition)
                    assert result == "wi-day-sunny"
                    
                    # Test night variant
                    weather_condition.icon = "01n"
                    
                    result = mapper.get_icon_for_condition(weather_condition)
                    assert result == "wi-night-clear"
                    
                    # Test other clear/cloudy IDs
                    weather_condition.id = 802
                    weather_condition.icon = "03d"
                    
                    result = mapper.get_icon_for_condition(weather_condition)
                    assert result == "wi-cloud"

    def test_get_icon_for_condition_fallback_to_code(self, mapper: WeatherIconMapper) -> None:
        """Test fallback to icon code when no mappings match."""
        # Don't load any CSV mappings
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                mock_path.return_value = "/path/to/owm_icon_map.csv"
                mock_exists.return_value = False
                
                weather_condition = Mock()
                weather_condition.id = 999  # Unknown ID
                weather_condition.icon = "10d"  # Known icon code
                
                result = mapper.get_icon_for_condition(weather_condition)
                assert result == "wi-day-rain"
                
                # Test with unknown ID and unknown icon code
                weather_condition.icon = "99x"
                
                result = mapper.get_icon_for_condition(weather_condition)
                assert result == "wi-cloud"

    def test_get_icon_for_condition_string_conversion(self, mapper: WeatherIconMapper) -> None:
        """Test that weather ID is converted to string."""
        weather_condition = Mock()
        weather_condition.id = 200  # Integer ID
        weather_condition.icon = "11d"
        
        # Should handle integer ID by converting to string
        result = mapper.get_icon_for_condition(weather_condition)
        # Will use default mapping since no CSV loaded
        assert result == "wi-thunderstorm"

    def test_csv_parsing_with_whitespace(self, mapper: WeatherIconMapper) -> None:
        """Test CSV parsing handles whitespace correctly."""
        csv_with_whitespace = """API response: id,API response: icon,Weather Icons Class
        200  ,  11d  ,  wi-thunderstorm  
        201,11d,wi-thunderstorm"""
        
        with patch("rpi_weather_display.server.weather_icon_mapper.path_resolver.get_data_file") as mock_path:
            with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_icon_mapper.file_utils.read_text") as mock_read:
                    mock_path.return_value = "/path/to/owm_icon_map.csv"
                    mock_exists.return_value = True
                    mock_read.return_value = csv_with_whitespace
                    
                    mapper._ensure_mappings_loaded()
                    
                    # Check that whitespace was stripped
                    assert mapper._weather_icon_map["200_11d"] == "wi-thunderstorm"
                    assert mapper._weather_id_to_icon["200"] == "wi-thunderstorm"

    def test_special_clear_cloudy_key_generation(self, mapper: WeatherIconMapper) -> None:
        """Test the special key generation for 800-804 weather IDs."""
        # Create weather conditions for testing
        weather_condition = Mock()
        
        # Test 800 with day icon
        weather_condition.id = "800"
        weather_condition.icon = "01d"
        
        # The special key should be "800_80d" for day variant
        # But since we don't have mappings loaded, it will fall back
        result = mapper.get_icon_for_condition(weather_condition)
        assert result == "wi-day-sunny"  # Falls back to get_icon_for_code
        
        # Test 803 with night icon
        weather_condition.id = "803"
        weather_condition.icon = "04n"
        
        result = mapper.get_icon_for_condition(weather_condition)
        assert result == "wi-cloudy"  # Falls back to get_icon_for_code

    def test_special_clear_cloudy_key_with_mapping(self, mapper: WeatherIconMapper) -> None:
        """Test clear/cloudy conditions when special key exists in mapping."""
        # Manually set up mappings to test the special key branch
        mapper._weather_icon_map["800_80d"] = "wi-special-day-clear"
        mapper._weather_icon_map["803_80n"] = "wi-special-night-cloudy"
        mapper._loaded = True  # Prevent loading from file
        
        weather_condition = Mock()
        
        # Test 800 with day icon - should use special mapping
        weather_condition.id = "800"
        weather_condition.icon = "01d"
        
        result = mapper.get_icon_for_condition(weather_condition)
        assert result == "wi-special-day-clear"
        
        # Test 803 with night icon - should use special mapping
        weather_condition.id = "803"
        weather_condition.icon = "04n"
        
        result = mapper.get_icon_for_condition(weather_condition)
        assert result == "wi-special-night-cloudy"