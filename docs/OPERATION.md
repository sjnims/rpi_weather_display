# Operation Guide

This guide covers day-to-day operation, maintenance, and updates for the Ultra-Low-Power Weather Display.

## System Management

### Starting and Stopping

**Client (Raspberry Pi):**
```bash
# Check service status
sudo systemctl status rpi-weather-display.service

# Start the service
sudo systemctl start rpi-weather-display.service

# Stop the service
sudo systemctl stop rpi-weather-display.service

# Restart the service
sudo systemctl restart rpi-weather-display.service

# Enable auto-start on boot
sudo systemctl enable rpi-weather-display.service

# Disable auto-start
sudo systemctl disable rpi-weather-display.service
```

**Server (Docker):**
```bash
# Start the container
docker start rpi-weather-display

# Stop the container
docker stop rpi-weather-display

# Restart the container
docker restart rpi-weather-display

# View container status
docker ps -a | grep rpi-weather-display
```

### Viewing Logs

**Client Logs:**
```bash
# View recent logs
sudo journalctl -u rpi-weather-display.service -n 50

# Follow logs in real-time
sudo journalctl -u rpi-weather-display.service -f

# View logs from specific time
sudo journalctl -u rpi-weather-display.service --since "2025-05-24 10:00"

# Export logs to file
sudo journalctl -u rpi-weather-display.service > weather-display.log
```

**Server Logs:**
```bash
# View recent logs
docker logs rpi-weather-display -n 50

# Follow logs in real-time
docker logs rpi-weather-display -f

# View logs with timestamps
docker logs -t rpi-weather-display

# Export logs to file
docker logs rpi-weather-display > server.log 2>&1
```

## Update Procedures

### Client Update

1. **Stop the service:**
   ```bash
   sudo systemctl stop rpi-weather-display.service
   ```

2. **Navigate to installation directory:**
   ```bash
   cd /opt/rpiweather
   ```

3. **Create backup (optional but recommended):**
   ```bash
   sudo cp -r /opt/rpiweather /opt/rpiweather.backup
   sudo cp /etc/rpi-weather-display/config.yaml /etc/rpi-weather-display/config.yaml.backup
   ```

4. **Pull latest changes:**
   ```bash
   sudo -u rpiweather git pull
   ```

5. **Update dependencies:**
   ```bash
   sudo -u rpiweather poetry install
   ```

6. **Review configuration changes:**
   ```bash
   # Check if config.example.yaml has new options
   diff /etc/rpi-weather-display/config.yaml config.example.yaml
   ```

7. **Start the service:**
   ```bash
   sudo systemctl start rpi-weather-display.service
   ```

8. **Verify operation:**
   ```bash
   sudo journalctl -u rpi-weather-display.service -n 20
   ```

### Server Update

1. **Pull latest code:**
   ```bash
   cd /path/to/rpi-weather-display
   git pull
   ```

2. **Build new image:**
   ```bash
   docker build -t rpi-weather-display-server .
   ```

3. **Stop old container:**
   ```bash
   docker stop rpi-weather-display
   docker rm rpi-weather-display
   ```

4. **Start new container:**
   ```bash
   docker run -d \
     --name rpi-weather-display \
     -p 8000:8000 \
     -v /path/to/config.yaml:/etc/rpi-weather-display/config.yaml \
     rpi-weather-display-server
   ```

5. **Verify operation:**
   ```bash
   docker logs rpi-weather-display -n 20
   curl http://localhost:8000/
   ```

### Using Pre-built Docker Images

If using Docker Hub images:

```bash
# Pull latest image
docker pull ghcr.io/sjnims/rpi-weather-display:latest

# Run with new image
docker run -d \
  --name rpi-weather-display \
  -p 8000:8000 \
  -v /path/to/config.yaml:/etc/rpi-weather-display/config.yaml \
  ghcr.io/sjnims/rpi-weather-display:latest
```

## Configuration Management

### Modifying Configuration

1. **Edit configuration file:**
   ```bash
   # Client
   sudo nano /etc/rpi-weather-display/config.yaml

   # Server (edit local file)
   nano /path/to/config.yaml
   ```

2. **Validate configuration (optional):**
   ```bash
   # Test configuration loading
   cd /opt/rpiweather
   poetry run python -c "from rpi_weather_display.models.config import AppConfig; AppConfig.from_yaml('/etc/rpi-weather-display/config.yaml')"
   ```

3. **Restart service to apply changes:**
   ```bash
   # Client
   sudo systemctl restart rpi-weather-display.service

   # Server
   docker restart rpi-weather-display
   ```

### Common Configuration Changes

**Adjust refresh frequency:**
```yaml
display:
  refresh_interval_minutes: 60  # Update every hour instead of 30 min
```

**Change quiet hours:**
```yaml
power:
  quiet_hours_start: "22:00"  # Start quiet hours earlier
  quiet_hours_end: "07:00"    # End quiet hours later
```

**Modify battery thresholds:**
```yaml
power:
  low_battery_threshold: 25     # Trigger power saving at 25%
  critical_battery_threshold: 15 # Critical mode at 15%
```

**Change weather location:**
```yaml
weather:
  location: {"lat": 40.7128, "lon": -74.0060}  # New York
  city_name: "New York"
```

## Monitoring

### Battery Status

**Check current battery level:**
```bash
# Using PiJuice CLI
pijuice_cli --status

# From application logs
sudo journalctl -u rpi-weather-display.service | grep -i battery
```

**Monitor battery trends:**
```bash
# Create battery log
echo "timestamp,level,voltage,current,temp,state" > battery_log.csv

# Add cron job to log battery status
crontab -e
# Add: */30 * * * * /opt/rpiweather/deploy/scripts/log_battery.sh
```

### Performance Monitoring

**Client performance:**
```bash
# CPU usage
top -b -n 1 | head -20

# Memory usage
free -h

# Disk usage
df -h

# Network statistics
ip -s link show wlan0
```

**Server performance:**
```bash
# Container statistics
docker stats rpi-weather-display

# Memory profile endpoint
curl http://localhost:8000/memory

# Container resource usage over time
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" rpi-weather-display
```

## Maintenance Tasks

### Regular Maintenance

**Weekly:**
- Check battery level trends
- Review error logs for issues
- Verify display is updating correctly

**Monthly:**
- Update system packages: `sudo apt update && sudo apt upgrade`
- Check disk space: `df -h`
- Review API usage on OpenWeatherMap dashboard
- Clean up old logs if needed

**Quarterly:**
- Update application to latest version
- Review and optimize configuration
- Check hardware connections
- Clean e-paper display surface

### Cache Management

**Server cache cleanup:**
```bash
# View cache size
docker exec rpi-weather-display du -sh /tmp/weather-cache-1000

# Manual cache clear (if needed)
docker exec rpi-weather-display rm -rf /tmp/weather-cache-1000/*
docker restart rpi-weather-display
```

**Client cache cleanup:**
```bash
# Client doesn't cache by default, but if enabled:
sudo rm -rf /var/cache/rpi-weather-display/*
```

## Backup and Recovery

### Backup Procedures

**Client backup:**
```bash
# Backup configuration
sudo cp /etc/rpi-weather-display/config.yaml ~/config.yaml.backup

# Backup entire installation
sudo tar -czf rpiweather-backup.tar.gz /opt/rpiweather /etc/rpi-weather-display

# Backup to external location
scp ~/rpiweather-backup.tar.gz user@backup-server:/path/to/backups/
```

**Server backup:**
```bash
# Backup configuration
cp /path/to/config.yaml ~/config.yaml.backup

# Export Docker image
docker save rpi-weather-display-server > weather-display-image.tar

# Backup data volume (if used)
docker run --rm -v weather-data:/data -v $(pwd):/backup alpine tar czf /backup/weather-data-backup.tar.gz /data
```

### Recovery Procedures

**Client recovery:**
```bash
# Restore from backup
sudo tar -xzf rpiweather-backup.tar.gz -C /

# Reinstall service
sudo systemctl daemon-reload
sudo systemctl enable rpi-weather-display.service
sudo systemctl start rpi-weather-display.service
```

**Server recovery:**
```bash
# Load Docker image
docker load < weather-display-image.tar

# Restore configuration
cp ~/config.yaml.backup /path/to/config.yaml

# Restart container
docker run -d \
  --name rpi-weather-display \
  -p 8000:8000 \
  -v /path/to/config.yaml:/etc/rpi-weather-display/config.yaml \
  rpi-weather-display-server
```

## Advanced Operations

### Manual Testing

**Test client without service:**
```bash
cd /opt/rpiweather
sudo -u rpiweather poetry run client --config /etc/rpi-weather-display/config.yaml --debug
```

**Test server endpoints:**
```bash
# Health check
curl http://localhost:8000/

# Get weather data
curl http://localhost:8000/weather | jq

# Test render endpoint
curl -X POST http://localhost:8000/render \
  -H "Content-Type: application/json" \
  -d '{"battery":{"level":75,"state":"NORMAL","voltage":4.1,"current":0.1,"temperature":25}}' \
  -o test-image.png
```

### Debug Mode

**Enable debug logging:**
```yaml
# In config.yaml
debug: true
logging:
  level: "DEBUG"
```

**Collect debug information:**
```bash
# Create debug report
cat > debug-report.sh << 'EOF'
#!/bin/bash
echo "=== System Information ==="
uname -a
echo -e "\n=== Service Status ==="
systemctl status rpi-weather-display.service
echo -e "\n=== Recent Logs ==="
journalctl -u rpi-weather-display.service -n 50
echo -e "\n=== Configuration ==="
grep -v api_key /etc/rpi-weather-display/config.yaml
echo -e "\n=== Network Status ==="
ip addr show
ping -c 3 8.8.8.8
echo -e "\n=== PiJuice Status ==="
pijuice_cli --status
EOF

chmod +x debug-report.sh
./debug-report.sh > debug-report.txt
```

## Tips and Best Practices

1. **Monitor battery regularly** during the first few weeks to ensure expected battery life
2. **Keep logs rotated** to prevent filling up storage
3. **Document configuration changes** for easier troubleshooting
4. **Test updates** during active hours when you can monitor
5. **Keep backups** before major updates
6. **Review API usage** monthly to avoid surprises
7. **Clean display** gently with microfiber cloth only