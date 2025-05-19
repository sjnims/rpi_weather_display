# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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