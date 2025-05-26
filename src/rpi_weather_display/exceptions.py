"""Custom exception hierarchy for the weather display application.

This module defines domain-specific exceptions to provide better error handling,
clearer intent, and improved debugging capabilities throughout the application.

Exception Hierarchy:
    WeatherDisplayError (Base)
    ├── ConfigurationError
    │   ├── InvalidConfigError
    │   ├── MissingConfigError
    │   └── ConfigFileNotFoundError
    ├── HardwareError
    │   ├── DisplayError
    │   │   ├── DisplayInitializationError
    │   │   ├── ImageRenderingError
    │   │   ├── PartialRefreshError
    │   │   └── DisplayUpdateError
    │   └── PowerManagementError
    │       ├── PiJuiceInitializationError
    │       ├── PiJuiceCommunicationError
    │       ├── BatteryMonitoringError
    │       ├── CriticalBatteryError
    │       ├── PowerStateError
    │       └── WakeupSchedulingError
    ├── NetworkError
    │   ├── NetworkTimeoutError
    │   └── NetworkUnavailableError
    └── APIError
        ├── WeatherAPIError
        ├── APIRateLimitError
        ├── APIAuthenticationError
        ├── APITimeoutError
        └── InvalidAPIResponseError
"""

from typing import Any


# Base Exception
class WeatherDisplayError(Exception):
    """Base exception for all weather display application errors.
    
    This is the root exception that all custom exceptions inherit from,
    allowing for broad exception handling when needed.
    
    Attributes:
        message: Human-readable error description
        details: Optional dictionary containing additional error context
    """
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize the exception with message and optional details.
        
        Args:
            message: Human-readable error description
            details: Optional dictionary containing additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        
    def __str__(self) -> str:
        """Return string representation of the exception."""
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


# Configuration Exceptions
class ConfigurationError(WeatherDisplayError):
    """Base exception for configuration-related errors."""
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when configuration contains invalid values.
    
    Example:
        raise InvalidConfigError(
            "Invalid refresh interval",
            {"field": "refresh_interval", "value": -5, "reason": "Must be positive"}
        )
    """
    pass


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing.
    
    Example:
        raise MissingConfigError(
            "Required configuration missing",
            {"field": "api_key", "config_section": "weather"}
        )
    """
    pass


class ConfigFileNotFoundError(ConfigurationError):
    """Raised when configuration file cannot be found.
    
    Example:
        raise ConfigFileNotFoundError(
            "Configuration file not found",
            {"path": "/etc/weather/config.yaml", "search_paths": ["/etc", "/home/user"]}
        )
    """
    pass


# Hardware Exceptions
class HardwareError(WeatherDisplayError):
    """Base exception for hardware-related errors."""
    pass


class DisplayError(HardwareError):
    """Base exception for display-related errors."""
    pass


class DisplayInitializationError(DisplayError):
    """Raised when e-paper display initialization fails.
    
    Example:
        raise DisplayInitializationError(
            "Failed to initialize e-paper display",
            {"spi_device": "/dev/spidev0.0", "error": "Device not found"}
        )
    """
    pass


class ImageRenderingError(DisplayError):
    """Raised when image rendering fails.
    
    Example:
        raise ImageRenderingError(
            "Failed to render weather image",
            {"size": (1872, 1404), "format": "1bit", "error": "Insufficient memory"}
        )
    """
    pass


class PartialRefreshError(DisplayError):
    """Raised when partial refresh operation fails.
    
    Example:
        raise PartialRefreshError(
            "Partial refresh failed",
            {"changed_pixels": 5000, "threshold": 1000, "error": "Display busy"}
        )
    """
    pass


class DisplayUpdateError(DisplayError):
    """Raised when display update fails.
    
    Example:
        raise DisplayUpdateError(
            "Failed to update display",
            {"mode": "partial", "error": "SPI communication error"}
        )
    """
    pass


class PowerManagementError(HardwareError):
    """Base exception for power management errors."""
    pass


class PiJuiceInitializationError(PowerManagementError):
    """Raised when PiJuice hardware initialization fails.
    
    Example:
        raise PiJuiceInitializationError(
            "Failed to initialize PiJuice",
            {"i2c_address": 0x14, "bus": 1, "error": "Device not detected"}
        )
    """
    pass


class PiJuiceCommunicationError(PowerManagementError):
    """Raised when PiJuice I2C communication fails.
    
    Example:
        raise PiJuiceCommunicationError(
            "Failed to communicate with PiJuice",
            {"operation": "GetBatteryLevel", "error": "I2C timeout"}
        )
    """
    pass


class BatteryMonitoringError(PowerManagementError):
    """Raised when battery status cannot be read.
    
    Example:
        raise BatteryMonitoringError(
            "Failed to read battery status",
            {"source": "pijuice", "error": "Invalid response"}
        )
    """
    pass


class CriticalBatteryError(PowerManagementError):
    """Raised when battery level is critically low.
    
    Example:
        raise CriticalBatteryError(
            "Battery critically low - initiating shutdown",
            {"level": 5, "threshold": 10, "voltage": 3.2}
        )
    """
    pass


class PowerStateError(PowerManagementError):
    """Raised when invalid power state transition occurs.
    
    Example:
        raise PowerStateError(
            "Invalid power state transition",
            {"from_state": "ACTIVE", "to_state": "UNKNOWN", "battery_level": 50}
        )
    """
    pass


class WakeupSchedulingError(PowerManagementError):
    """Raised when wakeup scheduling fails.
    
    Example:
        raise WakeupSchedulingError(
            "Failed to schedule wakeup",
            {"target_time": "2025-05-12T10:00:00", "error": "RTC not available"}
        )
    """
    pass


# Network Exceptions
class NetworkError(WeatherDisplayError):
    """Base exception for network-related errors."""
    pass




class NetworkTimeoutError(NetworkError):
    """Raised when network operation times out.
    
    Example:
        raise NetworkTimeoutError(
            "Network operation timed out",
            {"operation": "weather_fetch", "timeout": 30, "url": "api.openweathermap.org"}
        )
    """
    pass


class NetworkUnavailableError(NetworkError):
    """Raised when no network connectivity is available.
    
    Example:
        raise NetworkUnavailableError(
            "No network connectivity",
            {"interfaces_checked": ["wlan0", "eth0"], "dns_test": "failed"}
        )
    """
    pass


# API Exceptions
class APIError(WeatherDisplayError):
    """Base exception for API-related errors."""
    
    def __init__(
        self, 
        message: str, 
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        response_body: str | None = None
    ) -> None:
        """Initialize API exception with additional context.
        
        Args:
            message: Human-readable error description
            details: Optional dictionary containing additional error context
            status_code: HTTP status code if applicable
            response_body: Raw response body for debugging
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body


class WeatherAPIError(APIError):
    """General weather API error.
    
    Example:
        raise WeatherAPIError(
            "Weather API request failed",
            {"endpoint": "/data/3.0/onecall", "method": "GET"},
            status_code=500,
            response_body="Internal Server Error"
        )
    """
    pass


class APIRateLimitError(APIError):
    """Raised when API rate limit is exceeded.
    
    Example:
        raise APIRateLimitError(
            "API rate limit exceeded",
            {"limit": 1000, "window": "daily", "retry_after": 3600},
            status_code=429
        )
    """
    pass


class APIAuthenticationError(APIError):
    """Raised when API authentication fails.
    
    Example:
        raise APIAuthenticationError(
            "Invalid API key",
            {"api_key_prefix": "abc123...", "endpoint": "/weather"},
            status_code=401
        )
    """
    pass


class APITimeoutError(APIError):
    """Raised when API request times out.
    
    Example:
        raise APITimeoutError(
            "API request timed out",
            {"endpoint": "/data/3.0/onecall", "timeout": 30, "attempt": 3}
        )
    """
    pass


class InvalidAPIResponseError(APIError):
    """Raised when API returns invalid or malformed response.
    
    Example:
        raise InvalidAPIResponseError(
            "Invalid API response format",
            {"expected_fields": ["temp", "humidity"], "received": ["temp"]},
            status_code=200,
            response_body='{"temp": 25}'
        )
    """
    pass


# Utility function for exception chaining
def chain_exception(new_exception: WeatherDisplayError, cause: Exception) -> WeatherDisplayError:
    """Chain a new exception with its underlying cause.
    
    This utility function ensures proper exception chaining for better
    debugging and error tracking.
    
    Args:
        new_exception: The new domain-specific exception to raise
        cause: The underlying exception that caused this error
        
    Returns:
        The new exception with cause properly chained
        
    Example:
        try:
            response = requests.get(url)
        except requests.RequestException as e:
            raise chain_exception(
                WeatherAPIError("Failed to fetch weather", {"url": url}),
                e
            )
    """
    new_exception.__cause__ = cause
    return new_exception