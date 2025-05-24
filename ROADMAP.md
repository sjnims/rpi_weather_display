# Roadmap for Ultra-Low-Power Weather Display

This roadmap outlines the planned development phases for the Ultra-Low-Power Weather Display project. Each phase focuses on specific improvements to enhance power efficiency, code quality, and user experience.

## Progress Tracking

Tasks are marked with checkboxes and status indicators:
- [ ] Task not started yet [PLANNED]
- [x] Task completed [COMPLETED]
- [-] Task in progress [IN PROGRESS]

Priority is indicated as:
- 🔴 High - Critical for core functionality or significant improvement
- 🟠 Medium - Important but not blocking
- 🟢 Low - Nice to have

## Phase 1: Power Optimization Integration (Target: v0.2.0) ✅ COMPLETED

### 1.1 Extract Duplicate Code
- [x] 🔴 1.1.1 Move `is_quiet_hours()` to a common utility function [COMPLETED 2025-05-15]
- [x] 🔴 1.1.2 Centralize battery threshold logic into a shared utility [COMPLETED 2025-05-15]
- [x] 🟠 1.1.3 Create unified power state management interface [COMPLETED 2025-05-15]

### 1.2 WiFi Management Enhancement
- [x] 🔴 1.2.1 Integrate `wifi-sleep.sh` script with `NetworkManager` class [COMPLETED 2025-05-16]
- [x] 🟠 1.2.2 Implement exponential backoff for network retry attempts [COMPLETED 2025-05-16]
- [x] 🟠 1.2.3 Add battery-level-aware WiFi power state transitions [COMPLETED 2025-05-17]

### 1.3 PiJuice Integration
- [x] 🔴 1.3.1 Add support for all PiJuice events (LOW_CHARGE, button press) [COMPLETED 2025-05-18]
- [x] 🔴 1.3.2 Create safe shutdown hooks for critical battery events [COMPLETED 2025-05-19]
- [x] 🟠 1.3.3 Implement dynamic wakeup scheduling based on battery levels [COMPLETED 2025-05-19]

### 1.4 Dynamic Display Management
- [x] 🔴 1.4.1 Make image difference threshold configurable and battery-aware [COMPLETED 2025-05-19]
- [x] 🟠 1.4.2 Implement variable refresh rates based on battery state [COMPLETED 2025-05-19]
- [x] 🟢 1.4.3 Add quiet hours display sleep mode [COMPLETED 2025-05-19]

## Phase 2: Code Optimization (Target: v0.3.0)

### 2.1 Convention Improvements
- [x] 🔴 2.1.1 Create centralized constants module for default values [COMPLETED 2025-05-19]
- [x] 🔴 2.1.2 Standardize path resolution across client and server [COMPLETED 2025-05-20]
- [x] 🟢 2.1.3 Implement consistent file system abstraction project-wide [COMPLETED 2025-05-21]

### 2.2 Modern Python Features
- [x] 🔴 2.2.1 Replace generic `Any` types with more specific Union types (HIGH PRIORITY) [COMPLETED 2025-05-23]
- [x] 🟢 2.2.2 Implement structural pattern matching for state handling [COMPLETED 2025-05-23]
- [x] 🟠 2.2.3 Add exception chaining throughout error handling [COMPLETED 2025-05-23]

### 2.3 Async Optimization (COMPLETED)
- [x] 🟠 2.3.1 Extend async/await pattern to client-side network operations [COMPLETED 2025-05-24]
- [x] 🟢 2.3.2 Implement async context managers for hardware resources [COMPLETED 2025-05-24]
- [x] 🟢 2.3.3 Add concurrency limits to prevent resource exhaustion [COMPLETED 2025-05-24]

### 2.4 Memory Management (COMPLETED)
- [x] 🔴 2.4.1 Optimize image processing for memory efficiency [COMPLETED 2025-05-24]
- [x] 🔴 2.4.2 Implement memory-aware caching with size limits [COMPLETED 2025-05-24]
- [x] 🟢 2.4.3 Add memory profiling and reporting [COMPLETED 2025-05-24]

### 2.5 Code Refactoring
- [ ] 🔴 2.5.1 Modularize power_manager.py (1270 lines, maintainability: 19.56) [PLANNED]
  - Split PowerStateManager into: BatteryMonitor, PowerStateController, SystemMetricsCollector, PiJuiceAdapter
  - Extract complex methods: get_battery_status (C-rated), get_system_metrics (C-rated)
  - Move test-specific methods to separate test utilities module
- [ ] 🔴 2.5.2 Refactor renderer.py generate_html method (D-rated complexity) [PLANNED]
  - Break down into smaller, focused methods: prepare_template_data, format_weather_data, setup_jinja_filters
  - Extract moon phase logic into separate helper class
  - Simplify nested conditionals and reduce cyclomatic complexity
- [ ] 🔴 2.5.3 Simplify renderer._get_daily_max_uvi method (C-rated complexity) [PLANNED]
  - Extract cache handling logic
  - Separate UVI calculation from persistence logic
- [ ] 🟠 2.5.4 Create custom exception hierarchy for better error handling [PLANNED]
- [ ] 🟠 2.5.5 Refactor complex network and display methods [PLANNED]
  - Simplify AsyncNetworkManager.set_wifi_power_save_mode
  - Break down EPaperDisplay.display_pil_image into smaller methods
- [ ] 🟢 2.5.6 Remove test-only methods from production interfaces [PLANNED]
- [ ] 🟢 2.5.7 Resolve circular import risks in utils module [PLANNED]

### 2.6 Hardware Abstractions (New)
- [ ] 🔴 2.6.1 Create hardware abstraction interfaces for display and power management [PLANNED]
- [ ] 🔴 2.6.2 Optimize Playwright usage in renderer for lower memory footprint [PLANNED]
- [ ] 🟠 2.6.3 Implement more robust error recovery mechanisms [PLANNED]

### 2.7 E-Paper Display Optimization
- [ ] 🔴 2.7.1 Implement correct refresh modes for Waveshare 10.3" (GC16/Mode2 at 4bpp for optimal grayscale) [PLANNED]
- [ ] 🔴 2.7.2 Add periodic full refresh using INIT mode (Mode0) to prevent ghosting artifacts [PLANNED]
- [ ] 🔴 2.7.3 Enforce minimum 180-second interval between refreshes per manufacturer specs [PLANNED]
- [ ] 🔴 2.7.4 Implement mandatory 24-hour full refresh to prevent screen burn-in [PLANNED]
- [ ] 🟠 2.7.5 Schedule full refresh during quiet hours for minimal user disruption [PLANNED]
- [ ] 🟠 2.7.6 Implement proper display sleep mode during extended idle periods [PLANNED]
- [ ] 🟠 2.7.7 Add refresh mode selection based on battery level and content type [PLANNED]
- [ ] 🟠 2.7.8 Validate 4bpp grayscale rendering matches display capabilities [PLANNED]
- [ ] 🟠 2.7.9 Optimize SPI transmission speed for power efficiency vs refresh performance [PLANNED]
- [ ] 🟠 2.7.10 Add environmental monitoring (temperature 0-50°C operating range) [PLANNED]
- [ ] 🟢 2.7.11 Track refresh count to monitor display lifetime (1M refresh limit) [PLANNED]

### 2.8 Deployment Script Security & Quality ✅ COMPLETED
- [x] 🔴 2.8.1 Add checksum verification for Poetry and other downloaded content [COMPLETED 2025-05-24]
- [x] 🔴 2.8.2 Implement dependency checks in all shell scripts (xmlstarlet, inkscape, etc.) [COMPLETED 2025-05-24]
- [x] 🔴 2.8.3 Add input validation and proper error handling to deployment scripts [COMPLETED 2025-05-24]
- [x] 🔴 2.8.4 Create backup mechanism for system modifications in optimize-power.sh [COMPLETED 2025-05-24]
- [x] 🟠 2.8.5 Replace `|| true` patterns with proper error handling [COMPLETED 2025-05-24]
- [x] 🟠 2.8.6 Implement atomic operations in trim_svgs.sh to prevent data loss [COMPLETED 2025-05-24]
- [x] 🟠 2.8.7 Add rollback capability for failed installations [COMPLETED 2025-05-24]
- [x] 🟢 2.8.8 Add --dry-run options to destructive scripts [COMPLETED 2025-05-24]
- [x] 🟢 2.8.9 Improve shell script quoting and safety (shellcheck compliance) [COMPLETED 2025-05-24]

## Phase 3: Telemetry and Monitoring (Target: v0.4.0)

### 3.1 Power Consumption Tracking
- [ ] 🔴 3.1.1 Add battery drain rate calculation [PLANNED]
- [ ] 🔴 3.1.2 Create power consumption logging for different operations [PLANNED]
- [ ] 🟠 3.1.3 Implement event markers for power state transitions [PLANNED]

### 3.2 Performance Metrics
- [ ] 🟠 3.2.1 Add timing measurements for critical operations [PLANNED]
- [ ] 🟠 3.2.2 Implement CPU/memory usage tracking [PLANNED]
- [ ] 🟢 3.2.3 Create metrics dashboard for the server [PLANNED]

### 3.3 Logging Enhancements
- [ ] 🔴 3.3.1 Replace all `print()` calls with structured logging [PLANNED]
- [ ] 🟠 3.3.2 Implement contextual logging with operation IDs [PLANNED]
- [ ] 🟠 3.3.3 Add log rotation and size limits [PLANNED]

### 3.4 Remote Diagnostics
- [ ] 🟠 3.4.1 Create minimal telemetry data format for battery status [PLANNED]
- [ ] 🟠 3.4.2 Implement periodic reporting to server during updates [PLANNED]
- [ ] 🟢 3.4.3 Add alert mechanism for abnormal power consumption [PLANNED]

## Phase 4: Adaptive Behavior (Target: v0.5.0)

### 4.1 Weather Update Optimization
- [ ] 🔴 4.1.1 Implement forecast-aware update scheduling (less frequent during stable weather) [PLANNED]
- [ ] 🔴 4.1.2 Add weekly schedule-based power management (work/home/weekend schedules) [PLANNED]
- [ ] 🟠 4.1.3 Implement presence inference via network detection for smart scheduling [PLANNED]
- [ ] 🟠 4.1.4 Add time-of-day awareness to update frequency [PLANNED]
- [ ] 🟠 4.1.5 Create bundled API requests to minimize network connections [PLANNED]

### 4.2 Caching Strategy
- [ ] 🔴 4.2.1 Implement TTL-based cache invalidation [PLANNED]
- [ ] 🔴 4.2.2 Add differential data updates to minimize transfer size [PLANNED]
- [ ] 🟢 4.2.3 Create hierarchical caching (memory, disk, server) [PLANNED]

### 4.3 CPU Management Integration
- [ ] 🟠 4.3.1 Detect available CPU cores and adjust processing [PLANNED]
- [ ] 🟠 4.3.2 Implement dynamic CPU frequency scaling requests for intensive operations [PLANNED]
- [ ] 🟠 4.3.3 Add workload scheduling to minimize CPU wakeups [PLANNED]

### 4.4 Hardware Adaptation
- [ ] 🟠 4.4.1 Create abstraction layer for different e-paper display types [PLANNED]
- [ ] 🟢 4.4.2 Add support for different power management backends [PLANNED]
- [ ] 🟢 4.4.3 Implement feature detection for hardware capabilities [PLANNED]

## Phase 5: Testing and Performance Validation (Target: v1.0.0)

### 5.1 Power Validation
- [ ] 🔴 5.1.1 Create battery life projection tests [PLANNED]
- [ ] 🔴 5.1.2 Implement power consumption benchmarks [PLANNED]
- [ ] 🟠 5.1.3 Add regression testing for power optimizations [PLANNED]

### 5.2 Enhanced Test Coverage
- [ ] 🔴 5.2.1 Add property-based tests with Hypothesis for critical components [PLANNED]
- [ ] 🔴 5.2.2 Implement integration tests for power management features [PLANNED]
- [ ] 🟠 5.2.3 Create mock hardware environment for testing [PLANNED]

### 5.7 Hardware Integration & Testing
- [ ] 🔴 5.7.1 Set up Pi development environment for hardware testing [PLANNED]
- [ ] 🔴 5.7.2 Test PiJuice integration (battery status, events, shutdown) [PLANNED]
- [ ] 🔴 5.7.3 Test Waveshare e-paper display functionality and performance [PLANNED]
- [ ] 🔴 5.7.4 Validate power optimization script effectiveness on real hardware [PLANNED]
- [ ] 🔴 5.7.5 Test deep sleep/wake cycles with actual hardware timers [PLANNED]
- [ ] 🟠 5.7.6 Benchmark real power consumption vs theoretical estimates [PLANNED]
- [ ] 🟠 5.7.7 Test WiFi power management and connection stability [PLANNED]
- [ ] 🟠 5.7.8 Validate display refresh performance and battery impact [PLANNED]
- [ ] 🟢 5.7.9 Test hardware failure scenarios and recovery mechanisms [PLANNED]

### 5.3 Real-world Validation
- [ ] 🔴 5.3.1 Design extended battery life tests (multi-week) [PLANNED]
- [ ] 🟠 5.3.2 Implement A/B testing for optimization strategies [PLANNED]
- [ ] 🟢 5.3.3 Add environmental factor analysis (temperature impact, etc.) [PLANNED]

### 5.4 Documentation Updates
- [ ] 🔴 5.4.1 Create power optimization guide [PLANNED]
- [x] 🔴 5.4.2 Add proper Google-style docstrings to all modules, classes and functions [COMPLETED 2025-05-19]
- [ ] 🟠 5.4.3 Update code documentation to reflect optimization patterns [PLANNED]
- [ ] 🟠 5.4.4 Add battery life estimates based on usage patterns [PLANNED]

### 5.5 Deployment Improvements
- [ ] 🔴 5.5.1 Implement automatic update mechanism for client [PLANNED]
- [ ] 🟠 5.5.2 Create comprehensive CI/CD pipeline for deployment [PLANNED]
- [ ] 🟠 5.5.3 Add rollback capability for failed updates [PLANNED]
- [ ] 🔴 5.5.4 Add security scanning to CI/CD pipeline [PLANNED]
- [ ] 🟠 5.5.5 Implement deployment verification suite [PLANNED]
- [ ] 🟠 5.5.6 Add network security improvements (certificate validation) [PLANNED]

### 5.6 Docker & Unraid Optimization
- [ ] 🔴 5.6.1 Optimize Docker container for Unraid server deployment [PLANNED]
- [ ] 🔴 5.6.2 Add health checks and monitoring for Docker container [PLANNED]
- [ ] 🟠 5.6.3 Implement resource limits and memory optimization for server container [PLANNED]
- [ ] 🟠 5.6.4 Create Unraid Community Apps template [PLANNED]
- [ ] 🟠 5.6.5 Add Docker Compose configuration for easy deployment [PLANNED]
- [ ] 🟢 5.6.6 Implement container auto-restart and recovery mechanisms [PLANNED]

## Phase 6: Enhanced User Experience

### 6.1 Template Optimization
- [ ] 🟠 6.1.1 Refactor templates to reduce duplication [PLANNED]
- [ ] 🟠 6.1.2 Add template documentation for complex components [PLANNED]
- [ ] 🟢 6.1.3 Create themeable layout with configurable sections [PLANNED]

### 6.2 Preview & Development Experience
- [ ] 🟠 6.2.1 Enhance browser-based preview with live reload capability [PLANNED]
- [ ] 🟠 6.2.2 Add configurator UI for display settings [PLANNED]
- [ ] 🟢 6.2.3 Implement template validation during development [PLANNED]

### 6.3 Advanced Customization
- [ ] 🟠 6.3.1 Support for additional weather data providers [PLANNED]
- [ ] 🟠 6.3.2 Add plugin architecture for custom data sources [PLANNED]
- [ ] 🔴 6.3.3 Create web-based configuration editor with real-time validation [PLANNED]

### 6.4 Configuration Management
- [ ] 🔴 6.4.1 Build interactive config editor using existing Pydantic validation [PLANNED]
- [ ] 🔴 6.4.2 Add live preview of config changes on dashboard [PLANNED]
- [ ] 🟠 6.4.3 Implement config backup/restore functionality [PLANNED]
- [ ] 🟠 6.4.4 Add config validation API endpoints for real-time feedback [PLANNED]
- [ ] 🟠 6.4.5 Create guided setup wizard for first-time users [PLANNED]
- [ ] 🟢 6.4.6 Add config templates for common use cases [PLANNED]

### 6.5 Server-Side FastAPI Optimizations
- [ ] 🟢 6.5.1 Implement background tasks for cache cleanup and maintenance [PLANNED]
- [ ] 🟢 6.5.2 Add dependency injection for shared resources (API client, renderer) [PLANNED]
- [ ] 🟢 6.5.3 Create middleware for request logging and performance monitoring [PLANNED]
- [ ] 🟢 6.5.4 Add startup/shutdown events for initialization and cleanup [PLANNED]
- [ ] 🟢 6.5.5 Implement WebSocket support for real-time preview updates [PLANNED]
- [ ] 🟢 6.5.6 Add request context and tracing for better debugging [PLANNED]

### 6.6 Server-Side Caching Enhancements (Low Priority)
- [ ] 🟢 6.6.1 Implement image caching in render endpoint based on weather data hash + battery status [PLANNED]
- [ ] 🟢 6.6.2 Cache geocoding results indefinitely (city coordinates don't change) [PLANNED]
- [ ] 🟢 6.6.3 Add HTML template render caching for identical weather data [PLANNED]
- [ ] 🟢 6.6.4 Implement cache warming during quiet hours [PLANNED]
- [ ] 🟢 6.6.5 Add cache hit/miss metrics for monitoring effectiveness [PLANNED]
- [ ] 🟢 6.6.6 Create cache invalidation API endpoints for manual refresh [PLANNED]

## Phase 7: Server-Side Data Analytics & Local Sensors (Target: v1.5.0)

### 7.1 Weather Data Storage & Analytics (Docker Container)
- [ ] 🔴 7.1.1 Add database backend for historical weather data storage [PLANNED]
- [ ] 🔴 7.1.2 Create weather trend visualization web dashboard [PLANNED]
- [ ] 🟠 7.1.3 Implement data retention policies and archiving [PLANNED]
- [ ] 🟠 7.1.4 Add statistical analysis for weather patterns (seasonal trends, anomalies) [PLANNED]
- [ ] 🟠 7.1.5 Create exportable reports and data dumps [PLANNED]
- [ ] 🟢 7.1.6 Add weather prediction accuracy tracking vs actual conditions [PLANNED]

### 7.2 Local Sensor Integration (Docker Container Only)
- [ ] 🔴 7.2.1 Create sensor API endpoints for external sensor data ingestion [PLANNED]
- [ ] 🔴 7.2.2 Add thermostat integration (Nest, Ecobee, Honeywell APIs) [PLANNED]
- [ ] 🟠 7.2.3 Implement network-based sensor support (HTTP, MQTT, InfluxDB) [PLANNED]
- [ ] 🟠 7.2.4 Add air quality sensor data ingestion (PM2.5, PM10, VOC, CO2) [PLANNED]
- [ ] 🟠 7.2.5 Support for weather station APIs (Davis, Ambient Weather, etc.) [PLANNED]
- [ ] 🟢 7.2.6 Create sensor calibration and data validation system [PLANNED]

### 7.3 Hybrid Data Processing (Docker Container)
- [ ] 🔴 7.3.1 Blend local sensor data with weather API data in image generation [PLANNED]
- [ ] 🟠 7.3.2 Implement sensor data validation and outlier detection [PLANNED]
- [ ] 🟠 7.3.3 Add configurable weighting between local vs remote data sources [PLANNED]
- [ ] 🟠 7.3.4 Create alerts and notifications for sensor anomalies [PLANNED]
- [ ] 🟢 7.3.5 Generate trend-aware display layouts based on historical data [PLANNED]

### 7.4 Ultra-Minimal Client Architecture
- [ ] 🔴 7.4.1 Simplify Pi client to pure image fetch + display cycle [PLANNED]
- [ ] 🔴 7.4.2 Remove all data processing from Pi client code [PLANNED]
- [ ] 🟠 7.4.3 Add client-side image caching for offline resilience [PLANNED]
- [ ] 🟢 7.4.4 Create fallback display modes when server is unreachable [PLANNED]

## Recommended Task Prioritization

Based on the code complexity analysis, the following tasks should be prioritized:

**Code Quality Metrics Summary:**
- Average Complexity: C (15.78) - Acceptable but room for improvement
- Complex Functions (E-F): 0 - Good, no extremely complex functions
- Lowest Maintainability: power_manager.py (19.56), renderer.py (38.99)
- Highest Complexity Method: renderer.generate_html (D rating)

*Complexity Ratings: A (simple) → B → C (moderate) → D (complex) → E → F (very complex)*

### Immediate Priority (Next Sprint)
1. **Phase 2.5.2** - Refactor renderer.py generate_html method
   - Complexity rating: D (highest in codebase)
   - Method is doing too many things and needs decomposition
   - Will improve maintainability score (currently 38.99)

2. **Phase 2.5.1** - Modularize power_manager.py
   - Maintainability index: 19.56 (lowest in codebase)
   - 1270 lines is too large
   - Contains C-rated complex methods that need extraction

3. **Phase 2.5.3** - Simplify renderer._get_daily_max_uvi
   - Complexity rating: C
   - Mixed concerns (calculation + caching + persistence)

### Short-term Priority (Q1 2025)
1. **Phase 2.5.5** - Refactor other C-rated complex methods
   - api.py: get_coordinates, get_weather_data
   - network.py: set_wifi_power_save_mode
   - display.py: display_pil_image
   - client/main.py: run method
2. **Phase 2.5.4** - Create custom exception hierarchy
3. **Phase 2.5.6** - Remove test-only methods from production

### Medium-term Priority (Q2 2025)
1. **Phase 2.7** - E-Paper display optimization
2. **Phase 3** - Telemetry and monitoring
3. **Phase 4** - Adaptive behavior

## Progress Summary

| Phase | Not Started | In Progress | Completed | Total |
|-------|------------|-------------|-----------|-------|
| 1     | 0          | 0           | 14        | 14    |
| 2     | 16         | 0           | 18        | 34    |
| 3     | 12         | 0           | 0         | 12    |
| 4     | 12         | 0           | 0         | 12    |
| 5     | 17         | 0           | 2         | 19    |
| 6     | 21         | 0           | 0         | 21    |
| 7     | 18         | 0           | 0         | 18    |
| Total | 96         | 0           | 34        | 130   |