"""Tests for the system models.

This module tests the Pydantic models for system information, including
battery status, network conditions, and overall system metrics.
"""

from datetime import datetime, timedelta
from typing import TypedDict

import pytest

from rpi_weather_display.models.system import (
    BatteryState,
    BatteryStatus,
    NetworkState,
    NetworkStatus,
    SystemStatus,
)


# Type definitions for test data
class BatteryStatusData(TypedDict, total=False):
    """Type definition for battery status test data."""
    level: int
    voltage: float
    current: float
    temperature: float
    state: BatteryState
    time_remaining: int


class NetworkStatusData(TypedDict, total=False):
    """Type definition for network status test data."""
    state: NetworkState
    ssid: str | None
    ip_address: str | None
    signal_strength: int | None
    last_connection: datetime | None


class SystemStatusData(TypedDict):
    """Type definition for system status test data."""
    hostname: str
    uptime: int
    cpu_temp: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    battery: BatteryStatusData
    network: NetworkStatusData
    last_refresh: datetime | None
    metrics: dict[str, float]


# Test fixtures for sample data


@pytest.fixture()
def battery_status_charging() -> BatteryStatusData:
    """Sample battery status data for a charging battery."""
    return {
        "level": 75,
        "voltage": 3.85,
        "current": 350.0,
        "temperature": 27.5,
        "state": BatteryState.CHARGING,
    }


@pytest.fixture()
def battery_status_discharging() -> BatteryStatusData:
    """Sample battery status data for a discharging battery."""
    return {
        "level": 65,
        "voltage": 3.75,
        "current": -120.0,
        "temperature": 26.8,
        "state": BatteryState.DISCHARGING,
    }


@pytest.fixture()
def battery_status_low() -> BatteryStatusData:
    """Sample battery status data for a low battery."""
    return {
        "level": 15,
        "voltage": 3.6,
        "current": -100.0,
        "temperature": 26.0,
        "state": BatteryState.DISCHARGING,
    }


@pytest.fixture()
def battery_status_critical() -> BatteryStatusData:
    """Sample battery status data for a critically low battery."""
    return {
        "level": 5,
        "voltage": 3.5,
        "current": -90.0,
        "temperature": 25.5,
        "state": BatteryState.DISCHARGING,
        "time_remaining": 30,  # 30 minutes remaining
    }


@pytest.fixture()
def battery_status_full() -> BatteryStatusData:
    """Sample battery status data for a full battery."""
    return {
        "level": 100,
        "voltage": 4.2,
        "current": 0.0,
        "temperature": 26.0,
        "state": BatteryState.FULL,
    }


@pytest.fixture()
def network_status_connected() -> NetworkStatusData:
    """Sample network status data for connected state."""
    return {
        "state": NetworkState.CONNECTED,
        "ssid": "MyHomeWifi",
        "ip_address": "192.168.1.100",
        "signal_strength": -65,  # dBm
        "last_connection": datetime.now() - timedelta(minutes=30),
    }


@pytest.fixture()
def network_status_disconnected() -> NetworkStatusData:
    """Sample network status data for disconnected state."""
    return {
        "state": NetworkState.DISCONNECTED,
    }


@pytest.fixture()
def network_status_error() -> NetworkStatusData:
    """Sample network status data for error state."""
    return {
        "state": NetworkState.ERROR,
        "ssid": "MyHomeWifi",
        "last_connection": datetime.now() - timedelta(hours=2),
    }


@pytest.fixture()
def system_status_data(
    battery_status_charging: BatteryStatusData, network_status_connected: NetworkStatusData
) -> SystemStatusData:
    """Sample system status data."""
    return {
        "hostname": "rpi-weather",
        "uptime": 86400,  # 24 hours in seconds
        "cpu_temp": 42.5,
        "cpu_usage": 12.0,
        "memory_usage": 34.5,
        "disk_usage": 45.2,
        "battery": battery_status_charging,
        "network": network_status_connected,
        "last_refresh": datetime.now() - timedelta(minutes=15),
        "metrics": {
            "wifi_power_save": 1.0,
            "hdmi_power": 0.0,
            "bluetooth_power": 0.0,
        },
    }


# Tests for enums


def test_battery_state_enum() -> None:
    """Test BatteryState enum values."""
    assert BatteryState.CHARGING == "charging"
    assert BatteryState.DISCHARGING == "discharging"
    assert BatteryState.FULL == "full"
    assert BatteryState.UNKNOWN == "unknown"


def test_network_state_enum() -> None:
    """Test NetworkState enum values."""
    assert NetworkState.CONNECTED == "connected"
    assert NetworkState.DISCONNECTED == "disconnected"
    assert NetworkState.CONNECTING == "connecting"
    assert NetworkState.ERROR == "error"


# Tests for BatteryStatus model


def test_battery_status_charging(battery_status_charging: BatteryStatusData) -> None:
    """Test BatteryStatus model with charging state."""
    status = BatteryStatus.model_validate(battery_status_charging)

    # Check basic attributes
    assert status.level == 75
    assert status.voltage == 3.85
    assert status.current == 350.0
    assert status.temperature == 27.5
    assert status.state == BatteryState.CHARGING
    assert status.time_remaining is None

    # Check computed properties
    assert not status.is_low
    assert not status.is_critical


def test_battery_status_discharging(battery_status_discharging: BatteryStatusData) -> None:
    """Test BatteryStatus model with discharging state."""
    status = BatteryStatus.model_validate(battery_status_discharging)

    # Check basic attributes
    assert status.level == 65
    assert status.voltage == 3.75
    assert status.current == -120.0
    assert status.temperature == 26.8
    assert status.state == BatteryState.DISCHARGING

    # Check computed properties
    assert not status.is_low
    assert not status.is_critical


def test_battery_status_low(battery_status_low: BatteryStatusData) -> None:
    """Test BatteryStatus model with low battery."""
    status = BatteryStatus.model_validate(battery_status_low)

    # Check basic attributes
    assert status.level == 15
    assert status.voltage == 3.6
    assert status.current == -100.0
    assert status.temperature == 26.0
    assert status.state == BatteryState.DISCHARGING

    # Check computed properties
    assert status.is_low
    assert not status.is_critical


def test_battery_status_critical(battery_status_critical: BatteryStatusData) -> None:
    """Test BatteryStatus model with critically low battery."""
    status = BatteryStatus.model_validate(battery_status_critical)

    # Check basic attributes
    assert status.level == 5
    assert status.voltage == 3.5
    assert status.current == -90.0
    assert status.temperature == 25.5
    assert status.state == BatteryState.DISCHARGING
    assert status.time_remaining == 30

    # Check computed properties
    assert status.is_low
    assert status.is_critical


def test_battery_status_full(battery_status_full: BatteryStatusData) -> None:
    """Test BatteryStatus model with full battery."""
    status = BatteryStatus.model_validate(battery_status_full)

    # Check basic attributes
    assert status.level == 100
    assert status.voltage == 4.2
    assert status.current == 0.0
    assert status.temperature == 26.0
    assert status.state == BatteryState.FULL

    # Check computed properties
    assert not status.is_low
    assert not status.is_critical


def test_battery_status_level_validation() -> None:
    """Test validation for battery level."""
    # Valid level (0-100)
    status = BatteryStatus(level=0, voltage=3.5, current=0.0, temperature=25.0)
    assert status.level == 0

    status = BatteryStatus(level=100, voltage=3.5, current=0.0, temperature=25.0)
    assert status.level == 100


def test_battery_status_with_unknown_state() -> None:
    """Test BatteryStatus with unknown state."""
    status = BatteryStatus(level=50, voltage=3.7, current=0.0, temperature=25.0)
    assert status.state == BatteryState.UNKNOWN
    assert not status.is_low
    assert not status.is_critical


# Tests for NetworkStatus model


def test_network_status_connected(network_status_connected: NetworkStatusData) -> None:
    """Test NetworkStatus model with connected state."""
    status = NetworkStatus.model_validate(network_status_connected)

    # Check attributes
    assert status.state == NetworkState.CONNECTED
    assert status.ssid == "MyHomeWifi"
    assert status.ip_address == "192.168.1.100"
    assert status.signal_strength == -65
    assert isinstance(status.last_connection, datetime)


def test_network_status_disconnected(network_status_disconnected: NetworkStatusData) -> None:
    """Test NetworkStatus model with disconnected state."""
    status = NetworkStatus.model_validate(network_status_disconnected)

    # Check attributes
    assert status.state == NetworkState.DISCONNECTED
    assert status.ssid is None
    assert status.ip_address is None
    assert status.signal_strength is None
    assert status.last_connection is None


def test_network_status_error(network_status_error: NetworkStatusData) -> None:
    """Test NetworkStatus model with error state."""
    status = NetworkStatus.model_validate(network_status_error)

    # Check attributes
    assert status.state == NetworkState.ERROR
    assert status.ssid == "MyHomeWifi"
    assert status.ip_address is None
    assert status.signal_strength is None
    assert isinstance(status.last_connection, datetime)


def test_network_status_default_values() -> None:
    """Test NetworkStatus default values."""
    status = NetworkStatus()

    assert status.state == NetworkState.DISCONNECTED
    assert status.ssid is None
    assert status.ip_address is None
    assert status.signal_strength is None
    assert status.last_connection is None


# Tests for SystemStatus model


def test_system_status(system_status_data: SystemStatusData) -> None:
    """Test SystemStatus model."""
    status = SystemStatus.model_validate(system_status_data)

    # Check basic attributes
    assert status.hostname == "rpi-weather"
    assert status.uptime == 86400
    assert status.cpu_temp == 42.5
    assert status.cpu_usage == 12.0
    assert status.memory_usage == 34.5
    assert status.disk_usage == 45.2

    # Check nested models
    assert isinstance(status.battery, BatteryStatus)
    assert status.battery.level == 75
    assert status.battery.state == BatteryState.CHARGING

    assert isinstance(status.network, NetworkStatus)
    assert status.network.state == NetworkState.CONNECTED
    assert status.network.ssid == "MyHomeWifi"

    # Check metrics
    assert status.metrics["wifi_power_save"] == 1.0
    assert status.metrics["hdmi_power"] == 0.0

    # Check auto-generated fields
    assert isinstance(status.last_updated, datetime)
    assert isinstance(status.last_refresh, datetime)


def test_system_status_default_values() -> None:
    """Test SystemStatus with minimal required values."""
    status = SystemStatus(
        hostname="rpi-weather",
        uptime=3600,
        cpu_temp=40.0,
        cpu_usage=10.0,
        memory_usage=30.0,
        disk_usage=50.0,
        battery=BatteryStatus(level=80, voltage=3.8, current=0.0, temperature=25.0),
        network=NetworkStatus(),
    )

    # Check default values
    assert isinstance(status.last_updated, datetime)
    assert status.last_refresh is None
    assert status.metrics == {}


def test_system_status_with_metrics() -> None:
    """Test SystemStatus with custom metrics."""
    status = SystemStatus(
        hostname="rpi-weather",
        uptime=3600,
        cpu_temp=40.0,
        cpu_usage=10.0,
        memory_usage=30.0,
        disk_usage=50.0,
        battery=BatteryStatus(level=80, voltage=3.8, current=0.0, temperature=25.0),
        network=NetworkStatus(),
        metrics={
            "custom_metric_1": 42.0,
            "custom_metric_2": 123.45,
        },
    )

    assert status.metrics["custom_metric_1"] == 42.0
    assert status.metrics["custom_metric_2"] == 123.45


if __name__ == "__main__":
    pytest.main()
