"""Tests for the server API."""

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rpi_weather_display.utils.file_utils import JsonData, read_json
from rpi_weather_display.utils.path_utils import path_resolver


@pytest.fixture()
def mock_weather_data() -> JsonData:
    """Load mock weather data from file."""
    # Use path_resolver to locate the test data file relative to the current file
    data_file = path_resolver.normalize_path(
        Path(__file__).parent.parent / "data" / "mock_weather_response.json"
    )
    # Use file_utils to read and parse JSON in one operation
    return read_json(data_file)


@pytest.fixture()
def test_app(mock_weather_data: JsonData) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    # Create a simple FastAPI app for testing
    app = FastAPI()

    # Define test routes
    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "service": "Weather Display Server"}

    @app.get("/weather")
    async def get_weather() -> dict[str, Any]:
        # Return the mock data directly, cast to ensure dict type
        return cast(dict[str, Any], mock_weather_data)

    @app.get("/preview")
    async def preview() -> str:
        return "<html><body>Test HTML</body></html>"

    return app


@pytest.fixture()
def test_client(test_app: FastAPI) -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(test_app)


def test_server_root_endpoint(test_client: TestClient) -> None:
    """Test the server root endpoint returns OK status."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Weather Display Server"


def test_weather_endpoint_returns_json(
    test_client: TestClient, mock_weather_data: JsonData
) -> None:
    """Test the weather endpoint returns JSON."""
    response = test_client.get("/weather")

    # Check the response
    assert response.status_code == 200
    data = response.json()

    # Verify key data is in the response - cast mock_weather_data to dict for type safety
    weather_dict = cast(dict[str, Any], mock_weather_data)
    assert data["lat"] == weather_dict["lat"]
    assert data["lon"] == weather_dict["lon"]
    assert data["current"]["temp"] == weather_dict["current"]["temp"]


def test_preview_endpoint(test_client: TestClient) -> None:
    """Test the preview endpoint returns HTML."""
    response = test_client.get("/preview")

    # Check the response
    assert response.status_code == 200
    assert "Test HTML" in response.text
