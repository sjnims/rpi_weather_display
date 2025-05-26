"""Tests for custom exception hierarchy."""

import pytest

from rpi_weather_display.exceptions import (
    APIAuthenticationError,
    APIError,
    APIRateLimitError,
    APITimeoutError,
    BatteryMonitoringError,
    ConfigFileNotFoundError,
    ConfigurationError,
    CriticalBatteryError,
    DisplayError,
    DisplayInitializationError,
    DisplayUpdateError,
    HardwareError,
    ImageRenderingError,
    InvalidAPIResponseError,
    InvalidConfigError,
    MissingConfigError,
    NetworkTimeoutError,
    NetworkUnavailableError,
    PartialRefreshError,
    PiJuiceCommunicationError,
    PiJuiceInitializationError,
    PowerManagementError,
    PowerStateError,
    WakeupSchedulingError,
    WeatherAPIError,
    WeatherDisplayError,
    chain_exception,
)


class TestWeatherDisplayError:
    """Test base exception class."""
    
    def test_base_exception_with_message_only(self):
        """Test creating exception with just a message."""
        exc = WeatherDisplayError("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.details == {}
        
    def test_base_exception_with_details(self):
        """Test creating exception with message and details."""
        details = {"field": "test", "value": 123}
        exc = WeatherDisplayError("Test error", details)
        assert exc.message == "Test error"
        assert exc.details == details
        assert str(exc) == "Test error - Details: {'field': 'test', 'value': 123}"
        
    def test_inheritance_chain(self):
        """Test that all exceptions inherit from base."""
        exc = InvalidConfigError("Config error")
        assert isinstance(exc, ConfigurationError)
        assert isinstance(exc, WeatherDisplayError)
        assert isinstance(exc, Exception)


class TestConfigurationExceptions:
    """Test configuration-related exceptions."""
    
    def test_invalid_config_error(self):
        """Test InvalidConfigError with context."""
        exc = InvalidConfigError(
            "Invalid refresh interval",
            {"field": "refresh_interval", "value": -5, "reason": "Must be positive"}
        )
        assert exc.message == "Invalid refresh interval"
        assert exc.details["field"] == "refresh_interval"
        assert exc.details["value"] == -5
        assert exc.details["reason"] == "Must be positive"
        
    def test_missing_config_error(self):
        """Test MissingConfigError with context."""
        exc = MissingConfigError(
            "Required configuration missing",
            {"field": "api_key", "config_section": "weather"}
        )
        assert exc.details["field"] == "api_key"
        assert exc.details["config_section"] == "weather"
        
    def test_config_file_not_found_error(self):
        """Test ConfigFileNotFoundError with search paths."""
        exc = ConfigFileNotFoundError(
            "Configuration file not found",
            {"path": "/etc/weather/config.yaml", "search_paths": ["/etc", "/home/user"]}
        )
        assert exc.details["path"] == "/etc/weather/config.yaml"
        assert len(exc.details["search_paths"]) == 2


class TestHardwareExceptions:
    """Test hardware-related exceptions."""
    
    def test_display_initialization_error(self):
        """Test DisplayInitializationError."""
        exc = DisplayInitializationError(
            "Failed to initialize e-paper display",
            {"spi_device": "/dev/spidev0.0", "error": "Device not found"}
        )
        assert isinstance(exc, DisplayError)
        assert isinstance(exc, HardwareError)
        assert exc.details["spi_device"] == "/dev/spidev0.0"
        
    def test_image_rendering_error(self):
        """Test ImageRenderingError."""
        exc = ImageRenderingError(
            "Failed to render weather image",
            {"size": (1872, 1404), "format": "1bit", "error": "Insufficient memory"}
        )
        assert exc.details["size"] == (1872, 1404)
        assert exc.details["format"] == "1bit"
        
    def test_partial_refresh_error(self):
        """Test PartialRefreshError."""
        exc = PartialRefreshError(
            "Partial refresh failed",
            {"changed_pixels": 5000, "threshold": 1000, "error": "Display busy"}
        )
        assert exc.details["changed_pixels"] == 5000
        assert exc.details["threshold"] == 1000
        
    def test_display_update_error(self):
        """Test DisplayUpdateError."""
        exc = DisplayUpdateError(
            "Failed to update display",
            {"mode": "partial", "error": "SPI communication error"}
        )
        assert exc.details["mode"] == "partial"


class TestPowerManagementExceptions:
    """Test power management exceptions."""
    
    def test_pijuice_initialization_error(self):
        """Test PiJuiceInitializationError."""
        exc = PiJuiceInitializationError(
            "Failed to initialize PiJuice",
            {"i2c_address": 0x14, "bus": 1, "error": "Device not detected"}
        )
        assert isinstance(exc, PowerManagementError)
        assert exc.details["i2c_address"] == 0x14
        
    def test_pijuice_communication_error(self):
        """Test PiJuiceCommunicationError."""
        exc = PiJuiceCommunicationError(
            "Failed to communicate with PiJuice",
            {"operation": "GetBatteryLevel", "error": "I2C timeout"}
        )
        assert exc.details["operation"] == "GetBatteryLevel"
        
    def test_battery_monitoring_error(self):
        """Test BatteryMonitoringError."""
        exc = BatteryMonitoringError(
            "Failed to read battery status",
            {"source": "pijuice", "error": "Invalid response"}
        )
        assert exc.details["source"] == "pijuice"
        
    def test_critical_battery_error(self):
        """Test CriticalBatteryError."""
        exc = CriticalBatteryError(
            "Battery critically low - initiating shutdown",
            {"level": 5, "threshold": 10, "voltage": 3.2}
        )
        assert exc.details["level"] == 5
        assert exc.details["threshold"] == 10
        assert exc.details["voltage"] == 3.2
        
    def test_power_state_error(self):
        """Test PowerStateError."""
        exc = PowerStateError(
            "Invalid power state transition",
            {"from_state": "ACTIVE", "to_state": "UNKNOWN", "battery_level": 50}
        )
        assert exc.details["from_state"] == "ACTIVE"
        assert exc.details["to_state"] == "UNKNOWN"
        
    def test_wakeup_scheduling_error(self):
        """Test WakeupSchedulingError."""
        exc = WakeupSchedulingError(
            "Failed to schedule wakeup",
            {"target_time": "2025-05-12T10:00:00", "error": "RTC not available"}
        )
        assert exc.details["target_time"] == "2025-05-12T10:00:00"


class TestNetworkExceptions:
    """Test network-related exceptions."""
    
    def test_network_timeout_error(self):
        """Test NetworkTimeoutError."""
        exc = NetworkTimeoutError(
            "Network operation timed out",
            {"operation": "weather_fetch", "timeout": 30, "url": "api.openweathermap.org"}
        )
        assert exc.details["timeout"] == 30
        
    def test_network_unavailable_error(self):
        """Test NetworkUnavailableError."""
        exc = NetworkUnavailableError(
            "No network connectivity",
            {"interfaces_checked": ["wlan0", "eth0"], "dns_test": "failed"}
        )
        assert len(exc.details["interfaces_checked"]) == 2


class TestAPIExceptions:
    """Test API-related exceptions."""
    
    def test_api_error_base(self):
        """Test APIError base class with extended attributes."""
        exc = APIError(
            "API request failed",
            {"endpoint": "/test"},
            status_code=500,
            response_body="Internal Server Error"
        )
        assert exc.message == "API request failed"
        assert exc.status_code == 500
        assert exc.response_body == "Internal Server Error"
        assert exc.details["endpoint"] == "/test"
        
    def test_weather_api_error(self):
        """Test WeatherAPIError."""
        exc = WeatherAPIError(
            "Weather API request failed",
            {"endpoint": "/data/3.0/onecall", "method": "GET"},
            status_code=500,
            response_body="Internal Server Error"
        )
        assert isinstance(exc, APIError)
        assert exc.status_code == 500
        
    def test_api_rate_limit_error(self):
        """Test APIRateLimitError."""
        exc = APIRateLimitError(
            "API rate limit exceeded",
            {"limit": 1000, "window": "daily", "retry_after": 3600},
            status_code=429
        )
        assert exc.status_code == 429
        assert exc.details["retry_after"] == 3600
        
    def test_api_authentication_error(self):
        """Test APIAuthenticationError."""
        exc = APIAuthenticationError(
            "Invalid API key",
            {"api_key_prefix": "abc123...", "endpoint": "/weather"},
            status_code=401
        )
        assert exc.status_code == 401
        assert "abc123..." in exc.details["api_key_prefix"]
        
    def test_api_timeout_error(self):
        """Test APITimeoutError."""
        exc = APITimeoutError(
            "API request timed out",
            {"endpoint": "/data/3.0/onecall", "timeout": 30, "attempt": 3}
        )
        assert exc.details["timeout"] == 30
        assert exc.details["attempt"] == 3
        
    def test_invalid_api_response_error(self):
        """Test InvalidAPIResponseError."""
        exc = InvalidAPIResponseError(
            "Invalid API response format",
            {"expected_fields": ["temp", "humidity"], "received": ["temp"]},
            status_code=200,
            response_body='{"temp": 25}'
        )
        assert exc.status_code == 200
        assert len(exc.details["expected_fields"]) == 2
        assert len(exc.details["received"]) == 1


class TestExceptionChaining:
    """Test exception chaining utility."""
    
    def test_chain_exception(self):
        """Test chaining exceptions for better debugging."""
        original = ValueError("Original error")
        new_exc = WeatherAPIError("API failed", {"url": "test.com"})
        
        chained = chain_exception(new_exc, original)
        
        assert chained is new_exc
        assert chained.__cause__ is original
        assert isinstance(chained.__cause__, ValueError)
        
    def test_chain_exception_preserves_details(self):
        """Test that chaining preserves exception details."""
        original = ConnectionError("Connection failed")
        new_exc = NetworkTimeoutError(
            "Request timed out",
            {"timeout": 30, "retries": 3}
        )
        
        chained = chain_exception(new_exc, original)
        
        assert chained.details["timeout"] == 30
        assert chained.details["retries"] == 3
        if chained.__cause__:
            assert chained.__cause__.args[0] == "Connection failed"
        
    def test_exception_chain_in_practice(self):
        """Test practical exception chaining scenario."""
        try:
            # Simulate original error
            raise ConnectionError("Network unreachable")
        except ConnectionError as e:
            # Chain with custom exception
            with pytest.raises(NetworkUnavailableError) as exc_info:
                raise chain_exception(
                    NetworkUnavailableError(
                        "Cannot connect to weather service",
                        {"service": "OpenWeatherMap", "attempts": 3}
                    ),
                    e
                ) from e
            
            if exc_info.value.__cause__:
                assert exc_info.value.__cause__.args[0] == "Network unreachable"
            assert exc_info.value.details["service"] == "OpenWeatherMap"


class TestExceptionUsagePatterns:
    """Test common usage patterns for the exceptions."""
    
    def test_catching_specific_exceptions(self):
        """Test catching specific exception types."""
        def api_call() -> None:
            raise APIRateLimitError(
                "Too many requests",
                {"limit": 60, "window": "minute"},
                status_code=429
            )
            
        with pytest.raises(APIRateLimitError) as exc_info:
            api_call()
            
        # Can catch as APIRateLimitError
        assert isinstance(exc_info.value, APIRateLimitError)
        # Can also catch as APIError
        assert isinstance(exc_info.value, APIError)
        # Can also catch as WeatherDisplayError
        assert isinstance(exc_info.value, WeatherDisplayError)
        
    def test_exception_context_for_logging(self):
        """Test that exceptions provide good context for logging."""
        exc = PiJuiceCommunicationError(
            "Failed to read battery voltage",
            {
                "operation": "GetBatteryVoltage",
                "attempts": 3,
                "last_error": "I2C bus error",
                "timestamp": "2025-05-12T10:30:00"
            }
        )
        
        # String representation includes details
        exc_str = str(exc)
        assert "Failed to read battery voltage" in exc_str
        assert "Details:" in exc_str
        assert "GetBatteryVoltage" in exc_str
        
    def test_exception_hierarchy_for_handlers(self):
        """Test using exception hierarchy for different handling strategies."""
        # Simulate exceptions that might be raised from different parts of the code
        def raise_display_error() -> None:
            raise DisplayInitializationError("Display init failed")
            
        def raise_pijuice_error() -> None:
            raise PiJuiceInitializationError("PiJuice init failed")
            
        def raise_battery_error() -> None:
            raise BatteryMonitoringError("Battery read failed")
        
        # Test catching and categorizing exceptions
        hardware_errors = []
        display_errors = []
        power_errors = []
        
        error_functions = [raise_display_error, raise_pijuice_error, raise_battery_error]
        
        for error_func in error_functions:
            try:
                error_func()
            except DisplayError as e:
                display_errors.append(e)
                hardware_errors.append(e)  # DisplayError is a HardwareError
            except PowerManagementError as e:
                power_errors.append(e)
                hardware_errors.append(e)  # PowerManagementError is a HardwareError
            except HardwareError as e:
                hardware_errors.append(e)
                
        assert len(display_errors) == 1
        assert len(power_errors) == 2
        assert len(hardware_errors) == 3  # All are hardware errors