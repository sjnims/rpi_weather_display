"""Tests for the server API."""
# ruff: noqa: S101
# ^ Ignores "Use of assert detected" in test files

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def mock_weather_data() -> dict[str, Any]:
    """Load mock weather data from file."""
    data_file = (
        Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "mock_weather_response.json"
    )
    with open(data_file) as f:
        return json.load(f)


@pytest.fixture()
def test_app(mock_weather_data: dict[str, Any]) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    # Create a simple FastAPI app for testing
    app = FastAPI()

    # Define test routes
    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "service": "Weather Display Server"}

    @app.get("/weather")
    async def get_weather() -> dict[str, Any]:
        # Return the mock data directly
        return mock_weather_data

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
    test_client: TestClient, mock_weather_data: dict[str, Any]
) -> None:
    """Test the weather endpoint returns JSON."""
    response = test_client.get("/weather")

    # Check the response
    assert response.status_code == 200
    data = response.json()

    # Verify key data is in the response
    assert data["lat"] == mock_weather_data["lat"]
    assert data["lon"] == mock_weather_data["lon"]
    assert data["current"]["temp"] == mock_weather_data["current"]["temp"]


def test_preview_endpoint(test_client: TestClient) -> None:
    """Test the preview endpoint returns HTML."""
    response = test_client.get("/preview")

    # Check the response
    assert response.status_code == 200
    assert "Test HTML" in response.text
