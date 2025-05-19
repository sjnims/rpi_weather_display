"""Constants module for the Raspberry Pi weather display.

Contains centralized definitions for hardcoded constants used across the application,
making them easier to maintain and update. This includes system paths,
network parameters, calculation values, and other fixed values that aren't
part of the user configuration.
"""

# Path constants
SUDO_PATH = "/usr/bin/sudo"
SHUTDOWN_PATH = "/sbin/shutdown"
TOP_PATH = "/usr/bin/top"
DF_PATH = "/bin/df"
IWGETID_PATH = "/sbin/iwgetid"
IWCONFIG_PATH = "/sbin/iwconfig"
IFCONFIG_PATH = "/sbin/ifconfig"
# Client cache directory name
CLIENT_CACHE_DIR_NAME = "rpi-weather-display"  # Directory name for client cache
DEFAULT_CONFIG_PATH = f"/etc/{CLIENT_CACHE_DIR_NAME}/config.yaml"
WIFI_SLEEP_SCRIPT = "/usr/local/bin/wifi-sleep.sh"
IW_PATH = "/sbin/iw"

# Network constants
GOOGLE_DNS = "8.8.8.8"
GOOGLE_DNS_PORT = 53
BROADCAST_IP = "10.255.255.255"
BROADCAST_PORT = 1
API_LOCATION_LIMIT = 1  # Limit parameter for geocoding API
DEFAULT_SERVER_HOST = "127.0.0.1"  # Default host for server

# OpenWeatherMap API URLs
OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
OWM_AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
OWM_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"

# Battery calculation constants
DRAIN_WEIGHT_PREV = 0.9  # Weight for previous drain rate in moving average
DRAIN_WEIGHT_NEW = 0.1  # Weight for new drain rate in moving average
DEFAULT_DRAIN_RATE = 1.0  # Initial drain rate estimate (% per hour)
BATTERY_FULL_THRESHOLD = 90  # Percentage considered "full"
BATTERY_HIGH_THRESHOLD = 60  # Percentage considered "high"
BATTERY_LOW_THRESHOLD = 30  # Percentage considered "low"
BATTERY_EMPTY_THRESHOLD = 10  # Percentage considered "empty"
BATTERY_CHARGING_FACTOR = 0.8  # Factor for charging wakeup time
BATTERY_CHARGING_MIN = 30  # Minimum minutes for charging sleep
BATTERY_HISTORY_SIZE = 24  # Max number of battery readings to keep in history
ABNORMAL_DISCHARGE_FACTOR = 1.5  # Factor for abnormal discharge detection

# Power management constants
CRITICAL_SLEEP_FACTOR = 8.0  # Factor to extend sleep for critical battery
CONSERVING_MIN_FACTOR = 3.0  # Minimum factor for battery conservation mode
CONSERVING_MAX_FACTOR = 6.0  # Maximum factor for battery conservation mode
ABNORMAL_SLEEP_FACTOR = 1.5  # Factor to extend sleep when abnormal discharge detected
MAX_BATTERY_PERCENTAGE_SLEEP = 0.25  # Maximum percent of remaining battery for sleep calc
MIN_SLEEP_MINUTES = 30  # Minimum sleep time in minutes
MAX_SLEEP_MINUTES = 24 * 60  # Maximum sleep time in minutes (24 hours)

# Display constants
DISPLAY_MARGIN = 5  # Pixel margin for image display
TITLE_FONT_SIZE_BASE = 36  # Base font size for title
TITLE_FONT_SIZE_MAX = 48  # Maximum font size for title
MESSAGE_FONT_SIZE_BASE = 24  # Base font size for message text
MESSAGE_FONT_SIZE_MAX = 36  # Maximum font size for message text
DEFAULT_TITLE_FONT = "DejaVuSans-Bold.ttf"
DEFAULT_MESSAGE_FONT = "DejaVuSans.ttf"
TITLE_Y_POSITION_FACTOR = 3  # Screen height divided by this for title Y position
MESSAGE_Y_POSITION_FACTOR = 2  # Screen height divided by this for message Y position
FONT_SIZE_DIVIDER = 20  # Screen width divided by this for font size calculation
FONT_SIZE_MESSAGE_DIVIDER = 30  # Screen width divided by this for message font size

# Time constants
SLEEP_BEFORE_SHUTDOWN = 5  # Seconds to sleep before shutdown
TWELVE_HOURS_IN_MINUTES = 12 * 60  # Used for wakeup scheduling
TEN_MINUTES = 10 * 60  # Threshold for deep sleep in seconds

# Unit conversion constants
HPA_TO_MMHG = 0.75006  # Conversion factor from hectopascals to mmHg
HPA_TO_INHG = 0.02953  # Conversion factor from hectopascals to inHg

# Cache file constants
UVI_CACHE_FILENAME = "uvi_max_cache.json"  # Filename for UVI cache

# Preview default values
PREVIEW_BATTERY_LEVEL = 85  # Default battery level for preview
PREVIEW_BATTERY_VOLTAGE = 3.9  # Default battery voltage for preview
PREVIEW_BATTERY_CURRENT = 0.5  # Default battery current for preview
PREVIEW_BATTERY_TEMP = 25.0  # Default battery temperature for preview