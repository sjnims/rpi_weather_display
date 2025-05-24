"""Common fixtures for testing the weather display application."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus


@pytest.fixture()
def mock_subprocess_run() -> Generator[MagicMock, None, None]:
    """Mock subprocess.run to prevent actual command execution during tests."""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_run.return_value = mock_process
        yield mock_run


@pytest.fixture()
def mock_paths_exist() -> Generator[MagicMock, None, None]:
    """Mock Path.exists to prevent filesystem checks during tests."""
    with patch("pathlib.Path.exists", return_value=True) as mock_exists:
        yield mock_exists


@pytest.fixture(autouse=True)
def mock_command_execution(
    mock_subprocess_run: MagicMock, mock_paths_exist: MagicMock
) -> tuple[MagicMock, MagicMock]:
    """Automatically mock command execution for all tests."""
    return mock_subprocess_run, mock_paths_exist


@pytest.fixture()
def test_config_path() -> Path:
    """Get the path to the test config file."""
    # Import here to avoid circular imports during test collection
    from rpi_weather_display.utils import path_resolver

    # Use path resolver consistently to find test data file
    return path_resolver.get_resource_path("tests/data", "test_config.yaml")


@pytest.fixture()
def test_config_data(test_config_path: str) -> dict[str, Any]:
    """Load test configuration data from YAML."""
    with open(test_config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture()
def test_config(test_config_data: dict[str, Any]) -> AppConfig:
    """Create a test application configuration."""
    return AppConfig.model_validate(test_config_data)


@pytest.fixture()
def app_config(test_config_data: dict[str, Any]) -> AppConfig:
    """Create a test application configuration."""
    return AppConfig.model_validate(test_config_data)


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
    # Import here to avoid circular imports during test collection
    from rpi_weather_display.utils import path_resolver

    # Use path resolver to find templates directory
    return path_resolver.get_templates_dir()


@pytest.fixture()
def mock_logger() -> MagicMock:
    """Create a properly mocked logger that prevents output."""
    logger = MagicMock()
    # Mock all logging methods to prevent output
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    logger.log = MagicMock()
    # Mock the logger name
    logger.name = "test_logger"
    return logger
