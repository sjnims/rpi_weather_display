"""Tests for the weather data models.

This module tests the Pydantic models for weather information, ensuring
that models correctly validate input data and compute derived properties.
"""

from datetime import datetime
from typing import TypedDict

import pytest
from pydantic import ValidationError

from rpi_weather_display.models.weather import (
    AirPollution,
    AirPollutionData,
    CurrentWeather,
    DailyFeelsLike,
    DailyTemp,
    DailyWeather,
    HourlyWeather,
    WeatherCondition,
    WeatherData,
)


# Type definitions for test data
class WeatherConditionData(TypedDict):
    """Type definition for weather condition test data."""
    id: int
    main: str
    description: str
    icon: str


class CurrentWeatherData(TypedDict, total=False):
    """Type definition for current weather test data."""
    dt: int
    sunrise: int
    sunset: int
    temp: float
    feels_like: float
    pressure: int
    humidity: int
    dew_point: float
    uvi: float
    clouds: int
    visibility: int
    wind_speed: float
    wind_deg: int
    wind_gust: float | None
    weather: list[WeatherConditionData]


class DailyTempData(TypedDict):
    """Type definition for daily temperature test data."""
    day: float
    min: float
    max: float
    night: float
    eve: float
    morn: float


class DailyFeelsLikeData(TypedDict):
    """Type definition for daily feels like test data."""
    day: float
    night: float
    eve: float
    morn: float


class DailyWeatherData(TypedDict, total=False):
    """Type definition for daily weather test data."""
    dt: int
    sunrise: int
    sunset: int
    moonrise: int
    moonset: int
    moon_phase: float
    temp: DailyTempData
    feels_like: DailyFeelsLikeData
    pressure: int
    humidity: int
    dew_point: float
    wind_speed: float
    wind_deg: int
    weather: list[WeatherConditionData]
    clouds: int
    pop: float
    uvi: float
    rain: float | None


class HourlyWeatherData(TypedDict, total=False):
    """Type definition for hourly weather test data."""
    dt: int
    temp: float
    feels_like: float
    pressure: int
    humidity: int
    dew_point: float
    uvi: float
    clouds: int
    visibility: int
    wind_speed: float
    wind_deg: int
    weather: list[WeatherConditionData]
    pop: float


class AirPollutionComponents(TypedDict):
    """Type definition for air pollution components."""
    co: float
    no: float
    no2: float
    o3: float
    so2: float
    pm2_5: float
    pm10: float
    nh3: float


class AirPollutionMain(TypedDict):
    """Type definition for air pollution main data."""
    aqi: int


class AirPollutionDataDict(TypedDict):
    """Type definition for air pollution test data."""
    dt: int
    main: AirPollutionMain
    components: AirPollutionComponents


class WeatherDataDict(TypedDict, total=False):
    """Type definition for complete weather test data."""
    lat: float
    lon: float
    timezone: str
    timezone_offset: int
    current: CurrentWeatherData
    hourly: list[HourlyWeatherData]
    daily: list[DailyWeatherData]
    air_pollution: AirPollutionDataDict | None


# Test fixtures for sample data


@pytest.fixture()
def weather_condition_data() -> WeatherConditionData:
    """Sample weather condition data."""
    return {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}


@pytest.fixture()
def current_weather_data(weather_condition_data: WeatherConditionData) -> CurrentWeatherData:
    """Sample current weather data."""
    return {
        "dt": 1618317040,  # Tuesday, April 13, 2021 10:44:00 AM GMT
        "sunrise": 1618282134,
        "sunset": 1618333901,
        "temp": 15.2,
        "feels_like": 14.3,
        "pressure": 1023,
        "humidity": 55,
        "dew_point": 5.65,
        "uvi": 4.5,
        "clouds": 0,
        "visibility": 10000,
        "wind_speed": 3.6,
        "wind_deg": 320,
        "weather": [weather_condition_data],
    }


@pytest.fixture()
def daily_temp_data() -> DailyTempData:
    """Sample daily temperature data."""
    return {"day": 15.2, "min": 8.4, "max": 16.9, "night": 9.5, "eve": 15.6, "morn": 8.4}


@pytest.fixture()
def daily_feels_like_data() -> DailyFeelsLikeData:
    """Sample daily feels like data."""
    return {"day": 14.3, "night": 8.3, "eve": 14.5, "morn": 7.5}


@pytest.fixture()
def daily_weather_data(
    weather_condition_data: WeatherConditionData,
    daily_temp_data: DailyTempData,
    daily_feels_like_data: DailyFeelsLikeData,
) -> DailyWeatherData:
    """Sample daily weather data."""
    return {
        "dt": 1618308000,  # Tuesday, April 13, 2021 8:00:00 AM GMT
        "sunrise": 1618282134,
        "sunset": 1618333901,
        "moonrise": 1618284562,
        "moonset": 1618339541,
        "moon_phase": 0.25,
        "temp": daily_temp_data,
        "feels_like": daily_feels_like_data,
        "pressure": 1023,
        "humidity": 55,
        "dew_point": 5.65,
        "wind_speed": 3.6,
        "wind_deg": 320,
        "weather": [weather_condition_data],
        "clouds": 0,
        "pop": 0.2,  # 20% chance of precipitation
        "uvi": 4.5,
    }


@pytest.fixture()
def hourly_weather_data(weather_condition_data: WeatherConditionData) -> HourlyWeatherData:
    """Sample hourly weather data."""
    return {
        "dt": 1618315200,  # Tuesday, April 13, 2021 10:13:20 AM GMT
        "temp": 15.2,
        "feels_like": 14.3,
        "pressure": 1023,
        "humidity": 55,
        "dew_point": 5.65,
        "uvi": 4.5,
        "clouds": 0,
        "visibility": 10000,
        "wind_speed": 3.6,
        "wind_deg": 320,
        "weather": [weather_condition_data],
        "pop": 0.2,  # 20% chance of precipitation
    }


@pytest.fixture()
def air_pollution_data() -> AirPollutionDataDict:
    """Sample air pollution data."""
    return {
        "dt": 1618317040,  # Tuesday, April 13, 2021 10:44:00 AM GMT
        "main": {"aqi": 2},
        "components": {
            "co": 200.5,
            "no": 4.2,
            "no2": 3.5,
            "o3": 120.5,
            "so2": 1.1,
            "pm2_5": 8.2,
            "pm10": 10.1,
            "nh3": 1.2,
        },
    }


@pytest.fixture()
def weather_data(
    current_weather_data: CurrentWeatherData,
    hourly_weather_data: HourlyWeatherData,
    daily_weather_data: DailyWeatherData,
    air_pollution_data: AirPollutionDataDict,
) -> WeatherDataDict:
    """Sample complete weather data."""
    return {
        "lat": 40.7128,
        "lon": -74.0060,
        "timezone": "America/New_York",
        "timezone_offset": -14400,  # -4 hours from GMT
        "current": current_weather_data,
        "hourly": [hourly_weather_data],
        "daily": [daily_weather_data],
        "air_pollution": air_pollution_data,
    }


# Tests for individual models


def test_weather_condition(weather_condition_data: WeatherConditionData) -> None:
    """Test WeatherCondition model."""
    # Create model from data
    condition = WeatherCondition.model_validate(weather_condition_data)

    # Check that attributes are set correctly
    assert condition.id == 800
    assert condition.main == "Clear"
    assert condition.description == "clear sky"
    assert condition.icon == "01d"


def test_current_weather(current_weather_data: CurrentWeatherData) -> None:
    """Test CurrentWeather model."""
    # Create model from data
    current = CurrentWeather.model_validate(current_weather_data)

    # Check basic attributes
    assert current.dt == 1618317040
    assert current.temp == 15.2
    assert current.feels_like == 14.3

    # Check computed properties
    assert isinstance(current.timestamp, datetime)
    assert current.timestamp.year == 2021
    assert current.timestamp.month == 4
    assert current.timestamp.day == 13

    assert isinstance(current.sunrise_time, datetime)
    # Instead of checking the specific hour (which depends on timezone),
    # verify that sunrise happens before sunset
    assert current.sunrise_time < current.sunset_time

    assert isinstance(current.sunset_time, datetime)
    # Verify sunrise and sunset are on the same day (or adjacent days)
    assert abs(current.sunset_time.day - current.sunrise_time.day) <= 1

    # Check nested weather condition
    assert len(current.weather) == 1
    assert current.weather[0].main == "Clear"


def test_daily_temp(daily_temp_data: DailyTempData) -> None:
    """Test DailyTemp model."""
    # Create model from data
    temp = DailyTemp.model_validate(daily_temp_data)

    # Check attributes
    assert temp.day == 15.2
    assert temp.min == 8.4
    assert temp.max == 16.9
    assert temp.night == 9.5
    assert temp.eve == 15.6
    assert temp.morn == 8.4


def test_daily_feels_like(daily_feels_like_data: DailyFeelsLikeData) -> None:
    """Test DailyFeelsLike model."""
    # Create model from data
    feels_like = DailyFeelsLike.model_validate(daily_feels_like_data)

    # Check attributes
    assert feels_like.day == 14.3
    assert feels_like.night == 8.3
    assert feels_like.eve == 14.5
    assert feels_like.morn == 7.5


def test_daily_weather(daily_weather_data: DailyWeatherData) -> None:
    """Test DailyWeather model."""
    # Create model from data
    daily = DailyWeather.model_validate(daily_weather_data)

    # Check basic attributes
    assert daily.dt == 1618308000
    assert daily.moon_phase == 0.25
    assert daily.pop == 0.2  # 20% chance of precipitation

    # Check computed properties
    assert isinstance(daily.timestamp, datetime)
    assert daily.timestamp.year == 2021
    assert daily.timestamp.month == 4
    assert daily.timestamp.day == 13

    # Check nested models
    assert daily.temp.max == 16.9
    assert daily.feels_like.night == 8.3
    assert daily.weather[0].main == "Clear"


def test_hourly_weather(hourly_weather_data: HourlyWeatherData) -> None:
    """Test HourlyWeather model."""
    # Create model from data
    hourly = HourlyWeather.model_validate(hourly_weather_data)

    # Check basic attributes
    assert hourly.dt == 1618315200
    assert hourly.temp == 15.2
    assert hourly.feels_like == 14.3

    # Check computed properties
    assert isinstance(hourly.timestamp, datetime)
    assert hourly.timestamp.year == 2021
    assert hourly.timestamp.month == 4
    assert hourly.timestamp.day == 13

    # Check nested weather condition
    assert hourly.weather[0].main == "Clear"


def test_air_pollution() -> None:
    """Test AirPollution model."""
    # Create model from data
    pollution = AirPollution(
        co=200.5, no=4.2, no2=3.5, o3=120.5, so2=1.1, pm2_5=8.2, pm10=10.1, nh3=1.2
    )

    # Check attributes
    assert pollution.co == 200.5
    assert pollution.no == 4.2
    assert pollution.no2 == 3.5
    assert pollution.o3 == 120.5
    assert pollution.so2 == 1.1
    assert pollution.pm2_5 == 8.2
    assert pollution.pm10 == 10.1
    assert pollution.nh3 == 1.2


def test_air_pollution_data(air_pollution_data: AirPollutionDataDict) -> None:
    """Test AirPollutionData model."""
    # Create model from data
    pollution_data = AirPollutionData.model_validate(air_pollution_data)

    # Check basic attributes
    assert pollution_data.dt == 1618317040

    # Check computed properties
    assert isinstance(pollution_data.timestamp, datetime)
    assert pollution_data.timestamp.year == 2021
    assert pollution_data.timestamp.month == 4
    assert pollution_data.timestamp.day == 13

    # Check aqi property
    assert pollution_data.aqi == 2

    # Check nested models
    assert pollution_data.components.co == 200.5
    assert pollution_data.components.pm2_5 == 8.2


def test_weather_data(weather_data: WeatherDataDict) -> None:
    """Test WeatherData model."""
    # Create model from data
    data = WeatherData.model_validate(weather_data)

    # Check basic attributes
    assert data.lat == 40.7128
    assert data.lon == -74.0060
    assert data.timezone == "America/New_York"
    assert data.timezone_offset == -14400  # -4 hours from GMT

    # Check nested models
    assert data.current.temp == 15.2
    assert len(data.hourly) == 1
    assert data.hourly[0].temp == 15.2
    assert len(data.daily) == 1
    assert data.daily[0].temp.max == 16.9
    assert data.air_pollution is not None
    assert data.air_pollution.aqi == 2

    # Check auto-generated last_updated
    assert isinstance(data.last_updated, datetime)
    assert data.last_updated.year >= datetime.now().year


# Tests for validation and error handling


def test_required_fields() -> None:
    """Test that required fields are enforced."""
    # WeatherCondition missing required fields - intentionally incomplete
    with pytest.raises(ValidationError):
        # We're intentionally creating an invalid model to test validation
        WeatherCondition(id=800, main="Clear")  # type: ignore

    # CurrentWeather missing required fields - intentionally incomplete
    with pytest.raises(ValidationError):
        # We're intentionally creating an invalid model to test validation
        CurrentWeather(dt=1618317040, temp=15.2)  # type: ignore


def test_optional_fields() -> None:
    """Test handling of optional fields."""
    # CurrentWeather with missing optional wind_gust
    current = CurrentWeather(
        dt=1618317040,
        sunrise=1618282134,
        sunset=1618333901,
        temp=15.2,
        feels_like=14.3,
        pressure=1023,
        humidity=55,
        dew_point=5.65,
        uvi=4.5,
        clouds=0,
        visibility=10000,
        wind_speed=3.6,
        wind_deg=320,
        weather=[WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")],
    )
    assert current.wind_gust is None

    # DailyWeather with missing optional rain
    daily = DailyWeather(
        dt=1618308000,
        sunrise=1618282134,
        sunset=1618333901,
        moonrise=1618284562,
        moonset=1618339541,
        moon_phase=0.25,
        temp=DailyTemp(day=15.2, min=8.4, max=16.9, night=9.5, eve=15.6, morn=8.4),
        feels_like=DailyFeelsLike(day=14.3, night=8.3, eve=14.5, morn=7.5),
        pressure=1023,
        humidity=55,
        dew_point=5.65,
        wind_speed=3.6,
        wind_deg=320,
        weather=[WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")],
        clouds=0,
        pop=0.2,
        uvi=4.5,
    )
    assert daily.rain is None


def test_weather_data_without_air_pollution(weather_data: WeatherDataDict) -> None:
    """Test WeatherData without air pollution data."""
    # Remove air_pollution from data
    data_without_pollution = weather_data.copy()
    data_without_pollution.pop("air_pollution")

    # Create model
    data = WeatherData.model_validate(data_without_pollution)

    # Check that air_pollution is None
    assert data.air_pollution is None


def test_timestamp_conversion() -> None:
    """Test timestamp conversion in various models."""
    # Test with a specific timestamp
    timestamp = 1618317040  # Tuesday, April 13, 2021 10:44:00 AM GMT

    # Test in CurrentWeather
    current = CurrentWeather(
        dt=timestamp,
        sunrise=timestamp,
        sunset=timestamp + 3600,  # One hour later
        temp=15.2,
        feels_like=14.3,
        pressure=1023,
        humidity=55,
        dew_point=5.65,
        uvi=4.5,
        clouds=0,
        visibility=10000,
        wind_speed=3.6,
        wind_deg=320,
        weather=[WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")],
    )

    # Since we can't predict the exact hour due to timezone differences,
    # check that the date components are correct and that the timestamps
    # maintain their relative order
    assert current.timestamp.year == 2021
    assert current.timestamp.month == 4
    assert current.timestamp.day == 13

    # Check that sunset is exactly 1 hour after sunrise
    time_diff = current.sunset_time - current.sunrise_time
    assert time_diff.total_seconds() == 3600  # 1 hour in seconds


if __name__ == "__main__":
    pytest.main()
