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
    hourly_forecast_count: int = 24

    @field_validator("update_interval_minutes")
    @classmethod
    def validate_update_interval(cls, v: int) -> int:
        """Validate update interval is not too frequent."""
        if v < 15:
            raise ValueError("Update interval must be at least 15 minutes to conserve battery")
        return v

    @field_validator("hourly_forecast_count")
    @classmethod
    def validate_hourly_forecast_count(cls, v: int) -> int:
        """Validate the number of hourly forecasts to show."""
        if v < 1 or v > 48:
            raise ValueError("Hourly forecast count must be between 1 and 48")
        return v


class DisplayConfig(BaseModel):
    """E-paper display configuration."""

    width: int = 1872
    height: int = 1404
    rotate: int = 0  # 0, 90, 180, 270
    refresh_interval_minutes: int = 30
    refresh_interval_low_battery_minutes: int = 60  # Interval when battery is low
    refresh_interval_critical_battery_minutes: int = 120  # Interval when battery is critical
    refresh_interval_charging_minutes: int = 15  # Interval when charging
    battery_aware_refresh: bool = True  # Whether to adjust refresh intervals based on battery
    partial_refresh: bool = True
    pixel_diff_threshold: int = 10  # Threshold for considering a pixel changed
    pixel_diff_threshold_low_battery: int = 20  # Threshold when battery is low
    pixel_diff_threshold_critical_battery: int = 30  # Threshold when battery is critical
    min_changed_pixels: int = 100  # Minimum number of changed pixels to trigger refresh
    min_changed_pixels_low_battery: int = 250  # Minimum when battery is low
    min_changed_pixels_critical_battery: int = 500  # Minimum when battery is critical
    timestamp_format: str = "%Y-%m-%d %H:%M"
    time_format: str | None = None  # When None, will use AM/PM without leading zeros
    pressure_units: str = "hPa"  # Options: "hPa", "mmHg", "inHg"
    display_datetime_format: str | None = None  # Format for displayed dates and times
    battery_aware_threshold: bool = True  # Whether to adjust thresholds based on battery

    @field_validator("pressure_units")
    @classmethod
    def validate_pressure_units(cls, v: str) -> str:
        """Validate pressure units are one of the supported types."""
        valid_units = ["hPa", "mmHg", "inHg"]
        if v not in valid_units:
            raise ValueError(f"Pressure units must be one of: {', '.join(valid_units)}")
        return v


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
    enable_battery_aware_wifi: bool = True
    wifi_power_save_mode: str = "auto"  # Options: "auto", "off", "on", "aggressive"
    retry_initial_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 300.0  # 5 minutes max delay
    retry_backoff_factor: float = 2.0
    retry_jitter_factor: float = 0.1  # 10% jitter
    retry_max_attempts: int = 5
    disable_hdmi: bool = True
    disable_bluetooth: bool = True
    disable_leds: bool = True
    enable_temp_fs: bool = True
    cpu_governor: str = "powersave"
    cpu_max_freq_mhz: int = 700
    
    # PiJuice event handlers configuration
    enable_pijuice_events: bool = True
    low_charge_action: str = "SYSTEM_HALT"  # Action to take on LOW_CHARGE event
    low_charge_delay: int = 5  # Delay in seconds before taking action
    button_press_action: str = "SYSDOWN"  # Action for button press (SW1)
    button_press_delay: int = 180  # Delay in seconds for button press (SW1)
    
    @field_validator("wifi_power_save_mode")
    @classmethod
    def validate_wifi_power_save_mode(cls, v: str) -> str:
        """Validate WiFi power save mode is one of the supported types."""
        valid_modes = ["auto", "off", "on", "aggressive"]
        if v not in valid_modes:
            raise ValueError(f"WiFi power save mode must be one of: {', '.join(valid_modes)}")
        return v
        
    @field_validator("low_charge_action")
    @classmethod
    def validate_low_charge_action(cls, v: str) -> str:
        """Validate low charge action is valid."""
        valid_actions = [
            "NO_ACTION", "SYSTEM_HALT", "SYSTEM_HALT_POW_OFF", 
            "SYSTEM_POWER_OFF", "SYSTEM_POWER_ON", "SYSTEM_REBOOT", 
            "SYSTEM_WAKEUP"
        ]
        if v not in valid_actions:
            raise ValueError(f"Low charge action must be one of: {', '.join(valid_actions)}")
        return v


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
