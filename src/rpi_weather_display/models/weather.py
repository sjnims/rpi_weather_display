"""Weather data models used throughout the application.

Defines Pydantic models for weather information, including current conditions,
forecasts, and air quality data from weather service APIs.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class WeatherCondition(BaseModel):
    """Weather condition information."""

    id: int
    main: str
    description: str
    icon: str


class CurrentWeather(BaseModel):
    """Current weather data."""

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
    wind_gust: float | None = None
    weather: list[WeatherCondition]
    rain: dict[str, float] | None = None  # {"1h": mm}
    snow: dict[str, float] | None = None  # {"1h": mm}

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime.
        
        This property converts the Unix timestamp (dt) to a Python datetime object
        for easier handling and formatting of dates and times.
        
        Returns:
            A datetime object representing the time of this weather data point.
        """
        return datetime.fromtimestamp(self.dt)

    @property
    def sunrise_time(self) -> datetime:
        """Convert sunrise Unix timestamp to datetime.
        
        This property converts the Unix timestamp for sunrise to a Python datetime object
        for easier handling and formatting.
        
        Returns:
            A datetime object representing the sunrise time.
        """
        return datetime.fromtimestamp(self.sunrise)

    @property
    def sunset_time(self) -> datetime:
        """Convert sunset Unix timestamp to datetime.
        
        This property converts the Unix timestamp for sunset to a Python datetime object
        for easier handling and formatting.
        
        Returns:
            A datetime object representing the sunset time.
        """
        return datetime.fromtimestamp(self.sunset)


class DailyTemp(BaseModel):
    """Daily temperature forecast."""

    day: float
    min: float
    max: float
    night: float
    eve: float
    morn: float


class DailyFeelsLike(BaseModel):
    """Daily 'feels like' temperatures."""

    day: float
    night: float
    eve: float
    morn: float


class DailyWeather(BaseModel):
    """Daily weather forecast data."""

    dt: int
    sunrise: int
    sunset: int
    moonrise: int
    moonset: int
    moon_phase: float
    temp: DailyTemp
    feels_like: DailyFeelsLike
    pressure: int
    humidity: int
    dew_point: float
    wind_speed: float
    wind_deg: int
    wind_gust: float | None = None
    weather: list[WeatherCondition]
    clouds: int
    pop: float  # Probability of precipitation
    rain: float | None = None  # Total mm for the day
    snow: float | None = None  # Total mm for the day
    uvi: float

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime.
        
        This property converts the Unix timestamp (dt) to a Python datetime object
        for easier handling and formatting of dates and times.
        
        Returns:
            A datetime object representing the time of this weather data point.
        """
        return datetime.fromtimestamp(self.dt)


class HourlyWeather(BaseModel):
    """Hourly weather forecast data."""

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
    wind_gust: float | None = None
    weather: list[WeatherCondition]
    pop: float  # Probability of precipitation
    rain: dict[str, float] | None = None  # {"1h": mm}
    snow: dict[str, float] | None = None  # {"1h": mm}

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime.
        
        This property converts the Unix timestamp (dt) to a Python datetime object
        for easier handling and formatting of dates and times.
        
        Returns:
            A datetime object representing the time of this weather data point.
        """
        return datetime.fromtimestamp(self.dt)


class AirPollution(BaseModel):
    """Air pollution data."""

    aqi: int | None = None  # Air Quality Index: 1-5 (might be missing in some responses)
    co: float  # Carbon monoxide, μg/m3
    no: float  # Nitrogen monoxide, μg/m3
    no2: float  # Nitrogen dioxide, μg/m3
    o3: float  # Ozone, μg/m3
    so2: float  # Sulphur dioxide, μg/m3
    pm2_5: float  # Fine particles, μg/m3
    pm10: float  # Coarse particles, μg/m3
    nh3: float  # Ammonia, μg/m3


class AirPollutionData(BaseModel):
    """Air pollution data with timestamp."""

    dt: int
    main: dict[str, int] = Field(..., alias="main")
    components: AirPollution

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime.
        
        This property converts the Unix timestamp (dt) to a Python datetime object
        for easier handling and formatting of dates and times.
        
        Returns:
            A datetime object representing the time of this weather data point.
        """
        return datetime.fromtimestamp(self.dt)

    @property
    def aqi(self) -> int:
        """Get air quality index.
        
        This property extracts the Air Quality Index (AQI) value from the main data dictionary.
        The AQI is a value from 1-5 where:
        1: Good
        2: Fair
        3: Moderate
        4: Poor
        5: Very Poor
        
        Returns:
            An integer from 1-5 representing the air quality index.
        """
        return self.main["aqi"]


class WeatherData(BaseModel):
    """Complete weather data."""

    lat: float
    lon: float
    timezone: str
    timezone_offset: int
    current: CurrentWeather
    hourly: list[HourlyWeather]
    daily: list[DailyWeather]
    air_pollution: AirPollutionData | None = None
    last_updated: datetime = Field(default_factory=datetime.now)
