# Google-Style Docstring Examples

This document provides examples of proper Google-style docstrings to be used throughout the Raspberry Pi Weather Display project.

## Module Level Docstring

```python
"""Module description and purpose.

This module provides functionality for [describe what the module does].
It contains classes and functions for [main capabilities].

Typical usage example:
  foo = SampleClass()
  bar = foo.sample_method()
"""
```

## Function Docstring

```python
def function_with_types_in_docstring(param1: int, param2: str) -> bool:
    """Function description.

    Additional details about the function, its behavior,
    and any special considerations.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: If param1 is less than 0.
        TypeError: If param2 is not a string.
    """
```

## Class Docstring

```python
class SampleClass:
    """Summary of class purpose and behavior.

    This class provides functionality to [describe primary purpose].
    It is used for [main use cases].

    Attributes:
        attr1: Description of attr1.
        attr2: Description of attr2.
    """

    def __init__(self, param1: str, param2: int = 42):
        """Initialize the SampleClass.

        Args:
            param1: Description of param1.
            param2: Description of param2. Defaults to 42.
        """
        self.attr1 = param1
        self.attr2 = param2
```

## Property Method Docstring

```python
@property
def prop_name(self) -> str:
    """Get the property value.

    Additional description of what this property represents and how it's used.

    Returns:
        Description of return value.
    """
```

## Static Method Docstring

```python
@staticmethod
def static_method(param1: int) -> list:
    """Description of the method.

    Args:
        param1: Description of param1.

    Returns:
        Description of return value.
    """
```

## Class Method Docstring

```python
@classmethod
def from_something(cls, something: str) -> "ClassName":
    """Create a new instance from something.

    Args:
        something: Description of something.

    Returns:
        A new instance of ClassName.
    """
```

## Field Validator Docstring

```python
@field_validator("field_name")
@classmethod
def validate_field_name(cls, v: str) -> str:
    """Validate the field_name.

    Args:
        v: The value to validate.

    Returns:
        The validated value.

    Raises:
        ValueError: If the value is invalid.
    """
```

## Exception Class Docstring

```python
class CustomException(Exception):
    """Exception raised for specific error condition.

    This exception is raised when [describe conditions].

    Attributes:
        message: Explanation of the error.
        code: Error code.
    """

    def __init__(self, message: str, code: int = 400):
        """Initialize CustomException.

        Args:
            message: Explanation of the error.
            code: Error code. Defaults to 400.
        """
        self.message = message
        self.code = code
        super().__init__(self.message)
```

## Constants Module Docstring

```python
"""Application-wide constants for the Raspberry Pi weather display.

This module centralizes all constants used throughout the application to
ensure consistency and maintainability. Constants are organized into logical
categories for easier reference.

Constants are grouped into the following categories:
- Path Constants: Filepaths for system utilities and scripts
- Network Constants: Network configuration and defaults
- Battery Constants: Battery thresholds and indicators
- Power Management Constants: Sleep factors and timings
- Unit Conversion Constants: Factors for unit conversions
- Cache Constants: Cache-related filenames and paths
- Preview Constants: Default values for preview mode
"""
```

## Constants Documentation

```python
# Path constants
SUDO_PATH = "/usr/bin/sudo"  # Path to sudo command
IWCONFIG_PATH = "/sbin/iwconfig"  # Path to iwconfig utility
```

## Real Project Examples

### From time_utils.py
```python
def is_quiet_hours(quiet_hours_start: str, quiet_hours_end: str) -> bool:
    """Check if current time is within quiet hours.

    Args:
        quiet_hours_start: Quiet hours start time in format "HH:MM".
        quiet_hours_end: Quiet hours end time in format "HH:MM".

    Returns:
        True if current time is within quiet hours, False otherwise.
    """
```

### From config.py
```python
class LoggingConfig(BaseModel):
    """Logging configuration.
    
    Defines settings for the application's logging system including
    log level, file path, format, and rotation options.
    
    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file: Optional path to log file. If None, logs to console only.
        format: Log format style ("json" or "text")
        max_size_mb: Maximum log file size in megabytes before rotation
        backup_count: Number of backup log files to keep
    """
```