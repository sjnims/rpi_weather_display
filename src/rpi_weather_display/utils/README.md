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

## Other Utilities

- **Battery Utilities** (`battery_utils.py`) - Functions for battery state management
- **Power Manager** (`power_manager.py`) - Power state management and optimization
- **Time Utilities** (`time_utils.py`) - Functions for time and date handling
- **Error Utilities** (`error_utils.py`) - Error handling and reporting
- **Logging** (`logging.py`) - Structured logging configuration
- **Network** (`network.py`) - Network connectivity and configuration