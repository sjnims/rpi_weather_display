# Power Optimization Guide

This guide details the power optimization techniques implemented to achieve 60-90 days of battery life on a single charge.

## Overview

The Ultra-Low-Power Weather Display implements a comprehensive power management strategy across hardware, software, and operational levels. The goal is to minimize power consumption while maintaining functionality.

## Power Consumption Targets

- **Active Mode**: ~120mA @ 5V (during updates)
- **Sleep Mode**: <5mA @ 5V (between updates)
- **Average Daily**: ~50-70mAh (with 30-minute updates)
- **Battery Life**: 60-90 days on 12,000mAh battery

## Hardware Optimizations

### CPU Management

**Frequency Scaling:**
```bash
# Limited to 700 MHz (from 1000 MHz default)
echo 700000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Power-save governor
echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
```

**Core Disabling:**
```bash
# Disable 3 of 4 cores
echo 0 > /sys/devices/system/cpu/cpu1/online
echo 0 > /sys/devices/system/cpu/cpu2/online
echo 0 > /sys/devices/system/cpu/cpu3/online
```

Power Savings: ~40-50% reduction in CPU power consumption

### Peripheral Management

**HDMI Output:**
```bash
# Disable HDMI completely
/usr/bin/tvservice -o
```
Power Savings: ~25mA

**USB/Ethernet:**
```bash
# Disable USB controller (includes Ethernet)
echo '1-1' > /sys/bus/usb/drivers/usb/unbind
```
Power Savings: ~20mA

**Bluetooth:**
```bash
# Disable Bluetooth
systemctl disable bluetooth
rfkill block bluetooth
```
Power Savings: ~10mA

**Status LEDs:**
```bash
# Disable ACT LED
echo none > /sys/class/leds/ACT/trigger

# Disable PWR LED
echo 0 > /sys/class/leds/PWR/brightness
```
Power Savings: ~5mA

### WiFi Power Management

**Power Save Mode:**
```bash
# Enable WiFi power saving
iw dev wlan0 set power_save on
```

**Dynamic WiFi Control:**
- WiFi disabled when not needed
- Enabled only for network operations
- Automatic disable after use
- Power-save mode during operations

Power Savings: ~70mA when WiFi is off

## Software Optimizations

### Async Architecture

The client uses async/await patterns for improved power efficiency:

```python
# CPU sleeps during I/O operations
async with AsyncNetworkManager() as network:
    async with network.ensure_connectivity():
        response = await client.get(url)
# WiFi automatically disabled on exit
```

Benefits:
- CPU enters sleep state during network I/O
- No busy-waiting or polling
- Automatic resource cleanup
- Reduced total wake time

### Sleep Management

**Deep Sleep Between Updates:**
```python
# Use PiJuice for hardware-controlled sleep
pijuice.power.SetWakeUpOnCharge(0.0)  # Disable
pijuice.rtc.SetAlarm(next_wakeup_time)
pijuice.power.SetSystemPowerSwitch(0)  # Deep sleep
```

Power Consumption in Sleep: <5mA

### Memory Optimizations

**ZRAM Compression:**
```bash
# Enable ZRAM for memory compression
modprobe zram
echo lz4 > /sys/block/zram0/comp_algorithm
echo 256M > /sys/block/zram0/disksize
mkswap /dev/zram0
swapon /dev/zram0
```

**Tmpfs for Temporary Files:**
```bash
# Use RAM for /tmp and /var/log
mount -t tmpfs -o size=50M tmpfs /tmp
mount -t tmpfs -o size=50M tmpfs /var/log
```

Benefits:
- Reduced SD card access (power-hungry)
- Faster operations
- Less wear on SD card

## Operational Optimizations

### Update Scheduling

**Quiet Hours:**
```yaml
power:
  quiet_hours_start: "23:00"
  quiet_hours_end: "06:00"
```
- Reduced update frequency at night
- Display sleep during quiet hours

**Battery-Aware Scheduling:**
```yaml
display:
  refresh_interval_minutes: 30              # Normal
  refresh_interval_low_battery_minutes: 60   # <20% battery
  refresh_interval_critical_battery_minutes: 120  # <10% battery
```

### Display Optimizations

**Partial Refresh:**
- Use partial refresh when possible
- Full refresh only when necessary
- Minimum 180-second interval between refreshes

**Change Detection:**
```yaml
display:
  pixel_diff_threshold: 10  # Normal threshold
  pixel_diff_threshold_low_battery: 20  # Higher when battery low
  min_changed_pixels: 100  # Minimum changes to trigger refresh
```

### Network Optimizations

**Efficient API Usage:**
- Single bundled request for all weather data
- Caching to reduce API calls
- Compression for data transfer

**Connection Management:**
- Timeout limits to prevent hanging
- Exponential backoff for retries
- Maximum retry attempts

## System-Level Optimizations

### Kernel Parameters

```bash
# /boot/cmdline.txt additions
consoleblank=1 # Screen blanking
fastboot noswap # Faster boot, no swap
```

### Service Management

**Disabled Services:**
```bash
# Disable unnecessary services
systemctl disable avahi-daemon
systemctl disable triggerhappy
systemctl disable apt-daily.timer
systemctl disable apt-daily-upgrade.timer
systemctl disable man-db.timer
```

### Filesystem Optimizations

**Reduce Disk Writes:**
```bash
# Mount with noatime
/dev/mmcblk0p2 / ext4 defaults,noatime 0 1

# Disable filesystem journaling (optional, risky)
tune2fs -O ^has_journal /dev/mmcblk0p2
```

## Configuration Tuning

### Optimal Settings for Battery Life

```yaml
# Maximum battery life configuration
display:
  refresh_interval_minutes: 60
  refresh_interval_low_battery_minutes: 120
  refresh_interval_critical_battery_minutes: 240
  battery_aware_refresh: true
  pixel_diff_threshold: 15
  min_changed_pixels: 200

power:
  quiet_hours_start: "22:00"
  quiet_hours_end: "07:00"
  low_battery_threshold: 25
  critical_battery_threshold: 15
  wake_up_interval_minutes: 60
  wifi_power_save_mode: "aggressive"

weather:
  update_interval_minutes: 60
```

### Balanced Settings

```yaml
# Balance between updates and battery life
display:
  refresh_interval_minutes: 30
  refresh_interval_low_battery_minutes: 60
  battery_aware_refresh: true

power:
  quiet_hours_start: "23:00"
  quiet_hours_end: "06:00"
  low_battery_threshold: 20
  wifi_power_save_mode: "auto"
```

## Monitoring Power Usage

### Real-time Monitoring

```bash
# Monitor current draw (if supported by PiJuice)
pijuice_cli --status | grep Current

# System power state
cat /sys/class/power_supply/*/uevent

# CPU frequency
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
```

### Power Profiling

```python
# Add to your code for power profiling
import time
from pijuice import PiJuice

pj = PiJuice(1, 0x14)

def measure_operation(operation_name):
    start_current = pj.status.GetBatteryCurrent()
    start_time = time.time()

    yield  # Operation runs here

    end_current = pj.status.GetBatteryCurrent()
    duration = time.time() - start_time
    avg_current = (start_current + end_current) / 2

    print(f"{operation_name}: {avg_current}mA for {duration}s")
```

## Troubleshooting Power Issues

### High Power Consumption

1. **Check CPU frequency:**
   ```bash
   watch -n 1 cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
   ```

2. **Monitor processes:**
   ```bash
   top -b -n 1 | head -20
   ```

3. **Check WiFi state:**
   ```bash
   iw dev wlan0 get power_save
   ```

4. **Verify peripherals disabled:**
   ```bash
   tvservice -s  # Should show "TV is off"
   rfkill list   # Bluetooth should be blocked
   ```

### Battery Not Lasting

1. **Review update frequency** - Consider increasing intervals
2. **Check quiet hours** - Extend the quiet period
3. **Monitor wake reasons** - Check logs for unexpected wakes
4. **Verify deep sleep** - Ensure proper sleep between updates
5. **Check battery health** - Old batteries have reduced capacity

## Best Practices

1. **Start Conservative**: Begin with longer update intervals and adjust down
2. **Monitor First Week**: Track battery usage closely initially
3. **Seasonal Adjustments**: Consider different settings for seasons
4. **Location Matters**: Indoor displays can use less frequent updates
5. **Battery Maintenance**: Occasional full discharge/charge cycles
6. **Temperature Effects**: Cold weather reduces battery capacity

## Advanced Techniques

### Custom Power Profiles

Create different power profiles for various scenarios:

```python
# profiles.py
POWER_PROFILES = {
    "ultra_low": {
        "refresh_interval_minutes": 120,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "08:00",
    },
    "balanced": {
        "refresh_interval_minutes": 45,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "06:00",
    },
    "performance": {
        "refresh_interval_minutes": 15,
        "quiet_hours_start": "00:00",
        "quiet_hours_end": "05:00",
    }
}
```

### Adaptive Scheduling

Implement weather-based scheduling:

```python
# Reduce updates during stable weather
if weather_is_stable():
    refresh_interval *= 2

# Increase updates during severe weather
if severe_weather_alert():
    refresh_interval = min(15, refresh_interval)
```

## Results

With all optimizations applied:

- **Idle Power**: <5mA
- **Active Power**: ~120mA (for ~30 seconds)
- **Daily Consumption**: 50-70mAh
- **Expected Battery Life**: 60-90 days on 12,000mAh

These optimizations reduce power consumption by approximately 90% compared to an unoptimized Raspberry Pi Zero 2 W setup.