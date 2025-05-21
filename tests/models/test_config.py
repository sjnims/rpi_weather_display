"""Tests for the configuration models.

Tests validate the behavior of Pydantic models in config.py, including:
- Default values
- Validators
- Configuration loading from YAML
- Inheritance and composition
"""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml
from pydantic import ValidationError

from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    LoggingConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)


class TestWeatherConfig:
    """Test cases for WeatherConfig model."""

    def test_default_values(self) -> None:
        """Test default values for WeatherConfig."""
        # Only required field is api_key
        weather_config = WeatherConfig(api_key="test_key")

        assert weather_config.api_key == "test_key"
        assert weather_config.location == {"lat": 0.0, "lon": 0.0}
        assert weather_config.city_name is None
        assert weather_config.units == "metric"
        assert weather_config.language == "en"
        assert weather_config.update_interval_minutes == 30
        assert weather_config.forecast_days == 5

    def test_custom_values(self) -> None:
        """Test WeatherConfig with custom values."""
        weather_config = WeatherConfig(
            api_key="custom_key",
            location={"lat": 40.7128, "lon": -74.0060},
            city_name="New York",
            units="imperial",
            language="fr",
            update_interval_minutes=60,
            forecast_days=7,
        )

        assert weather_config.api_key == "custom_key"
        assert weather_config.location == {"lat": 40.7128, "lon": -74.0060}
        assert weather_config.city_name == "New York"
        assert weather_config.units == "imperial"
        assert weather_config.language == "fr"
        assert weather_config.update_interval_minutes == 60
        assert weather_config.forecast_days == 7

    def test_update_interval_validator(self) -> None:
        """Test validator for update_interval_minutes."""
        # Valid interval (>= 15 minutes)
        weather_config = WeatherConfig(api_key="test_key", update_interval_minutes=15)
        assert weather_config.update_interval_minutes == 15

        # Invalid interval (< 15 minutes)
        with pytest.raises(ValidationError) as excinfo:
            WeatherConfig(api_key="test_key", update_interval_minutes=10)

        error_details = str(excinfo.value)
        assert "Update interval must be at least 15 minutes" in error_details

    def test_hourly_forecast_count_validator(self) -> None:
        """Test validator for hourly_forecast_count."""
        # Valid counts
        min_count = WeatherConfig(api_key="test_key", hourly_forecast_count=1)
        assert min_count.hourly_forecast_count == 1

        max_count = WeatherConfig(api_key="test_key", hourly_forecast_count=48)
        assert max_count.hourly_forecast_count == 48

        # Invalid counts
        with pytest.raises(ValidationError) as excinfo:
            WeatherConfig(api_key="test_key", hourly_forecast_count=0)
        error_details = str(excinfo.value)
        assert "Hourly forecast count must be between 1 and 48" in error_details

        with pytest.raises(ValidationError) as excinfo:
            WeatherConfig(api_key="test_key", hourly_forecast_count=49)
        error_details = str(excinfo.value)
        assert "Hourly forecast count must be between 1 and 48" in error_details


class TestDisplayConfig:
    """Test cases for DisplayConfig model."""

    def test_default_values(self) -> None:
        """Test default values for DisplayConfig."""
        display_config = DisplayConfig()

        assert display_config.width == 1872
        assert display_config.height == 1404
        assert display_config.rotate == 0
        assert display_config.refresh_interval_minutes == 30
        assert display_config.partial_refresh is True
        assert display_config.timestamp_format == "%Y-%m-%d %H:%M"
        assert display_config.pressure_units == "hPa"

    def test_custom_values(self) -> None:
        """Test DisplayConfig with custom values."""
        display_config = DisplayConfig(
            width=800,
            height=600,
            rotate=90,
            refresh_interval_minutes=60,
            partial_refresh=False,
            timestamp_format="%H:%M %d/%m/%Y",
            pressure_units="mmHg",
        )

        assert display_config.width == 800
        assert display_config.height == 600
        assert display_config.rotate == 90
        assert display_config.refresh_interval_minutes == 60
        assert display_config.partial_refresh is False
        assert display_config.timestamp_format == "%H:%M %d/%m/%Y"
        assert display_config.pressure_units == "mmHg"

    def test_invalid_pressure_units(self) -> None:
        """Test validation of pressure units."""
        with pytest.raises(ValueError, match="Pressure units must be one of"):
            DisplayConfig(pressure_units="invalid")


class TestPowerConfig:
    """Test cases for PowerConfig model."""

    def test_default_values(self) -> None:
        """Test default values for PowerConfig."""
        power_config = PowerConfig()

        assert power_config.quiet_hours_start == "23:00"
        assert power_config.quiet_hours_end == "06:00"
        assert power_config.low_battery_threshold == 20
        assert power_config.critical_battery_threshold == 10
        assert power_config.wake_up_interval_minutes == 60
        assert power_config.wifi_timeout_seconds == 30
        assert power_config.enable_battery_aware_wifi is True
        assert power_config.wifi_power_save_mode == "auto"
        assert power_config.retry_initial_delay_seconds == 1.0
        assert power_config.retry_max_delay_seconds == 300.0
        assert power_config.retry_backoff_factor == 2.0
        assert power_config.retry_jitter_factor == 0.1
        assert power_config.retry_max_attempts == 5
        assert power_config.disable_hdmi is True
        assert power_config.disable_bluetooth is True
        assert power_config.disable_leds is True
        assert power_config.enable_temp_fs is True
        assert power_config.cpu_governor == "powersave"
        assert power_config.cpu_max_freq_mhz == 700
        assert power_config.enable_pijuice_events is True
        assert power_config.low_charge_action == "SYSTEM_HALT"
        assert power_config.low_charge_delay == 5
        assert power_config.button_press_action == "SYSDOWN"
        assert power_config.button_press_delay == 180

    def test_custom_values(self) -> None:
        """Test PowerConfig with custom values."""
        power_config = PowerConfig(
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            low_battery_threshold=30,
            critical_battery_threshold=15,
            wake_up_interval_minutes=120,
            wifi_timeout_seconds=45,
            enable_battery_aware_wifi=False,
            wifi_power_save_mode="off",
            retry_initial_delay_seconds=2.0,
            retry_max_delay_seconds=60.0,
            retry_backoff_factor=1.5,
            retry_jitter_factor=0.2,
            retry_max_attempts=3,
            disable_hdmi=False,
            disable_bluetooth=False,
            disable_leds=False,
            enable_temp_fs=False,
            cpu_governor="performance",
            cpu_max_freq_mhz=1000,
            enable_pijuice_events=False,
            low_charge_action="NO_ACTION",
            low_charge_delay=10,
            button_press_action="SYSTEM_POWER_OFF",
            button_press_delay=60,
        )

        assert power_config.quiet_hours_start == "22:00"
        assert power_config.quiet_hours_end == "07:00"
        assert power_config.low_battery_threshold == 30
        assert power_config.critical_battery_threshold == 15
        assert power_config.wake_up_interval_minutes == 120
        assert power_config.wifi_timeout_seconds == 45
        assert power_config.enable_battery_aware_wifi is False
        assert power_config.wifi_power_save_mode == "off"
        assert power_config.retry_initial_delay_seconds == 2.0
        assert power_config.retry_max_delay_seconds == 60.0
        assert power_config.retry_backoff_factor == 1.5
        assert power_config.retry_jitter_factor == 0.2
        assert power_config.retry_max_attempts == 3
        assert power_config.disable_hdmi is False
        assert power_config.disable_bluetooth is False
        assert power_config.disable_leds is False
        assert power_config.enable_temp_fs is False
        assert power_config.cpu_governor == "performance"
        assert power_config.cpu_max_freq_mhz == 1000
        assert power_config.enable_pijuice_events is False
        assert power_config.low_charge_action == "NO_ACTION"
        assert power_config.low_charge_delay == 10
        assert power_config.button_press_action == "SYSTEM_POWER_OFF"
        assert power_config.button_press_delay == 60

    def test_wifi_power_save_mode_validator(self) -> None:
        """Test validation of WiFi power save mode."""
        # Valid modes
        for mode in ["auto", "off", "on", "aggressive"]:
            config = PowerConfig(wifi_power_save_mode=mode)
            assert config.wifi_power_save_mode == mode

        # Invalid mode
        with pytest.raises(ValidationError) as excinfo:
            PowerConfig(wifi_power_save_mode="invalid_mode")

        error_details = str(excinfo.value)
        assert "WiFi power save mode must be one of" in error_details

    def test_low_charge_action_validator(self) -> None:
        """Test validation of low charge action."""
        # Valid actions
        valid_actions = [
            "NO_ACTION",
            "SYSTEM_HALT",
            "SYSTEM_HALT_POW_OFF",
            "SYSTEM_POWER_OFF",
            "SYSTEM_POWER_ON",
            "SYSTEM_REBOOT",
            "SYSTEM_WAKEUP",
        ]

        for action in valid_actions:
            config = PowerConfig(low_charge_action=action)
            assert config.low_charge_action == action

        # Invalid action
        with pytest.raises(ValidationError) as excinfo:
            PowerConfig(low_charge_action="INVALID_ACTION")

        error_details = str(excinfo.value)
        assert "Low charge action must be one of" in error_details


class TestServerConfig:
    """Test cases for ServerConfig model."""

    def test_default_values(self) -> None:
        """Test default values for ServerConfig."""
        server_config = ServerConfig(url="http://localhost")

        assert server_config.url == "http://localhost"
        assert server_config.port == 8000
        assert server_config.timeout_seconds == 10
        assert server_config.retry_attempts == 3
        assert server_config.retry_delay_seconds == 5
        assert server_config.log_level == "INFO"
        assert server_config.image_format == "PNG"

        # Default for cache_dir is now an empty string (using path_resolver's default)
        assert server_config.cache_dir == ""

    def test_custom_values(self) -> None:
        """Test ServerConfig with custom values."""
        server_config = ServerConfig(
            url="http://example.com",
            port=5000,
            timeout_seconds=20,
            retry_attempts=5,
            retry_delay_seconds=10,
            cache_dir="/custom/cache/dir",
            log_level="DEBUG",
            image_format="JPEG",
        )

        assert server_config.url == "http://example.com"
        assert server_config.port == 5000
        assert server_config.timeout_seconds == 20
        assert server_config.retry_attempts == 5
        assert server_config.retry_delay_seconds == 10
        assert server_config.cache_dir == "/custom/cache/dir"
        assert server_config.log_level == "DEBUG"
        assert server_config.image_format == "JPEG"


class TestLoggingConfig:
    """Test cases for LoggingConfig model."""

    def test_default_values(self) -> None:
        """Test default values for LoggingConfig."""
        logging_config = LoggingConfig()

        assert logging_config.level == "INFO"
        assert logging_config.file is None
        assert logging_config.format == "json"
        assert logging_config.max_size_mb == 5
        assert logging_config.backup_count == 3

    def test_custom_values(self) -> None:
        """Test LoggingConfig with custom values."""
        logging_config = LoggingConfig(
            level="DEBUG",
            file="/var/log/weather.log",
            format="text",
            max_size_mb=10,
            backup_count=5,
        )

        assert logging_config.level == "DEBUG"
        assert logging_config.file == "/var/log/weather.log"
        assert logging_config.format == "text"
        assert logging_config.max_size_mb == 10
        assert logging_config.backup_count == 5


class TestAppConfig:
    """Test cases for AppConfig model."""

    def test_minimal_config(self) -> None:
        """Test minimal valid AppConfig."""
        app_config = AppConfig(
            weather=WeatherConfig(api_key="test_key"),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
        )

        assert app_config.weather.api_key == "test_key"
        assert isinstance(app_config.display, DisplayConfig)
        assert isinstance(app_config.power, PowerConfig)
        assert app_config.server.url == "http://localhost"
        assert isinstance(app_config.logging, LoggingConfig)
        assert app_config.debug is False
        assert app_config.development_mode is False

    def test_complete_config(self) -> None:
        """Test complete AppConfig with custom values."""
        app_config = AppConfig(
            weather=WeatherConfig(
                api_key="custom_key",
                location={"lat": 40.7128, "lon": -74.0060},
                city_name="New York",
            ),
            display=DisplayConfig(
                width=800,
                height=600,
            ),
            power=PowerConfig(
                quiet_hours_start="22:00",
                quiet_hours_end="07:00",
            ),
            server=ServerConfig(
                url="http://example.com",
                port=5000,
            ),
            logging=LoggingConfig(
                level="DEBUG",
                file="/var/log/weather.log",
            ),
            debug=True,
            development_mode=True,
        )

        assert app_config.weather.api_key == "custom_key"
        assert app_config.weather.location == {"lat": 40.7128, "lon": -74.0060}
        assert app_config.weather.city_name == "New York"

        assert app_config.display.width == 800
        assert app_config.display.height == 600

        assert app_config.power.quiet_hours_start == "22:00"
        assert app_config.power.quiet_hours_end == "07:00"

        assert app_config.server.url == "http://example.com"
        assert app_config.server.port == 5000

        assert app_config.logging.level == "DEBUG"
        assert app_config.logging.file == "/var/log/weather.log"

        assert app_config.debug is True
        assert app_config.development_mode is True

    def test_default_logging_config(self) -> None:
        """Test that logging config gets default values when not provided."""
        app_config = AppConfig(
            weather=WeatherConfig(api_key="test_key"),
            display=DisplayConfig(),
            power=PowerConfig(),
            server=ServerConfig(url="http://localhost"),
        )

        assert isinstance(app_config.logging, LoggingConfig)
        assert app_config.logging.level == "INFO"
        assert app_config.logging.file is None
        assert app_config.logging.format == "json"

    def test_from_yaml(self) -> None:
        """Test loading configuration from YAML file."""
        yaml_content = """
        weather:
          api_key: test_yaml_key
          city_name: London
          units: metric
          update_interval_minutes: 30
        display:
          width: 800
          height: 600
          pressure_units: mmHg
        power:
          quiet_hours_start: "23:00"
          quiet_hours_end: "06:00"
        server:
          url: http://test-server
          port: 8080
        logging:
          level: DEBUG
        debug: true
        """

        # Mock open to return our test YAML
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            # Mock yaml.safe_load to return parsed test data
            with patch("yaml.safe_load", return_value=yaml.safe_load(yaml_content)):
                config = AppConfig.from_yaml("dummy_path.yaml")

                assert config.weather.api_key == "test_yaml_key"
                assert config.weather.city_name == "London"
                assert config.display.width == 800
                assert config.display.height == 600
                assert config.display.pressure_units == "mmHg"
                assert config.server.url == "http://test-server"
                assert config.server.port == 8080
                assert config.logging.level == "DEBUG"
                assert config.debug is True

    def test_from_yaml_with_real_file(self, tmp_path: Path) -> None:
        """Test loading configuration from an actual YAML file."""
        # Create a temporary YAML file
        config_path = tmp_path / "test_config.yaml"
        test_yaml_content = """
        weather:
          api_key: test_real_yaml_key
          city_name: Berlin
          units: metric
        display:
          width: 1280
          height: 720
          pressure_units: inHg
        power:
          quiet_hours_start: "22:00"
        server:
          url: http://test-yaml-server
        """
        config_path.write_text(test_yaml_content)

        # Load the config from the file
        config = AppConfig.from_yaml(config_path)

        # Verify the loaded values
        assert config.weather.api_key == "test_real_yaml_key"
        assert config.weather.city_name == "Berlin"
        assert config.display.width == 1280
        assert config.display.height == 720
        assert config.display.pressure_units == "inHg"
        assert config.server.url == "http://test-yaml-server"

        # Check defaults are set for values not in the YAML
        assert config.weather.units == "metric"
        assert config.power.quiet_hours_end == "06:00"
        assert config.server.port == 8000
        assert config.logging.level == "INFO"
        assert config.debug is False

    def test_missing_required_fields(self) -> None:
        """Test validation error when required fields are missing."""
        # Missing api_key in weather config
        with pytest.raises(ValidationError) as excinfo:
            AppConfig(
                weather={"location": {"lat": 0.0, "lon": 0.0}},  # type: ignore # Missing api_key
                display=DisplayConfig(),
                power=PowerConfig(),
                server=ServerConfig(url="http://localhost"),
            )

        error_details = str(excinfo.value)
        assert "weather.api_key" in error_details
        assert "Field required" in error_details

        # Missing url in server config
        with pytest.raises(ValidationError) as excinfo:
            AppConfig(
                weather=WeatherConfig(api_key="test_key"),
                display=DisplayConfig(),
                power=PowerConfig(),
                server={"port": 8000},  # type: ignore # Missing url
            )

        error_details = str(excinfo.value)
        assert "server.url" in error_details
        assert "Field required" in error_details
