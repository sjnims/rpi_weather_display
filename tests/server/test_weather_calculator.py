"""Tests for the WeatherCalculator class."""

from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rpi_weather_display.server.weather_calculator import WeatherCalculator


@pytest.fixture()
def calculator() -> WeatherCalculator:
    """Create a WeatherCalculator instance."""
    return WeatherCalculator()


@pytest.fixture()
def sample_weather_data() -> Mock:
    """Create sample weather data for testing."""
    weather_data = Mock()
    
    # Current weather with UVI
    weather_data.current = Mock()
    weather_data.current.uvi = 5.5
    
    # Hourly forecast
    weather_data.hourly = []
    
    return weather_data


class TestWeatherCalculator:
    """Tests for WeatherCalculator."""

    def test_calculate_daylight_hours(self, calculator: WeatherCalculator) -> None:
        """Test daylight hours calculation."""
        # Test normal case: 12 hours of daylight
        sunrise = 1640088000  # 06:00
        sunset = 1640131200   # 18:00
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "12h 0m"
        
        # Test with minutes: 14 hours 30 minutes
        sunrise = 1640077200  # 03:00
        sunset = 1640129400   # 17:30
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "14h 30m"
        
        # Test short day: 8 hours 18 minutes (actual calculation)
        sunrise = 1640095200  # 08:00
        sunset = 1640125100   # 16:18:20
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "8h 18m"
        
        # Test edge case: exactly 24 hours
        sunrise = 1640088000
        sunset = 1640174400
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "24h 0m"

    def test_calculate_daylight_hours_exception(self, calculator: WeatherCalculator) -> None:
        """Test daylight hours calculation with exception."""
        # Test with non-numeric input that would cause TypeError
        with patch("rpi_weather_display.server.weather_calculator.SECONDS_PER_HOUR", None):
            # This will cause TypeError when trying to divide by None
            result = calculator.calculate_daylight_hours(1640088000, 1640131200)
            assert result == "12h 30m"  # Fallback value

    def test_convert_pressure_to_mmhg(self, calculator: WeatherCalculator) -> None:
        """Test pressure conversion to mmHg."""
        # Standard atmospheric pressure: 1013.25 hPa = 760 mmHg
        result = calculator.convert_pressure(1013.25, "mmHg")
        assert round(result, 1) == 760.0
        
        # Test other values
        result = calculator.convert_pressure(1000.0, "mmHg")
        assert round(result, 1) == 750.1

    def test_convert_pressure_to_inhg(self, calculator: WeatherCalculator) -> None:
        """Test pressure conversion to inHg."""
        # Standard atmospheric pressure: 1013.25 hPa = 29.92 inHg
        result = calculator.convert_pressure(1013.25, "inHg")
        assert round(result, 2) == 29.92
        
        # Test other values
        result = calculator.convert_pressure(1000.0, "inHg")
        assert round(result, 2) == 29.53

    def test_convert_pressure_to_hpa(self, calculator: WeatherCalculator) -> None:
        """Test pressure conversion to hPa (no conversion)."""
        result = calculator.convert_pressure(1013.25, "hPa")
        assert result == 1013.25
        
        # Test with unknown unit (defaults to hPa)
        result = calculator.convert_pressure(1013.25, "unknown")
        assert result == 1013.25

    def test_get_daily_max_uvi_no_cache(
        self, calculator: WeatherCalculator, sample_weather_data: Mock
    ) -> None:
        """Test getting daily max UVI without cache."""
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        # Add hourly data for today
        today_start = datetime(2024, 1, 15, 0, 0, 0)
        for hour in range(24):
            hourly = Mock()
            hourly.dt = int((today_start + timedelta(hours=hour)).timestamp())
            hourly.uvi = hour * 0.5 if hour < 14 else (24 - hour) * 0.5  # Peak at 13:00
            sample_weather_data.hourly.append(hourly)
        
        with patch("rpi_weather_display.server.weather_calculator.path_resolver.get_cache_file") as mock_cache:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_calculator.file_utils.write_json") as mock_write:
                    mock_cache.return_value = Path("/tmp/uvi_cache.json")
                    mock_exists.return_value = False
                    
                    max_uvi, timestamp = calculator.get_daily_max_uvi(sample_weather_data, now)
                    
                    assert max_uvi == 6.5  # Max at 13:00
                    assert timestamp == sample_weather_data.hourly[13].dt
                    
                    # Verify cache was written
                    mock_write.assert_called_once()

    def test_get_daily_max_uvi_with_valid_cache(
        self, calculator: WeatherCalculator, sample_weather_data: Mock
    ) -> None:
        """Test getting daily max UVI with valid cache containing higher value."""
        now = datetime(2024, 1, 15, 14, 0, 0)
        
        # Set current UVI lower than cached
        sample_weather_data.current.uvi = 3.0
        
        with patch("rpi_weather_display.server.weather_calculator.path_resolver.get_cache_file") as mock_cache:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_calculator.file_utils.read_json") as mock_read:
                    mock_cache.return_value = Path("/tmp/uvi_cache.json")
                    mock_exists.return_value = True
                    
                    # Cache has higher UVI from earlier today
                    cache_data = {
                        "date": "2024-01-15",
                        "max_uvi": 8.5,
                        "timestamp": int(datetime(2024, 1, 15, 12, 0, 0).timestamp())
                    }
                    mock_read.return_value = cache_data
                    
                    max_uvi, timestamp = calculator.get_daily_max_uvi(sample_weather_data, now)
                    
                    assert max_uvi == 8.5  # Cached value
                    assert timestamp == cache_data["timestamp"]

    def test_get_daily_max_uvi_with_outdated_cache(
        self, calculator: WeatherCalculator, sample_weather_data: Mock
    ) -> None:
        """Test getting daily max UVI with outdated cache."""
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        with patch("rpi_weather_display.server.weather_calculator.path_resolver.get_cache_file") as mock_cache:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_calculator.file_utils.read_json") as mock_read:
                    with patch("rpi_weather_display.server.weather_calculator.file_utils.write_json") as mock_write:
                        mock_cache.return_value = Path("/tmp/uvi_cache.json")
                        mock_exists.return_value = True
                        
                        # Cache from yesterday
                        cache_data = {
                            "date": "2024-01-14",
                            "max_uvi": 10.0,
                            "timestamp": int(datetime(2024, 1, 14, 12, 0, 0).timestamp())
                        }
                        mock_read.return_value = cache_data
                        
                        max_uvi, timestamp = calculator.get_daily_max_uvi(sample_weather_data, now)
                        
                        assert max_uvi == 5.5  # Current value (cache ignored)
                        assert timestamp == int(now.timestamp())
                        
                        # Verify new cache was written
                        mock_write.assert_called_once()

    def test_calculate_current_max_uvi_no_current_uvi(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test calculating max UVI when current weather has no UVI."""
        weather_data = Mock()
        weather_data.current = Mock(spec=[])  # No uvi attribute
        weather_data.hourly = []
        
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        # Add hourly data
        hourly = Mock()
        hourly.dt = int(now.timestamp())
        hourly.uvi = 4.0
        weather_data.hourly.append(hourly)
        
        max_uvi, timestamp = calculator._calculate_current_max_uvi(weather_data, now)
        
        assert max_uvi == 4.0
        assert timestamp == hourly.dt

    def test_calculate_current_max_uvi_multiple_days(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test that only today's UVI values are considered."""
        weather_data = Mock()
        weather_data.current = Mock()
        weather_data.current.uvi = 2.0
        weather_data.hourly = []
        
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        # Add hourly data for multiple days
        base_time = datetime(2024, 1, 14, 0, 0, 0)
        for day in range(3):
            for hour in range(24):
                hourly = Mock()
                hourly.dt = int((base_time + timedelta(days=day, hours=hour)).timestamp())
                hourly.uvi = (day + 1) * 5.0  # Different UVI for each day
                weather_data.hourly.append(hourly)
        
        max_uvi, _ = calculator._calculate_current_max_uvi(weather_data, now)
        
        # Should only consider today's values (day 1, UVI = 10.0)
        assert max_uvi == 10.0

    def test_read_uvi_cache_invalid_json(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test reading UVI cache with invalid JSON."""
        cache_file = Path("/tmp/uvi_cache.json")
        today = date(2024, 1, 15)
        
        with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.read_json") as mock_read:
                mock_exists.return_value = True
                mock_read.side_effect = Exception("Invalid JSON")
                
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                
                assert uvi is None
                assert timestamp is None

    def test_read_uvi_cache_invalid_structure(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test reading UVI cache with invalid structure."""
        cache_file = Path("/tmp/uvi_cache.json")
        today = date(2024, 1, 15)
        
        with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.read_json") as mock_read:
                mock_exists.return_value = True
                
                # Test non-dict cache data
                mock_read.return_value = []
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                assert uvi is None
                assert timestamp is None
                
                # Test missing date
                mock_read.return_value = {"max_uvi": 5.0, "timestamp": 12345}
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                assert uvi is None
                assert timestamp is None
                
                # Test invalid date type
                mock_read.return_value = {"date": 12345, "max_uvi": 5.0, "timestamp": 12345}
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                assert uvi is None
                assert timestamp is None
                
                # Test invalid value types
                mock_read.return_value = {
                    "date": "2024-01-15", 
                    "max_uvi": "not a number", 
                    "timestamp": 12345
                }
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                assert uvi is None
                assert timestamp is None

    def test_write_uvi_cache_exception(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test writing UVI cache with exception."""
        cache_file = Path("/tmp/uvi_cache.json")
        today = date(2024, 1, 15)
        
        with patch("rpi_weather_display.server.weather_calculator.file_utils.write_json") as mock_write:
            mock_write.side_effect = Exception("Write error")
            
            # Should not raise exception
            calculator._write_uvi_cache(cache_file, today, 7.5, 12345)
            
            # Verify write was attempted
            mock_write.assert_called_once()

    def test_get_daily_max_uvi_zero_uvi(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test that zero UVI doesn't write to cache."""
        weather_data = Mock()
        weather_data.current = Mock()
        weather_data.current.uvi = 0.0
        weather_data.hourly = []
        
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        with patch("rpi_weather_display.server.weather_calculator.path_resolver.get_cache_file") as mock_cache:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
                with patch("rpi_weather_display.server.weather_calculator.file_utils.write_json") as mock_write:
                    mock_cache.return_value = Path("/tmp/uvi_cache.json")
                    mock_exists.return_value = False
                    
                    max_uvi, timestamp = calculator.get_daily_max_uvi(weather_data, now)
                    
                    assert max_uvi == 0.0
                    assert timestamp == int(now.timestamp())
                    
                    # Should not write to cache with zero UVI
                    mock_write.assert_not_called()

    def test_calculate_current_max_uvi_no_uvi_in_hourly(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test max UVI calculation when hourly data has no UVI."""
        weather_data = Mock()
        weather_data.current = Mock()
        weather_data.current.uvi = 3.5
        weather_data.hourly = []
        
        now = datetime(2024, 1, 15, 12, 0, 0)
        
        # Add hourly data without UVI attribute
        hourly = Mock(spec=["dt"])  # Only dt, no uvi
        hourly.dt = int(now.timestamp())
        weather_data.hourly.append(hourly)
        
        max_uvi, timestamp = calculator._calculate_current_max_uvi(weather_data, now)
        
        assert max_uvi == 3.5  # Uses current UVI
        assert timestamp == int(now.timestamp())

    def test_read_uvi_cache_valid_types(
        self, calculator: WeatherCalculator
    ) -> None:
        """Test reading UVI cache with both int and float values."""
        cache_file = Path("/tmp/uvi_cache.json")
        today = date(2024, 1, 15)
        
        with patch("rpi_weather_display.server.weather_calculator.file_utils.file_exists") as mock_exists:
            with patch("rpi_weather_display.server.weather_calculator.file_utils.read_json") as mock_read:
                mock_exists.return_value = True
                
                # Test with int max_uvi
                cache_data = {
                    "date": "2024-01-15",
                    "max_uvi": 8,  # int
                    "timestamp": 12345
                }
                mock_read.return_value = cache_data
                
                uvi, timestamp = calculator._read_uvi_cache(cache_file, today)
                
                assert uvi == 8.0  # Converted to float
                assert timestamp == 12345

    def test_calculate_daylight_hours_edge_cases(self, calculator: WeatherCalculator) -> None:
        """Test daylight calculation edge cases."""
        # Test with 0 minutes
        sunrise = 1640088000  # 06:00
        sunset = 1640088000   # 06:00 (same as sunrise)
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "0h 0m"
        
        # Test with exactly 59 minutes
        sunrise = 1640088000
        sunset = 1640091540  # 59 minutes later
        result = calculator.calculate_daylight_hours(sunrise, sunset)
        assert result == "0h 59m"