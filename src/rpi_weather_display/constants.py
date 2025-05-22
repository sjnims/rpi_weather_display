"""Application-wide constants for the Raspberry Pi weather display.

This module centralizes all constants used throughout the application to
ensure consistency and maintainability. Constants are organized into logical
categories for easier reference and documentation.

Constants are grouped into the following categories:
- Path Constants: Filepaths for system utilities and scripts
- Network Constants: Network configuration and connection defaults
- OpenWeatherMap API: API endpoints for weather data
- Battery Constants: Battery thresholds and calculation factors
- Power Management Constants: Sleep factors and power optimization values
- Display Constants: Visual formatting and layout values
- Time Constants: Time-related values for scheduling and timeouts
- Unit Conversion Constants: Factors for converting between measurement units
- Cache Constants: Filenames and settings for caching mechanisms
- Preview Constants: Default values used in preview/development mode
"""

# Path constants
# Script for enabling WiFi power save, kept as a constant since it's a custom script
WIFI_SLEEP_SCRIPT = "/usr/local/bin/wifi-sleep.sh"

# Client/configuration constants
CLIENT_CACHE_DIR_NAME = "rpi-weather-display"  # Directory name for client cache
DEFAULT_CONFIG_PATH = f"/etc/{CLIENT_CACHE_DIR_NAME}/config.yaml"  # Default config location

# Network constants
GOOGLE_DNS = "8.8.8.8"  # Google DNS server for connectivity tests
GOOGLE_DNS_PORT = 53  # DNS port for connectivity tests
BROADCAST_IP = "10.255.255.255"  # Broadcast IP for network discovery
BROADCAST_PORT = 1  # Port for network discovery
API_LOCATION_LIMIT = 1  # Limit parameter for geocoding API results
DEFAULT_SERVER_HOST = "127.0.0.1"  # Default host for server

# OpenWeatherMap API URLs
OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"  # One Call API endpoint
OWM_AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"  # Air pollution API
OWM_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"  # Geocoding API

# Battery calculation constants
DRAIN_WEIGHT_PREV = 0.9  # Weight for previous drain rate in moving average calculation
DRAIN_WEIGHT_NEW = 0.1  # Weight for new drain rate in moving average calculation
DEFAULT_DRAIN_RATE = 1.0  # Initial drain rate estimate (% per hour)
BATTERY_FULL_THRESHOLD = 90  # Percentage considered "full" for battery status
BATTERY_HIGH_THRESHOLD = 60  # Percentage considered "high" for battery status
BATTERY_LOW_THRESHOLD = 30  # Percentage considered "low" for battery status
BATTERY_EMPTY_THRESHOLD = 10  # Percentage considered "empty" for battery status
BATTERY_CHARGING_FACTOR = 0.8  # Factor for reducing sleep time while charging
BATTERY_CHARGING_MIN = 30  # Minimum minutes for charging sleep duration
BATTERY_HISTORY_SIZE = 24  # Max number of battery readings to keep in history
ABNORMAL_DISCHARGE_FACTOR = 1.5  # Factor to detect abnormal battery discharge rate

# Power management constants
CRITICAL_SLEEP_FACTOR = 8.0  # Factor to extend sleep for critical battery level
CONSERVING_MIN_FACTOR = 3.0  # Minimum factor for battery conservation mode
CONSERVING_MAX_FACTOR = 6.0  # Maximum factor for battery conservation mode
ABNORMAL_SLEEP_FACTOR = 1.5  # Factor to extend sleep when abnormal discharge detected
MAX_BATTERY_PERCENTAGE_SLEEP = 0.25  # Maximum percent of remaining battery for sleep calculation
MIN_SLEEP_MINUTES = 30  # Minimum sleep time in minutes
MAX_SLEEP_MINUTES = 24 * 60  # Maximum sleep time in minutes (24 hours)

# Display constants
DISPLAY_MARGIN = 5  # Pixel margin for image display
TITLE_FONT_SIZE_BASE = 36  # Base font size for title text
TITLE_FONT_SIZE_MAX = 48  # Maximum font size for title text
MESSAGE_FONT_SIZE_BASE = 24  # Base font size for message text
MESSAGE_FONT_SIZE_MAX = 36  # Maximum font size for message text
DEFAULT_TITLE_FONT = "DejaVuSans-Bold.ttf"  # Default font for title text
DEFAULT_MESSAGE_FONT = "DejaVuSans.ttf"  # Default font for message text
TITLE_Y_POSITION_FACTOR = 3  # Screen height divided by this for title Y position
MESSAGE_Y_POSITION_FACTOR = 2  # Screen height divided by this for message Y position
FONT_SIZE_DIVIDER = 20  # Screen width divided by this for font size calculation
FONT_SIZE_MESSAGE_DIVIDER = 30  # Screen width divided by this for message font size

# Time constants
SLEEP_BEFORE_SHUTDOWN = 5  # Seconds to sleep before shutdown
TWELVE_HOURS_IN_MINUTES = 12 * 60  # 12 hours in minutes, used for wakeup scheduling
TEN_MINUTES = 10 * 60  # Ten minutes in seconds, threshold for deep sleep

# Unit conversion constants
HPA_TO_MMHG = 0.75006  # Conversion factor from hectopascals to millimeters of mercury
HPA_TO_INHG = 0.02953  # Conversion factor from hectopascals to inches of mercury

# Cache file constants
UVI_CACHE_FILENAME = "uvi_max_cache.json"  # Filename for UV index cache

# Preview default values
PREVIEW_BATTERY_LEVEL = 85  # Default battery level percentage for preview mode
PREVIEW_BATTERY_VOLTAGE = 3.9  # Default battery voltage (V) for preview mode
PREVIEW_BATTERY_CURRENT = 0.5  # Default battery current (A) for preview mode
PREVIEW_BATTERY_TEMP = 25.0  # Default battery temperature (°C) for preview mode
