# Utility Modules

This directory contains utility modules for the Raspberry Pi weather display.

## Path Utilities (`path_utils.py`)

The `path_utils.py` module provides standardized path resolution across the codebase. It implements a `PathResolver` class that handles various path-related operations consistently:

- Finding configuration files
- Locating resource directories (templates, static files)
- Managing cache and temporary files
- Resolving executable paths

### Usage Examples

```python
from rpi_weather_display.utils import path_resolver

# Get path to configuration file
config_path = path_resolver.get_config_path()

# Get path to a resource directory
templates_dir = path_resolver.get_templates_dir()
static_dir = path_resolver.get_static_dir()

# Get path to a cache file
cache_file = path_resolver.get_cache_file("weather_data.json")

# Get a temporary file with a specific suffix
temp_file = path_resolver.get_temp_file(suffix=".png")

# Find a data file
data_file = path_resolver.get_data_file("owm_icon_map.csv")

# Ensure a directory exists
log_dir = path_resolver.ensure_dir_exists("/var/log/rpi-weather-display")

# Get path to a system binary
shutdown_path = path_resolver.get_bin_path("shutdown")
```

### Rationale

The path resolver was implemented to address several issues:

1. **Inconsistent path handling** - Different parts of the codebase were using different approaches (os.path vs pathlib.Path)
2. **Deep relative paths** - Complex chains like `Path(__file__).parent.parent.parent.parent` were used
3. **Hard-coded paths** - Several paths were hard-coded rather than discovered or configured
4. **No fallback strategy** - Missing resource directories could cause crashes rather than graceful fallbacks

### Design Principles

- Use `pathlib.Path` consistently for all path operations
- Support multiple search locations with fallbacks
- Provide a single global instance (`path_resolver`) for easy import
- Ensure directories exist when needed
- Normalize different path formats (str vs Path)

### Search Locations

The path resolver searches for files in the following locations (in order of priority):

1. **Current working directory** - For easy local development
2. **User config directory** - For user-specific configurations (`~/.config/rpi-weather-display/`)
3. **System config directory** - For system-wide configurations (`/etc/rpi-weather-display/`)
4. **Project root directory** - For running directly from the repository

## File Utilities (`file_utils.py`)

The `file_utils.py` module provides a consistent file system abstraction layer for the entire project. It standardizes file operations with proper error handling, path normalization, and type annotations.

### Key Features

- Consistent error handling across all file operations
- Path normalization using pathlib.Path objects
- Type annotations for better IDE support and type checking
- Atomic file operations where appropriate for data safety
- Support for both text and binary file operations
- Specialized utilities for JSON and YAML files

### Usage Examples

#### Reading Files

```python
from rpi_weather_display.utils.file_utils import read_text, read_bytes, read_json

# Read text content
content = read_text("config.yaml")  

# Read binary content
image_data = read_bytes("image.png")

# Read and parse JSON
config = read_json("config.json")
```

#### Writing Files

```python
from rpi_weather_display.utils.file_utils import write_text, write_bytes, write_json

# Write text content
write_text("output.txt", "Hello, world!")

# Write binary content
write_bytes("image.png", image_data)

# Write JSON data (with pretty formatting)
write_json("config.json", config_data, pretty=True)
```

#### File Operations

```python
from rpi_weather_display.utils.file_utils import (
    file_exists, 
    copy_file, 
    move_file, 
    delete_file,
    ensure_dir_exists
)

# Check if a file exists
if file_exists("data.csv"):
    # Process the file
    pass

# Copy a file
copy_file("source.txt", "destination.txt")

# Move/rename a file
move_file("old_name.txt", "new_name.txt")

# Delete a file
delete_file("temporary.txt")

# Ensure a directory exists (create if needed)
ensure_dir_exists("output/logs")
```

#### Directory Operations

```python
from rpi_weather_display.utils.file_utils import (
    ensure_dir_exists,
    delete_dir,
    list_files
)

# Create directory if it doesn't exist
ensure_dir_exists("data/cache")

# List files in a directory (optional pattern matching)
json_files = list_files("config", "*.json")

# Delete a directory and its contents
delete_dir("temp", recursive=True)
```

### Error Handling

All functions in `file_utils.py` use consistent error handling:

- `FileNotFoundError`: When a file doesn't exist
- `PermissionError`: When permissions are insufficient
- `IsADirectoryError`/`NotADirectoryError`: When the wrong type is provided
- `OSError`: For general file system errors
- `ValueError`/`TypeError`: For invalid arguments

### Testing

When testing code that uses `file_utils.py`, you can mock the functions to avoid actual file system operations:

```python
def test_function_using_file_utils(mocker):
    # Mock file_exists to return True
    mocker.patch("rpi_weather_display.utils.file_utils.file_exists", return_value=True)
    
    # Mock read_text to return specific content
    mocker.patch("rpi_weather_display.utils.file_utils.read_text", return_value="test content")
    
    # Test your function that uses file_utils
    result = function_to_test()
    assert result == expected_result
```

## Other Utilities

- **Battery Utilities** (`battery_utils.py`) - Functions for battery state management
- **Power Manager** (`power_manager.py`) - Power state management and optimization
- **Time Utilities** (`time_utils.py`) - Functions for time and date handling
- **Error Utilities** (`error_utils.py`) - Error handling and reporting
- **Logging** (`logging.py`) - Structured logging configuration
- **Network** (`network.py`) - Network connectivity and configuration