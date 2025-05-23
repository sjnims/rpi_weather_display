# CodeQL Configuration

This directory contains the CodeQL configuration for the rpi_weather_display project.

## False Positives

The project uses Python 3.10+ structural pattern matching, which CodeQL's current rules don't fully understand. This leads to false positives for:

### 1. Uninitialized Local Variable (py/uninitialized-local-variable)
- **Location**: `power_manager.py:541`
- **Reason**: Pattern matching with exhaustive cases (including `case _:`) always assigns a value

### 2. Mixed Returns (py/mixed-returns)
- **Locations**: 
  - `battery_utils.py`: Lines 43, 117, 139
  - `display.py`: Lines 358, 402
  - `network.py`: Lines 63, 93, 185, 229
  - `power_manager.py`: Line 415
- **Reason**: Pattern matching with catch-all `case _:` ensures all paths return a value

## Pattern Matching Examples

These patterns are exhaustive and safe:

```python
# Example 1: Simple exhaustive match
match status.state:
    case BatteryState.CHARGING:
        return True
    case _:  # Catches ALL other cases
        return False

# Example 2: Tuple matching with catch-all
match (state, level):
    case (BatteryState.CHARGING, level):
        return f"Charging ({level}%)"
    case (BatteryState.FULL, _):
        return "Fully Charged"
    case (_, level):  # Catches ALL remaining tuples
        return f"Battery: {level}%"
```

## Configuration

The `codeql-config.yml` file excludes these false positive queries to reduce noise while maintaining security scanning for real issues.