# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Server-side browser manager for efficient Playwright usage
- Memory-aware caching system with size limits for API responses
- Memory profiler for tracking and debugging memory usage
- File cache system for server-side caching (not yet fully utilized)

### Changed
- Improved deployment scripts with better error handling and security
- Enhanced shell script safety with proper quoting and error handling
- Added checksum verification for downloaded content in installation scripts

## [0.3.0] - 2025-05-24

### Added
- Full async/await architecture for client-side operations
- AsyncNetworkManager with automatic WiFi power management
- Semaphore-based concurrency limiting to prevent resource exhaustion
- Memory profiling and reporting endpoints
- Browser-based singleton for Playwright to reduce memory usage
- Exception chaining throughout error handling
- Structural pattern matching for state handling (Python 3.10+)
- Centralized constants module for all default values
- Standardized path resolution across client and server
- Consistent file system abstraction project-wide

### Changed
- Migrated from `requests` to `httpx` for async HTTP operations
- Replaced generic `Any` types with specific type annotations
- Improved type safety with TypedDict for test data structures
- Enhanced test suite with explicit Pydantic validation testing
- CPU now sleeps during network I/O instead of busy-waiting
- WiFi automatically disabled after network operations to save power

### UI Enhancements
- Wind direction shown as cardinal points (N, NE, E, etc.) with correctly oriented icons
- Wind direction indicators now properly point to the direction wind is coming from
- Air quality index display with descriptive labels based on OpenWeatherMap data
- Configurable pressure units (hPa, mmHg, inHg) through the config file
- Customizable datetime formats for display elements
- Support for multiple time format options (AM/PM or 24-hour)
- More accurate high UV time prediction that persists between updates
- Improved weather icon mapping for precise conditions visualization

## [0.2.0] - 2025-05-19

### Added
- Quiet hours display sleep mode for e-paper display controller
- Variable refresh rates based on battery state
- Configurable image difference threshold that adapts to battery level
- Dynamic wakeup scheduling based on battery levels
- Safe shutdown hooks for critical battery events
- Support for PiJuice events (LOW_CHARGE, button press)
- Battery-level-aware WiFi power state transitions
- Exponential backoff for network retry attempts
- Unified power state management interface
- Centralized battery threshold logic
- Common utility functions for power management

### Changed
- Refactored power management code into a unified PowerStateManager
- Improved battery status handling and state transitions
- Enhanced display refresh logic to save power during quiet hours
- Optimized WiFi power usage based on battery state

### Fixed
- Display refresh issues with partial updates
- Battery status detection and reporting
- WiFi connection retry logic

## [0.1.0] - 2025-05-15

### Added
- Initial implementation of weather display client and server
- E-paper display support for Waveshare 10.3" IT8951 HAT
- Weather data fetching from OpenWeatherMap API
- Basic power management
- Configuration system with Pydantic models
- Quiet hours scheduling
- E-ink display refresh optimization