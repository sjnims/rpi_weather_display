# CLAUDE.md

This file provides guidance to Claude Code when working with this weather display project.

## 🔋 Three Golden Rules
1. **Client does NOTHING but fetch and display** - Server does all other work
2. **Every feature must pass the power checklist** - No exceptions
3. **94%+ test coverage** - Power optimization needs confidence

## Project Overview

A battery-optimized weather display using:
- **Client**: Raspberry Pi Zero 2 W + PiJuice Zero + Waveshare 10.3″ E-paper (1872x1404)
- **Server**: Docker container on Unraid server (i9-12900K, 32GB RAM)
- **Goal**: 60-90 days battery life on 12,000 mAh battery
- **Dev Machine**: macOS M2 MAX (all dependencies must be macOS-compatible)

## Quick Start

```bash
# Install
poetry install --with dev --extras server
poetry run playwright install  # For server rendering

# Run
poetry run server --config config.yaml
poetry run client --config config.yaml

# Test & Quality Checks (ALWAYS run before committing)
poetry run pytest
poetry run ruff check .
poetry run pyright .
```

## Common Pitfalls to Avoid
- **Never** add processing logic to the client - it kills battery life
- **Don't** use `typing.Any` - be specific with types
- **Don't** use `Union[X, Y]` - use `X | Y` syntax (Python 3.11+)
- **Avoid** synchronous HTTP calls on client - use httpx async
- **Never** leave WiFi on after operations on client - use context managers
- **Don't** forget to mock hardware for tests on macOS

## Quick Decision Guide

New feature? Ask yourself:
```
┌─ Requires computation? ──Yes──→ Server
│                          No
│                          ↓
├─ Needs network access? ──Yes──→ Server
│                          No
│                          ↓
├─ Updates frequently? ────Yes──→ Server (cache it)
│                          No
│                          ↓
└─ Display only? ─────────Yes──→ Client (maybe)
```

## Client Power Impact Examples
- WiFi on for 1 minute = ~3 hours of deep sleep
- One API call on client = ~10 display updates worth of power
- Parsing JSON on client = ~5x more power than displaying image
- Async I/O saves ~40% power vs synchronous during network ops

## Architecture & Power Optimization

### APIs Used
- [OpenWeatherMap One Call 3.0](https://openweathermap.org/api/one-call-3) - Main weather data
- [OpenWeatherMap Air Pollution](https://openweathermap.org/api/air-pollution) - Air quality data
- [OpenWeatherMap Geocoding](https://openweathermap.org/api/geocoding-api) - City name to lat/lon

### Client-Server Split
- **Server handles**: API calls, data processing, HTML rendering, image generation
- **Client handles**: Display updates only (fetches pre-rendered images)

### Power Checklist
Before implementing any client-side feature:
1. Is this operation necessary?
2. Can it be done on the server instead?
3. Can the result be cached?
4. Does it respect quiet hours?
5. Does it adapt to battery level?

Power optimizations in: `deploy/scripts/install.sh` & `deploy/scripts/optimize-power.sh`

### Key Files
**Server:**
- `src/rpi_weather_display/server/main.py` - FastAPI server
- `src/rpi_weather_display/server/api.py` - Weather API client
- `src/rpi_weather_display/server/renderer.py` - HTML/image rendering

**Client:**
- `src/rpi_weather_display/client/main.py` - Async client app
- `src/rpi_weather_display/client/display.py` - E-ink interface
- `src/rpi_weather_display/utils/network.py` - Async network with WiFi power control

### Async Architecture
Client uses async/await throughout for power efficiency:
- WiFi auto-disabled after use via context managers
- Non-blocking I/O prevents CPU busy-waiting
- Semaphore limits concurrent operations
- httpx.AsyncClient for async HTTP

## Testing Best Practices

### Performance Targets
- Client wake time: <5 seconds per update
- Server image generation: <2 seconds
- Memory usage on Pi: <50MB
- Network data per update: <100KB

### Testing Requirements
- Maintain 94%+ coverage
- Mock hardware for macOS compatibility
- Test fixtures in `tests/conftest.py`

### Coverage Reporting
When checking coverage for specific modules, use the import path (not file path):
```bash
# CORRECT - No warnings, accurate coverage for specific module
poetry run pytest tests/models/test_config.py --cov=rpi_weather_display.models.config --cov-report=term-missing:skip-covered

# Show only the specific module in the report (with grep)
poetry run pytest tests/models/test_config.py --cov=rpi_weather_display.models.config --cov-report=term-missing:skip-covered | grep -E "(models/config|Cover)"

# Disable fail_under for single module testing (won't fail at 94%)
poetry run pytest tests/models/test_config.py --cov=rpi_weather_display.models.config --cov-report=term-missing:skip-covered --cov-fail-under=0

# Quick coverage check for a specific module (alias-friendly)
poetry run pytest tests/models/test_config.py --cov=rpi_weather_display.models.config --cov-fail-under=0 -q | grep -A1 -B1 "models/config"

# WRONG - Shows misleading "module not imported" warning
poetry run pytest tests/models/test_config.py --cov=src/rpi_weather_display/models/config
```

### AsyncMock Warning Fix
```python
# WRONG - causes warning
mock_client.run = AsyncMock()
with patch("asyncio.run"):
    main()

# CORRECT - no warning
mock_client.run = Mock()  # Regular Mock when asyncio.run is mocked
```

### Type Stubs
When pyright complains about external libraries:
1. Create stubs in `stubs/<library>/`
2. Include `__init__.pyi` and `py.typed`
3. Match external API exactly (even non-PEP8 names)
4. Configure in pyproject.toml: `stubPath = "stubs"`

### Other Testing Notes
- **Think** before creating a new test file - is there an existing one that fits?
- **Think deeply** before changing implementation code to match a test's expectation:
  - Did we just change the implementation of a feature that might also require us to change its tests?
  - Just because we have an existing test, doesn't mean it's still the right test for the job.

## Configuration System

Hierarchical YAML with Pydantic validation:

```yaml
weather:
  api_key: "YOUR_OPENWEATHERMAP_API_KEY"
  city_name: "London"
  units: "metric"  # metric, imperial, standard

display:
  width: 1872
  height: 1404

power:
  quiet_hours_start: "23:00"
  quiet_hours_end: "06:00"
  battery_thresholds:  # Update frequency by battery %
    - {min: 80, update_interval: 900}    # 15 min
    - {min: 50, update_interval: 1800}   # 30 min
    - {min: 20, update_interval: 3600}   # 1 hour
    - {min: 0, update_interval: 7200}    # 2 hours

server:
  url: "http://your-server-ip"
  port: 8000

logging:
  level: "INFO"
  format: "json"  # json or text
```

Features:
- Multiple time/date formats
- Pressure units (hPa, mmHg, inHg)
- Battery-aware update intervals

## Important Patterns

### Network Operations
```python
async with network_manager.ensure_connectivity() as connected:
    if connected:
        await fetch_data()
# WiFi auto-disabled on exit
```

### Semaphore for Resource Limiting
```python
async with self._semaphore:
    response = await client.post(url, json=data)
```

## Modern Python (3.11.12)
- Use `str | None` instead of `Union[str, None]`
- Avoid `Any` - use specific types
- Use pathlib, f-strings, async/await
- Pydantic V2 for data models

## User Feedback & Display

### Battery Icons (in SVG sprite)
- `battery-charging-bold`
- `battery-empty-bold`
- `battery-full-bold`
- `battery-high-bold`
- `battery-low-bold`

### Display Format
- Show last update timestamp using configured format
- Server renders HTML with Jinja2, screenshots with Playwright
- Client displays pre-rendered image on e-paper

## Debugging Tips
- **Client not updating?** Check battery thresholds & quiet hours
- **Type errors?** Create stubs for external libs (see Type Stubs section)
- **Async warnings?** Use Mock instead of AsyncMock when mocking asyncio.run
- **Power drain?** Profile with: `poetry run python -m cProfile client.py`

## Error Handling & Updates

### Error Reporting
- Custom exception hierarchy in `exceptions.py`
- Network errors trigger exponential backoff
- Critical errors sent to server before shutdown
- Use lightweight formats (CSV/JSON) for power logs

### Update Mechanism
- SHA-256 checksum verification
- Atomic updates with rollback support
- Test in staging before production
- Keep backup for automatic reversion

## Development Mode
Set `development_mode: true` to:
- Disable deep sleep on the client
- Enable browser preview at :8000/preview
- Increase logging verbosity

## Hardware Abstraction
- Mock all hardware dependencies for macOS development
- PiJuice adapter pattern in `utils/pijuice_adapter.py`
- Type stubs in `stubs/pijuice/` for external libraries

## Chat Preferences
- Explain context for changes
- Use friendly tone