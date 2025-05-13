"""Common fixtures for testing the weather display application."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus


@pytest.fixture()
def test_config_path() -> Path:
    """Path to test configuration file."""
    return Path(os.path.dirname(__file__)) / "data" / "test_config.yaml"


@pytest.fixture()
def app_config(test_config_path: Path) -> AppConfig:
    """Create test application configuration."""
    # If the test config doesn't exist yet, create a minimal one
    if not test_config_path.exists():
        test_config_path.parent.mkdir(exist_ok=True)
        minimal_config = {
            "weather": {
                "api_key": "test_api_key",
                "city_name": "Test City",
                "units": "metric",
                "language": "en",
                "update_interval_minutes": 30,
                "forecast_days": 5,
            },
            "display": {
                "width": 800,
                "height": 600,
                "rotate": 0,
                "refresh_interval_minutes": 30,
                "partial_refresh": True,
                "timestamp_format": "%Y-%m-%d %H:%M",
            },
            "power": {
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "06:00",
                "low_battery_threshold": 20,
                "critical_battery_threshold": 10,
                "wake_up_interval_minutes": 60,
                "wifi_timeout_seconds": 30,
            },
            "server": {
                "url": "http://localhost",
                "port": 8000,
                "timeout_seconds": 5,
                "retry_attempts": 2,
                "retry_delay_seconds": 1,
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "max_size_mb": 1,
                "backup_count": 1,
            },
            "debug": True,
            "development_mode": True,
        }

        import yaml

        with open(test_config_path, "w") as f:
            yaml.dump(minimal_config, f)

    return AppConfig.from_yaml(test_config_path)


@pytest.fixture()
def mock_battery_status() -> BatteryStatus:
    """Create a mock battery status for testing."""
    return BatteryStatus(
        level=85,
        voltage=3.9,
        current=0.5,
        temperature=25.0,
        state=BatteryState.FULL,
    )


@pytest.fixture()
def mock_server(test_config_path: Path) -> TestClient:
    """Create a FastAPI test client for the server."""
    from rpi_weather_display.server.main import WeatherDisplayServer

    # Create a test server with the test config
    server = WeatherDisplayServer(test_config_path)

    # Create a test client
    client = TestClient(server.app)

    # Return the test client
    return client


@pytest.fixture()
def template_dir() -> Path:
    """Path to templates directory."""
    return Path(os.path.dirname(os.path.dirname(__file__))) / "templates"
