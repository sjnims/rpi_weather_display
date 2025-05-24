# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the Ultra-Low-Power Weather Display.

## Client Issues (Raspberry Pi)

### Display Not Updating

**Symptoms:**
- E-paper display shows old weather data
- Last update timestamp is outdated
- Display appears frozen

**Solutions:**

1. **Check if the service is running:**
   ```bash
   sudo systemctl status rpi-weather-display.service
   ```
   If not running, start it:
   ```bash
   sudo systemctl start rpi-weather-display.service
   ```

2. **Verify network connectivity:**
   ```bash
   ping 8.8.8.8
   ```
   If no response, check your WiFi configuration.

3. **Check server connectivity:**
   ```bash
   curl -v http://your-server:8000/
   ```
   Should return `{"status":"ok","service":"Weather Display Server"}`

4. **Check logs for errors:**
   ```bash
   sudo journalctl -u rpi-weather-display.service -n 50
   ```
   Look for connection errors, timeout messages, or Python exceptions.

### Battery Draining Too Quickly

**Symptoms:**
- Battery life significantly less than expected 60-90 days
- Frequent low battery warnings
- Device shutting down prematurely

**Solutions:**

1. **Verify power optimizations are active:**
   ```bash
   # Check CPU governor
   cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
   # Should show "powersave"

   # Check CPU frequency
   cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
   # Should be 700000 or less
   ```

2. **Check WiFi power save mode:**
   ```bash
   iw dev wlan0 get power_save
   # Should show "Power save: on"
   ```

3. **Check for CPU-intensive processes:**
   ```bash
   top -b -n 1
   ```
   Look for any processes using significant CPU time.

4. **Adjust configuration for better battery life:**
   - Increase `quiet_hours_start` and `quiet_hours_end` range
   - Increase `refresh_interval_minutes` values
   - Increase `wake_up_interval_minutes`
   - Set `wifi_power_save_mode` to "aggressive"

### PiJuice Issues

**Symptoms:**
- Battery status not showing correctly
- Device not waking from sleep
- Unexpected shutdowns

**Solutions:**

1. **Verify PiJuice is detected:**
   ```bash
   i2cdetect -y 1
   ```
   Should show device at address 0x14.

2. **Check PiJuice status:**
   ```bash
   pijuice_cli --status
   ```

3. **Update PiJuice firmware:**
   ```bash
   pijuice_cli --update-firmware
   ```

4. **Check PiJuice configuration:**
   ```bash
   pijuice_cli --get-config
   ```

### Display Hardware Issues

**Symptoms:**
- Display shows garbled content
- Display not responding
- Partial refresh not working

**Solutions:**

1. **Check display connections:**
   - Ensure the display HAT is properly seated
   - Check ribbon cable connections
   - Verify SPI is enabled: `raspi-config`

2. **Test display with example code:**
   ```bash
   cd /opt/rpiweather
   poetry run python -c "from rpi_weather_display.client.display import EpaperDisplay; d = EpaperDisplay(); d.test()"
   ```

3. **Check VCOM setting:**
   - Verify the VCOM value in config matches your display
   - Usually found on a sticker on the display flex cable

## Server Issues (Docker)

### Server Not Responding

**Symptoms:**
- Client can't connect to server
- Browser preview not working
- No response from API endpoints

**Solutions:**

1. **Check if container is running:**
   ```bash
   docker ps
   ```
   Should show the rpi-weather-display container.

2. **View server logs:**
   ```bash
   docker logs rpi-weather-display -n 50
   ```
   Look for startup errors or exceptions.

3. **Verify port is accessible:**
   ```bash
   curl -v http://localhost:8000/
   ```

4. **Check Docker container health:**
   ```bash
   docker inspect rpi-weather-display
   ```

5. **Restart the container:**
   ```bash
   docker restart rpi-weather-display
   ```

### Weather Data Not Updating

**Symptoms:**
- Same weather data shown repeatedly
- Old forecast information
- Missing current conditions

**Solutions:**

1. **Check API key validity:**
   - Verify your OpenWeatherMap API key is active
   - Check API usage limits haven't been exceeded
   - Test API key directly:
     ```bash
     curl "https://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_API_KEY"
     ```

2. **Check cache permissions:**
   ```bash
   docker exec rpi-weather-display ls -la /tmp/weather-cache-1000
   ```

3. **Force cache refresh:**
   - Restart the container to clear memory cache
   - Delete cache directory contents if needed

4. **Verify OpenWeatherMap service status:**
   - Check https://status.openweathermap.org/

### Memory Issues

**Symptoms:**
- Container using excessive memory
- Out of memory errors in logs
- Server becoming unresponsive

**Solutions:**

1. **Check memory usage:**
   ```bash
   docker stats rpi-weather-display
   ```

2. **View memory profile:**
   ```bash
   curl http://localhost:8000/memory
   ```

3. **Set memory limits for container:**
   ```bash
   docker run -d --memory="512m" --memory-swap="1g" ...
   ```

4. **Check for memory leaks:**
   - Monitor memory usage over time
   - Check logs for repeated error patterns

## Common Error Messages

### "Failed to connect to server"
- Check network connectivity
- Verify server URL in config
- Ensure server is running

### "Battery critically low, shutting down"
- Charge the battery immediately
- Check battery connections
- Verify battery capacity setting

### "Display refresh failed"
- Check display connections
- Verify SPI is enabled
- Check display power

### "API rate limit exceeded"
- Wait for rate limit reset
- Check update interval settings
- Consider upgrading API plan

### "WiFi connection timeout"
- Check WiFi credentials
- Verify router is working
- Check signal strength
- Increase wifi_timeout_seconds

## Diagnostic Commands

### Client Diagnostics
```bash
# Full system check
sudo /opt/rpiweather/deploy/scripts/diagnose.sh

# Manual test run
cd /opt/rpiweather
poetry run client --config /etc/rpi-weather-display/config.yaml --debug

# Check all services
systemctl status rpi-weather-display.service
systemctl status pijuice.service
```

### Server Diagnostics
```bash
# Container logs with timestamps
docker logs -t rpi-weather-display

# Interactive shell in container
docker exec -it rpi-weather-display /bin/bash

# Test API endpoints
curl http://localhost:8000/weather
curl http://localhost:8000/memory
```

## Getting Help

If these solutions don't resolve your issue:

1. Check the [GitHub Issues](https://github.com/sjnims/rpi_weather_display/issues) for similar problems
2. Enable debug logging by setting `debug: true` in config.yaml
3. Collect logs and system information before reporting:
   ```bash
   sudo journalctl -u rpi-weather-display.service > client.log
   docker logs rpi-weather-display > server.log
   ```
4. Create a new issue with:
   - Description of the problem
   - Steps to reproduce
   - Relevant log excerpts
   - Your configuration (with API key removed)