# Ultra-Low-Power Weather Display

A power-optimized weather display solution for Raspberry Pi Zero 2 W with e-paper display, designed to achieve 60-90 days of battery life on a single charge.

## Features

- Ultra-low-power consumption (60-90 days battery life)
- Beautiful e-paper weather display with current conditions and forecast
- Server-client architecture for minimal client power usage
- Comprehensive power management with aggressive optimizations
- Quiet hours support to conserve battery during night time
- Weather data from OpenWeatherMap API
- Automatic deep sleep between updates
- Browser-based preview for easier development

## Hardware Requirements

- **Client**:
  - Raspberry Pi Zero 2 W
  - PiJuice Zero HAT
  - PiJuice 12,000 mAh LiPo battery
  - Waveshare 10.3″ 1872 x 1404 E-paper IT8951 HAT

- **Server**:
  - Docker container running on Unraid server (or any Linux server)
  - 12th Gen Intel® Core™ i9-12900K and 32GB RAM (recommended)

## Architecture

The project uses a client-server architecture to maximize battery life:

- **Server**: Handles all computation-intensive tasks including:
  - Weather API calls
  - Data processing
  - HTML rendering
  - Image generation

- **Client**: Focuses on power efficiency:
  - Wakes up periodically to request updates
  - Displays pre-rendered images
  - Manages power and sleep cycles
  - Implements aggressive power-saving measures

## Installation

### Client Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/sjnims/rpi-weather-display.git
   cd rpi-weather-display
   ```

2. Run the installation script (requires Raspberry Pi OS Bookworm):
   ```bash
   sudo bash deploy/scripts/install.sh
   ```

   This script will:
   - Install Python 3.11 and required dependencies
   - Set up the application with Poetry
   - Apply comprehensive power optimizations
   - Configure the system for maximum battery life
   - Create and enable systemd service

3. Create configuration file:
   ```bash
   sudo mkdir -p /etc/rpi-weather-display
   sudo cp config.example.yaml /etc/rpi-weather-display/config.yaml
   sudo nano /etc/rpi-weather-display/config.yaml  # Edit as needed
   ```

4. The system will automatically reboot after installation and start the service.

### Manual Power Optimization

If you want to apply power optimizations separately:

```bash
sudo bash deploy/scripts/optimize-power.sh
```

### Server Setup

1. Build Docker image:
   ```bash
   docker build -t weather-display-server .
   ```

2. Run Docker container:
   ```bash
   docker run -d \
     --name weather-display \
     -p 8000:8000 \
     -v /path/to/config.yaml:/etc/rpi-weather-display/config.yaml \
     weather-display-server
   ```

## Development

To set up the development environment on macOS:

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# For server components
poetry install --extras server

# Install Playwright browsers (required for rendering images)
poetry run playwright install

# Run tests
poetry run pytest

# Check code with ruff
poetry run ruff check .

# Check types with pyright
poetry run pyright
```

### Running the Application in Development Mode

1. Start the server with a local config file:
   ```bash
   poetry run server --config config.yaml
   ```

2. In a separate terminal, run the client with the same config file:
   ```bash
   poetry run client --config config.yaml
   ```

3. Preview the dashboard in your browser:
   ```
   http://localhost:8000/preview
   ```
   This provides a live view of the dashboard for easier development and iteration.

4. Modify the HTML template in `templates/weather.html.j2` and refresh the browser to see changes immediately.

## Configuration

Edit the `config.yaml` file to customize:

- OpenWeatherMap API key
- Location settings
- Display preferences
- Power management settings
- Server connection details
- Logging options

### Example Configuration

```yaml
weather:
  api_key: "your_openweathermap_api_key_here"
  city_name: "Atlanta"
  units: "metric"
  language: "en"
  update_interval_minutes: 30
  forecast_days: 5

display:
  width: 1872
  height: 1404
  rotate: 0
  refresh_interval_minutes: 30
  partial_refresh: true
  timestamp_format: "%Y-%m-%d %H:%M"

power:
  quiet_hours_start: "23:00"
  quiet_hours_end: "06:00"
  low_battery_threshold: 20
  critical_battery_threshold: 10
  wake_up_interval_minutes: 60
  wifi_timeout_seconds: 30
  disable_hdmi: true
  disable_bluetooth: true
  disable_leds: true
  enable_temp_fs: true
  cpu_governor: "powersave"
  cpu_max_freq_mhz: 700

server:
  url: "http://localhost"  # Use localhost for development, your server IP for production
  port: 8000
  timeout_seconds: 10
  retry_attempts: 3
  retry_delay_seconds: 5
  cache_dir: "/tmp/weather-cache"
  log_level: "INFO"
  image_format: "PNG"

logging:
  level: "INFO"
  format: "json"
  max_size_mb: 5
  backup_count: 3

debug: false
development_mode: true
```

## Power Optimization

The project implements numerous power-saving techniques to achieve 60-90 days of battery life:

- Offloading computation to the server
- CPU frequency limited to 700 MHz
- Power-efficient CPU governor
- HDMI, Bluetooth, and LEDs disabled
- Aggressive WiFi power management
- Deep sleep between refreshes
- Quiet hours during night time
- Adaptive refresh rates based on battery level
- Memory and filesystem optimizations

## Project Structure

```
rpi-weather-display/
├── pyproject.toml         # Project configuration and dependencies
├── config.example.yaml    # Example configuration file
├── src/
│   └── rpi_weather_display/
│       ├── client/        # Client code for Raspberry Pi
│       ├── server/        # Server code for Docker container
│       ├── models/        # Shared data models
│       └── utils/         # Utility functions
├── deploy/
│   └── scripts/
│       ├── install.sh         # Installation script
│       └── optimize-power.sh  # Power optimization script
├── templates/             # HTML templates for weather display
└── static/                # Static assets including icons and CSS
```

## API Endpoints

The server provides the following endpoints:

- `POST /render` - Used by the client to get a rendered image for e-paper display
- `GET /weather` - Returns weather data as JSON
- `GET /preview` - Renders the dashboard in a browser for development

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.