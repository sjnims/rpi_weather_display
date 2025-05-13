"""Configuration models for the Raspberry Pi weather display.

Defines Pydantic models for application configuration including weather API settings,
display parameters, power management options, and server configuration.
"""

import os
from pathlib import Path
from tempfile import gettempdir

from pydantic import BaseModel, Field, field_validator


class WeatherConfig(BaseModel):
    """Weather API configuration."""

    api_key: str
    location: dict[str, float] = Field(default_factory=lambda: {"lat": 0.0, "lon": 0.0})
    city_name: str | None = None
    units: str = "metric"
    language: str = "en"
    update_interval_minutes: int = 30
    forecast_days: int = 5

    @field_validator("update_interval_minutes")
    @classmethod
    def validate_update_interval(cls, v: int) -> int:
        """Validate update interval is not too frequent."""
        if v < 15:
            raise ValueError("Update interval must be at least 15 minutes to conserve battery")
        return v


class DisplayConfig(BaseModel):
    """E-paper display configuration."""

    width: int = 1872
    height: int = 1404
    rotate: int = 0  # 0, 90, 180, 270
    refresh_interval_minutes: int = 30
    partial_refresh: bool = True
    timestamp_format: str = "%Y-%m-%d %H:%M"


class PowerConfig(BaseModel):
    """Power management configuration.

    Note: Power optimizations are applied by deploy/scripts/optimize-power.sh script
    rather than in code. The settings here are primarily used for reference and
    by the power management features that adjust behavior based on battery status.
    """

    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "06:00"
    low_battery_threshold: int = 20
    critical_battery_threshold: int = 10
    wake_up_interval_minutes: int = 60
    wifi_timeout_seconds: int = 30
    disable_hdmi: bool = True
    disable_bluetooth: bool = True
    disable_leds: bool = True
    enable_temp_fs: bool = True
    cpu_governor: str = "powersave"
    cpu_max_freq_mhz: int = 700


class ServerConfig(BaseModel):
    """Server configuration."""

    url: str
    port: int = 8000
    timeout_seconds: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    cache_dir: str = Field(
        default_factory=lambda: os.path.join(gettempdir(), f"weather-cache-{os.getuid()}")
    )
    log_level: str = "INFO"
    image_format: str = "PNG"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str | None = None
    format: str = "json"
    max_size_mb: int = 5
    backup_count: int = 3


class AppConfig(BaseModel):
    """Main application configuration."""

    weather: WeatherConfig
    display: DisplayConfig
    power: PowerConfig
    server: ServerConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    debug: bool = False
    development_mode: bool = False

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "AppConfig":
        """Load configuration from YAML file."""
        import yaml

        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        return cls.model_validate(config_data)
