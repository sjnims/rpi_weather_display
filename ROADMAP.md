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
- [x] 🔴 2.5.1 Modularize power_manager.py (1270 lines, maintainability: 19.56) [COMPLETED 2025-05-24]
  - Split PowerStateManager into: BatteryMonitor, PowerStateController, SystemMetricsCollector, PiJuiceAdapter
  - Extract complex methods: get_battery_status (C-rated), get_system_metrics (C-rated)
  - Move test-specific methods to separate test utilities module
- [x] 🔴 2.5.2 Refactor renderer.py generate_html method (D-rated, CC: 27) [COMPLETED 2025-05-25]
  - Break down into smaller, focused methods: prepare_template_data, format_weather_data, setup_jinja_filters
  - Extract moon phase logic into separate helper class
  - Simplify nested conditionals and reduce cyclomatic complexity
  - NOTE: Successfully reduced complexity from CC: 27 to CC: 5 (81% reduction!)
  - Extracted logic into MoonPhaseHelper and WindHelper classes
  - Created 6 helper methods: _get_template_data, _add_weather_icons, _add_daily_forecast_icons, _add_hourly_forecast_icons, _add_wind_icons, _get_moon_icon
  - Fixed weather models to correctly match OpenWeatherMap API structure
  - All tests passing and preview functionality confirmed working
- [x] 🔴 2.5.3 Refactor battery_monitor.py get_battery_status method (D-rated, CC: 22) [COMPLETED 2025-05-25]
  - NEW: Emerged as high complexity after power_manager modularization
  - Break down battery status determination logic
  - Extract voltage-based calculations into separate methods
  - Simplify nested conditionals for different battery states
  - NOTE: Successfully reduced complexity from CC: 22 to below 10 (no longer in high complexity list)
  - Extracted 6 helper methods: _get_development_battery_status, _get_default_battery_status, _extract_pijuice_value, _get_pijuice_data, _determine_battery_state, _update_battery_history
  - All tests passing and functionality preserved
- [x] 🔴 2.5.4 Simplify renderer._get_daily_max_uvi method (C-rated, CC: 19) [COMPLETED 2025-05-25]
  - Extract cache handling logic
  - Separate UVI calculation from persistence logic
  - NOTE: Complexity increased to CC: 19 after generate_html refactoring
  - Successfully reduced complexity from CC: 19 to below 10 (no longer in high complexity list)
  - Extracted 3 helper methods: _calculate_current_max_uvi, _read_uvi_cache, _write_uvi_cache
  - Simplified main method from ~75 lines to 17 lines
  - All tests passing and functionality preserved
- [x] 🟠 2.5.5 Create custom exception hierarchy for better error handling [COMPLETED 2025-05-25]
  - Created comprehensive exception hierarchy in exceptions.py with 24 domain-specific exception classes
  - Implemented all 4 previously unused exceptions throughout the codebase:
    - PowerStateError: Added to power_state_controller.py for invalid state transitions
    - WakeupSchedulingError: Added to pijuice_adapter.py for alarm scheduling failures
    - NetworkTimeoutError: Added to network.py for network operation timeouts
    - NetworkUnavailableError: Added to network.py for network unreachability errors
  - Removed unused WiFiConnectionError exception (replaced by NetworkTimeoutError)
  - Added exception chaining utility for preserving error context
  - Updated all affected tests to handle new exception behavior
  - Achieved 94.51% overall test coverage with all 818 tests passing
- [x] 🟠 2.5.6 Refactor other complex methods (C-rated) [COMPLETED 2025-05-25]
  - Break down EPaperDisplay.display_pil_image (CC: 15 → 7)
  - Simplify renderer._prepare_time_data (CC: 14 → 4) - NEW: emerged after generate_html refactoring
  - Simplify AsyncNetworkManager.set_wifi_power_save_mode (CC: 13 → 4)
  - Refactor client/main.py run method (CC: 13 → 5)
  - Simplify api.py get_coordinates (CC: 12 → 2) and get_weather_data (CC: 11 → 4)
- [x] 🟠 2.5.7 Improve renderer.py maintainability through modularization [COMPLETED 2025-05-25]
  - NOTE: Maintainability Index improved from 36.81 to 57.66 (+56.6%)
  - Extracted template filter management to template_filter_manager.py (MI: 76.81)
  - Extracted time/date formatting to time_formatter.py (MI: 69.53)
  - Extracted weather calculations to weather_calculator.py (MI: 64.53)
  - Extracted icon mapping to weather_icon_mapper.py (MI: 74.02)
  - Added comprehensive tests for all new modules (>96% coverage each)
  - All new modules achieved "A" rank maintainability
- [x] 🟠 2.5.8 Modularize display.py for improved maintainability [COMPLETED 2025-05-25]
  - NOTE: Display.py emerged as low maintainability (MI: 41.40) after other refactoring
  - Successfully improved maintainability from MI: 41.40 to 62.58 (+51%)
  - Extracted logic into 4 focused modules:
    - battery_threshold_manager.py (MI: 65.48) - Battery threshold management logic
    - image_processor.py (MI: 67.22) - Image processing operations
    - partial_refresh_manager.py (MI: 74.01) - Partial refresh coordination  
    - text_renderer.py (MI: 67.59) - Text rendering utilities
  - All new modules achieved "A" rank maintainability
  - Added 50+ comprehensive test cases with 90%+ coverage
- [ ] 🟢 2.5.9 Remove test-only methods from production interfaces [PLANNED]
- [ ] 🟢 2.5.10 Resolve circular import risks in utils module [PLANNED]

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

**Code Quality Metrics Summary (Updated 2025-05-25 after exception implementation):**
- Average Complexity: 2.89 (slight increase from 2.70 due to exception handling) - Still excellent!
- Complex Functions (CC > 10): 1 (config.py:from_yaml CC: 15) - Nearly at goal!
- Lowest Maintainability: exceptions.py at 38.6 (expected for exception definitions)
- Average Maintainability: 68.2/100 - Good overall maintainability (slight decrease from 69.4)
- Successfully Refactored (All complex methods now below CC 10):
  - renderer.generate_html: CC 27 → 5 (D → A rating) - 81% reduction!
  - battery_monitor.get_battery_status: CC 22 → <10 (D → A/B rating)
  - renderer._get_daily_max_uvi: CC 19 → <10 (C → A/B rating)
  - display.display_pil_image: CC 15 → 7 (C → A rating)
  - renderer._prepare_time_data: CC 14 → 4 (C → A rating)
  - network.set_wifi_power_save_mode: CC 13 → 4 (C → A rating)
  - client/main.run: CC 13 → 5 (C → A rating)
  - api.get_coordinates: CC 12 → 2 (C → A rating)
  - api.get_weather_data: CC 11 → 4 (C → A rating)
  - power_manager: Modularized into smaller, focused components
  - display.py: Modularized into 4 focused modules (MI: 41.40 → 62.58)
- Total Source Lines: 4,970 (+679 from previous, +877 from baseline)
- Comment Ratio: 18.17% - Decreased due to added exception handling code
- Test Coverage: 94.51% - Exceeds 94% requirement!

*Complexity Ratings: A (simple) → B → C (moderate) → D (complex) → E → F (very complex)*

### Immediate Priority (Next Sprint)
1. **Phase 2.7** - E-Paper display optimization
   - Implement correct refresh modes for Waveshare 10.3"
   - Add periodic full refresh to prevent ghosting
   - Enforce manufacturer-specified refresh intervals
   
2. **Phase 2.5.9-10** - Final code cleanup
   - Remove test-only methods from production interfaces
   - Resolve circular import risks in utils module

### Short-term Priority (Q1 2025)
1. **Phase 2.6** - Hardware abstractions
   - Create hardware abstraction interfaces
   - Optimize Playwright usage for lower memory footprint
2. **Phase 3.1** - Power consumption tracking
   - Add battery drain rate calculation
   - Create power consumption logging for different operations

### Medium-term Priority (Q2 2025)
1. **Phase 3** - Complete telemetry and monitoring implementation
2. **Phase 4** - Adaptive behavior for power optimization
3. **Phase 5.7** - Hardware integration and testing on actual Pi

## Progress Summary

| Phase | Not Started | In Progress | Completed | Total |
|-------|------------|-------------|-----------|-------|
| 1     | 0          | 0           | 14        | 14    |
| 2     | 10         | 0           | 27        | 37    |
| 3     | 12         | 0           | 0         | 12    |
| 4     | 12         | 0           | 0         | 12    |
| 5     | 17         | 0           | 2         | 19    |
| 6     | 21         | 0           | 0         | 21    |
| 7     | 18         | 0           | 0         | 18    |
| Total | 90         | 0           | 43        | 133   |