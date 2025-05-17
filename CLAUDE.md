# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Development Commands

### Setup and Installation

```bash
# Install Poetry dependency management
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies including development tools
poetry install --with dev --extras server

# Install server-only dependencies
poetry install --extras server

# Install Playwright browsers (required for rendering)
poetry run playwright install
```

### Running the Application

```bash
# Start the server with a config file
poetry run server --config config.yaml

# Start the client with a config file
poetry run client --config config.yaml

# Preview dashboard in browser (while server is running)
# http://localhost:8000/preview
```

### Testing

```bash
# Run all tests with coverage
poetry run pytest

# Run specific test files or directories
poetry run pytest tests/models/

# Run specific test with more verbosity
poetry run pytest tests/models/test_config.py -v

# Run tests with specific markers
poetry run pytest -m "not slow"
```

### Code Quality

```bash
# Run ruff linter
poetry run ruff check .

# Run type checking with pyright
poetry run pyright

# Run pre-commit checks
poetry run pre-commit run --all-files
```

## Project Architecture

The project uses a client-server architecture to maximize battery life on the Raspberry Pi:

### Server Component

The server side handles all computation-intensive tasks:
- Fetches weather data from OpenWeatherMap API
- Processes and formats weather information
- Renders HTML dashboard using Jinja2 templates
- Generates screen-ready images via Playwright
- Provides API endpoints via FastAPI
- Implements caching to reduce API calls

Key server files:
- `src/rpi_weather_display/server/main.py`: FastAPI server implementation
- `src/rpi_weather_display/server/api.py`: Weather API client
- `src/rpi_weather_display/server/renderer.py`: HTML and image rendering

### Client Component

The client focuses on energy efficiency:
- Wakes periodically from sleep mode
- Requests pre-rendered images from server
- Displays images on e-ink display
- Manages power-saving features
- Handles deep sleep and wake cycles
- Monitors battery status

Key client files:
- `src/rpi_weather_display/client/main.py`: Main client application
- `src/rpi_weather_display/client/display.py`: E-ink display interface

### Shared Components

- `src/rpi_weather_display/models/`: Pydantic data models (config, weather, system)
- `src/rpi_weather_display/utils/`: Shared utilities (battery, network, time, logging)

## Configuration System

The configuration system uses a hierarchical YAML-based approach with validation via Pydantic:

```yaml
weather:
  api_key: "YOUR_OPENWEATHERMAP_API_KEY"
  city_name: "London"
  units: "metric"
  # ...more weather options

display:
  width: 1872  # Display resolution width
  height: 1404 # Display resolution height
  # ...more display options

power:
  quiet_hours_start: "23:00"
  quiet_hours_end: "06:00"
  # ...more power options

server:
  url: "http://your-server-ip"
  port: 8000
  # ...more server options

logging:
  level: "INFO"
  format: "json"
  # ...more logging options

debug: false
development_mode: true
```

Key configuration features:
- Strong validation through Pydantic models
- Support for multiple time/date formats
- Customizable pressure units (hPa, mmHg, inHg)
- Quiet hours for battery conservation
- Battery threshold configuration
- Comprehensive logging options

## Testing Approach

The project maintains a high test coverage standard (94%+) using pytest:

1. **Model Testing**:
   - `tests/models/`: Tests for configuration, system status, and weather data models
   - Ensures validation logic works as expected
   - Tests edge cases and error conditions

2. **Client Testing**:
   - `tests/client/`: Tests for client-side functionality
   - Mock hardware interactions to avoid dependencies
   - Tests power management and display functions

3. **Server Testing**:
   - `tests/server/`: Tests for server API and rendering
   - Tests FastAPI endpoints with TestClient
   - Validates image generation and HTML rendering

4. **Utility Testing**:
   - `tests/utils/`: Tests for shared utility functions
   - Battery utils, logging, networking, power management
   - Time-related utilities

The test fixtures in `tests/conftest.py` provide:
- Mock subprocess execution
- Test configuration loading
- Mock battery status
- FastAPI test client
- Path handling utilities

## Debugging and Development

### Development Mode

When `development_mode: true` is set in configuration:
- Deep sleep is disabled for easier debugging
- More verbose logging is enabled
- Browser preview is available at http://localhost:8000/preview

### Common Issues

1. **API Key Issues**:
   - Check your OpenWeatherMap API key is valid
   - Verify you're not exceeding API call limits

2. **Display Issues**:
   - For e-ink display problems, check hardware connections
   - Validate display parameters match your hardware

3. **Server Connection**:
   - Ensure server URL and port are correct
   - Confirm network connectivity between client and server