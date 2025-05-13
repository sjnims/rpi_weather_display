# Ultra-Low-Power Weather Display Project

## Hardware

- Raspberry Pi Zero 2 W
- PiJuice Zero
- PiJuice 12,000 mAh LiPo battery
- Waveshare 10.3″ 1872 x 1404 IT8951 HAT (SKU 18434)
- Unraid 7.1.2 server with 12th Gen Intel® Core™ i9-12900K and 32GB RAM
- Docker container running on Unraid server

## Hardware Setup

- Client: Raspberry Pi Zero 2 W with PiJuice Zero and Waveshare 10.3″ E-paper display
- Server: Docker container running on Unraid server

## Development Hardware

- Macbook Pro with M2 MAX chip from 2023
  - Any development dependecies should be compatible with macOS
  - Where there are hardware dependencies, they should be implemented, but in a way that they can be mocked out for testing

## API

- (Open Weather Map One Call 3.0 API)[https://openweathermap.org/api/one-call-3] for the majority of the data
- (Open Weather Map Air Pollution API concept)[https://openweathermap.org/api/air-pollution] for air quality data
- (Open Weather Map Geocoding API)[https://openweathermap.org/api/geocoding-api] for reverse lat & lon lookup based on city name if lat & lon are not provided

## Architectural Principles

- Server handles all computation (rendering, API calls).
- Client only displays pre-rendered images it fetches from the server.
- Client power optimization is the highest priority.
- Client network calls must be minimized.
- Client should sleep when not in use.

## Goal Battery Life

- 60-90 days on a single charge.

## Power Optimization Checklist

- Is this operation necessary?
- Can it be done on the server instead?
- Can the result be cached?
- Does it respect quiet hours?
- Does it adapt to battery level?
- Power saving tweaks saved in `deploy/scripts/install.sh`, but open to more suggestions.

## Naming conventions

- Use descriptive names for variables, functions, and classes.
- Follow a consistent naming scheme (e.g., camelCase, snake_case).
  - Use snake_case for variable and function names.
  - Use CamelCase for class names.

## Code structure

- Organize code into modules and packages.
- Keep related code together and separate unrelated code.
- Include type hints for function parameters and return types.
- Use `__init__.py` files to mark directories as packages.
- Follow DRY (Don't Repeat Yourself) principles.
- Avoid over-abstracting code; keep it simple and readable.
- Follow object-oriented principles where possible.

## Documentation

- Write clear and concise comments.
- Use docstrings for all public modules, functions, methods, and classes.
- Follow the Google style guide for Python docstrings.

## Testing

- Write unit tests for all new code.
- Use a testing framework (using pytest) for running tests.
- Write integration tests to validate interactions between the client and server.
- Use tools like `pytest` and `pytest-docker` for testing Dockerized components.
- Include end-to-end tests to simulate real-world usage scenarios.

## Style

- Follow PEP 8 style guide for Python code.
- Use linters (ruff and pyright) to enforce coding standards.
- Adhere to pyright's strict mode for type checking.

## Dependency Management

- Use Poetry for managing dependencies.
- Keep dependencies up to date.
- Use virtual environments to isolate project dependencies.
- Use `pyproject.toml` for managing production and development dependencies.

## Project structure

- Follow the src-layout pattern (src/package_name/) for better packaging, e.g. `src/rpi-weather-display/`
  - Use `src/rpi_weather_display/client/` for client code.
  - Use `src/rpi_weather_display/server/` for server code.
  - Use `src/rpi_weather_display/utils/` for shared code between client and server.
  - Use `src/rpi_weather_display/models/` for data models.
- Use `tests/` directory for unit tests.
- Use `pyproject.toml` for configuration (PEP 621)
- Include standard files (README.md, CHANGELOG.md, LICENSE)
- Scripts to use will be located in `deploy/scripts/` directory and are already present in the repository.
- An empty `rpi-weather-display.service` file will be provided for the client to run on boot.
- All icons will be provided by a single SVG sprite file located at `static/icons/sprite.svg`
  - The icons will be used in the e-paper display and will be referenced by their ID (e.g., `#battery-charging-bold`).
  - Scripts will be provided to generate the sprite file from individual SVG files.
  - A mapping of the icon IDs to their corresponding SVG files will be provided in a separate file (e.g., `owm_icon_map.csv`).

## Modern Python Features

- Use Python 3.11.12
- Use f-strings for string formatting instead of .format() or %
- Leverage dataclasses or Pydantic V2 models for data containers
- Use pathlib instead of os.path for file operations
- Consider async/await for I/O-bound operations
- Use walrus operator (:=) where appropriate (Python 3.8+)
- Implement structural pattern matching for Python 3.10+

## Error Handling

- Use context managers (with statements) for resource management
- Create custom exception hierarchies for your application
- Use exception chaining with "raise Exception() from original_exception"

## Application Configuration

- Use configuration files with config.yaml as the standard format
  - Use YAML for configuration files
  - Use a separate config.yaml file for each environment (development, production)
  - Use config.example.yaml as the template with default values
  - Consider Pydantic Settings for config validation
  - Implement a hierarchical configuration system
- Use Jinja2 for templating
- Unless necessary, avoid using full web frameworks (Flask, Django) for the server
  - Use FastAPI for the server if a web framework is needed
- Development preview should be available to run from the development machine on the command line (macOS, zsh)

## Code Quality Tools

- Use pre-commit hooks for automated checks
- Consider property-based testing with hypothesis
- Add Pyright for static type checking
- Use built-in types and avoid third-party libraries for basic types
- Use ruff for linting and code formatting
- Use pytest for testing
- Use pytest-cov for test coverage
- Use pytest-mock for mocking in tests
- Use pytest-asyncio for testing async code
- Use pytest-benchmark for performance testing
- Use pytest-xdist for parallel test execution
- Use pytest-html for generating HTML test reports
- Do not use mypy

## Logging

- Use the built-in logging module with appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- Configure structured logging for production environments.
  - Use JSON format for logs to enable easy parsing and analysis.
  - Consider using `structlog` for structured logging in Python.
    - Example configuration:
      ```python
      import structlog

      structlog.configure(
          processors=[
              structlog.processors.TimeStamper(fmt="iso"),
              structlog.processors.JSONRenderer(),
          ]
      )
      logger = structlog.get_logger()
      logger.info("Application started", module="main", level="INFO")
      ```
- Include contextual information in logs (e.g., timestamp, module name, log level).
- Ensure logs are rotated and archived to prevent excessive storage usage.
  - Use `logging.handlers.RotatingFileHandler` for log rotation.

## Version Control Practices

- Use descriptive commit messages following conventional commits format (type: description)
- Create feature branches for new work and use pull requests for review
- Keep commits focused on single logical changes
- Consider using git hooks to enforce coding standards
- Tag releases in Git using semantic versioning (e.g., `v1.0.0`).

## Security Practices

- Store API keys and secrets in config.yaml (ensure it's added to .gitignore)
- For local development, copy config.example.yaml to config.yaml and add your API keys
- Implement rate limiting for API requests to avoid quota issues
- Regularly update dependencies to patch security vulnerabilities

## CI/CD Pipeline

- Use GitHub Actions for continuous integration.
- Automate testing, linting, and type checking.
- Implement automated deployment to the Docker container.
  - Use Docker image tags to version releases (e.g., `weather-display:v1.0.0`).
  - Deploy updates using rolling updates to minimize downtime.
  - Example GitHub Actions workflow for deployment:
    ```yaml
    name: Deploy to Docker
    on:
      push:
        branches:
          - main
    jobs:
      deploy:
        runs-on: ubuntu-latest
        steps:
          - name: Check out code
            uses: actions/checkout@v3
          - name: Build Docker image
            run: docker build -t weather-display:${{ github.sha }} .
          - name: Push Docker image
            run: docker push weather-display:${{ github.sha }}
    ```
- Add status badges to `README.md` to indicate build and test status.
- Include a staging environment for testing updates before production deployment.
  - Use a separate Docker container or Raspberry Pi device for staging.

## Performance Considerations

- Cache API responses appropriately to reduce network requests.
- Use profiling tools to identify and optimize bottlenecks.
  - Use `cProfile` for CPU profiling.
  - Use `memory_profiler` for memory usage analysis.
  - Use `line_profiler` for line-by-line performance analysis.
- Consider memory usage limits on the Raspberry Pi.
  - Use `ulimit` to set memory constraints during testing.
- Implement graceful degradation when resources are constrained.
  - Example: Reduce display refresh rate when battery is low.

## Hardware Abstraction

- Abstract hardware interfaces (e.g., display, battery, sensors) behind well-documented classes or modules.
- Ensure hardware-specific code is isolated to facilitate future hardware swaps or upgrades.

## Power Profiling

- Use power profiling tools to measure and log power consumption during development and testing.
  - Software: PiJuice CLI tools for battery status and power metrics.
  - Use `powertop` for identifying power-hungry processes during development.
- Regularly review power metrics to validate optimizations and ensure battery life targets are met.
- Log power consumption metrics to the server when possible for remote diagnostics.
  - Use lightweight formats (e.g., CSV or JSON) for power logs.
  - Example CSV format:
    ```
    timestamp,battery_level,current_draw,voltage
    2025-05-12T10:00:00Z,85,120mA,3.7V
    ```
- Log power consumption metrics to the server when possible for remote diagnostics.

## Error Reporting

- Implement robust error logging and reporting, especially for critical failures.
- Send error logs to the server before shutdown or on unrecoverable errors, when network is available.
  - Use lightweight protocols like MQTT or HTTP POST for transmitting logs.
  - Ensure logs are encrypted during transmission to protect sensitive data.
- Store logs on the server in a structured format (e.g., JSON) for easy analysis.
- Ensure logs are concise to minimize network usage and power consumption.
- Implement log rotation to avoid excessive storage usage on the server.

## Update Mechanism

- Design a secure, atomic update mechanism for the client software.
  - Use checksum verification (e.g., SHA-256) to validate update integrity before applying.
  - Store updates in a temporary location and validate them before replacing the current version.
- Support rollback to a previous version in case of update failure.
  - Keep a backup of the previous version and configuration files.
  - Automatically revert to the backup if the update fails to initialize properly.
  - Example rollback logic:
    ```python
    import shutil

    def rollback_update():
        shutil.copy("backup/version", "current/version")
        print("Rollback to previous version completed.")
    ```
- Validate updates before applying to prevent bricking the device.
  - Test updates in a staging environment before deploying to production devices.
  - Use a "canary deployment" strategy for gradual rollouts.

## User Feedback

- If user interaction is supported, provide minimal, power-efficient feedback (e.g., simple display messages or icons).
- Avoid unnecessary display refreshes or animations to conserve power.
- Clearly indicate device status (e.g., low battery, error state) using the e-paper display.
  - Icon files will be provided for the battery within the SVG sprite for the following states:
    - Battery charging: `battery-charging-bold`
    - Battery empty: `battery-empty-bold`
    - Battery full: `battery-full-bold`
    - Battery high: `battery-high-bold`
    - Battery low: `battery-low-bold`
  - Display a timestamp of the last successful update in the format `YYYY-MM-DD HH:MM` or whichever timestamp format is defined in the user config.yaml file.
    - Example:
      ```
      Last Update: 2025-05-12 10:00
      ```
  - Use a library like `Jinja2` to render text and icons to html on the server, screenshot the resulting generated dashboard, and then display it on the e-paper display.

## Chat Preferences

- Always provide the path of the file being modified
- Use a concise and clear style
- I prefer a more friendly tone
- I prefer to know which files are being modified
- I like to know the context behind any changes and suggestions

## Code Review

- Provide constructive feedback
- Focus on code quality, readability, and maintainability
- Suggest improvements and alternatives