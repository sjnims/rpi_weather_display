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

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.dt)

    @property
    def sunrise_time(self) -> datetime:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.sunrise)

    @property
    def sunset_time(self) -> datetime:
        """Convert Unix timestamp to datetime."""
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
    rain: float | None = None
    uvi: float

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime."""
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

    @property
    def timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.dt)


class AirPollution(BaseModel):
    """Air pollution data."""
    aqi: int  # Air Quality Index: 1-5
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
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.dt)

    @property
    def aqi(self) -> int:
        """Get air quality index."""
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