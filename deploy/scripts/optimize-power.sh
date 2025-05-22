#!/usr/bin/env bash
# Ultra-Low-Power Optimization Script for Raspberry Pi Weather Display
# Targets 60-90 day battery life on PiJuice 12,000 mAh battery
#
# This script applies aggressive power optimizations including:
# - CPU frequency and governor adjustments
# - Disabling unused hardware (HDMI, Bluetooth, LEDs)
# - WiFi power saving modes
# - Service disabling
# - Memory optimizations via tmpfs
#
# Usage: sudo ./optimize-power.sh

set -euo pipefail

# Ensure running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

echo "Applying comprehensive power optimizations for maximum battery life..."

###############################################################################
# 1. CPU and Performance Optimizations                                        #
###############################################################################
echo "1. Applying CPU optimizations..."

# Set CPU governor to powersave (immediate effect)
echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# Set maximum CPU frequency to 700 MHz (immediate effect)
echo 700000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Make CPU settings persistent across reboots
echo 'GOVERNOR="powersave"' > /etc/default/cpufrequtils

# Ensure cpufrequtils service is enabled
systemctl enable --now cpufrequtils.service

# Apply boot config changes for permanent effect
CONFIG=/boot/config.txt
apply_once() { grep -qF "$1" "$CONFIG" || echo "$1" | tee -a "$CONFIG" >/dev/null; }

apply_once "# Weather display power optimization settings"
apply_once "arm_freq=700"              # Limit ARM CPU frequency
apply_once "arm_freq_min=700"          # Set minimum to same as max to prevent scaling

# Enable SPI for Waveshare e-paper display
apply_once "dtparam=spi=on"            # Enable SPI interface
apply_once "dtoverlay=spi0-hw-cs"      # Hardware chip select for SPI0

# Disable CPU cores if it's a multi-core system (Zero 2 W has 4 cores)
# This is aggressive, but for a device that's mostly sleeping, we can use just one core
for i in /sys/devices/system/cpu/cpu[1-3]; do
    if [[ -d "$i" ]]; then
        echo 0 > "$i/online" 2>/dev/null || true
    fi
done

###############################################################################
# 2. Hardware Power Savings                                                   #
###############################################################################
echo "2. Applying hardware power optimizations..."

# HDMI (immediate effect and boot config)
/usr/bin/tvservice -o
apply_once "dtparam=hdmi_force_hotplug=0"  # Don't detect HDMI on boot

# Bluetooth
rfkill block bluetooth  # Immediate effect
apply_once "dtoverlay=disable-bt"  # Permanent at boot

# Disable onboard LEDs
for led in led0 led1; do
    if [[ -d "/sys/class/leds/$led" ]]; then
        echo 0 > "/sys/class/leds/$led/brightness"
    fi
done

# Make LED settings persistent
apply_once "dtparam=act_led_trigger=none"
apply_once "dtparam=act_led_activelow=on"
apply_once "dtparam=pwr_led_trigger=none"
apply_once "dtparam=pwr_led_activelow=on"

# Disable USB controller when not needed (this can be risky if using USB devices)
# Uncomment only if you're confident you don't need USB
# echo 0 > /sys/devices/platform/soc/3f980000.usb/buspower

###############################################################################
# 3. WiFi Power Optimizations                                                 #
###############################################################################
echo "3. Applying WiFi power optimizations..."

# Enable WiFi power saving mode (immediate effect)
iw dev wlan0 set power_save on
iw dev wlan0 set ps_timeout 30

# Create service for WiFi power saving at boot
cat <<'EOF' > /etc/systemd/system/wifi-powersave.service
[Unit]
Description=Enable WiFi APS-SD power save
After=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/sbin/iw dev wlan0 set power_save on && /sbin/iw dev wlan0 set ps_timeout 30'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wifi-powersave.service

# Add WiFi sleep script to disable when not in use
cat <<'EOF' > /usr/local/bin/wifi-sleep.sh
#!/bin/bash
# Toggle WiFi on/off - use with: wifi-sleep.sh on|off
if [ "$1" = "off" ]; then
    rfkill block wifi
    echo "WiFi disabled"
elif [ "$1" = "on" ]; then
    rfkill unblock wifi
    sleep 3
    # Re-apply power saving
    /sbin/iw dev wlan0 set power_save on
    echo "WiFi enabled with power saving"
fi
EOF
chmod +x /usr/local/bin/wifi-sleep.sh

###############################################################################
# 4. Filesystem and Memory Optimizations                                      #
###############################################################################
echo "4. Applying filesystem optimizations..."

# Configure tmpfs to reduce SD card wear
for mount_point in "/var/log" "/tmp"; do
    size="20m"
    if [ "$mount_point" = "/tmp" ]; then size="50m"; fi

    if ! grep -q "$mount_point tmpfs" /etc/fstab; then
        echo "tmpfs $mount_point tmpfs defaults,noatime,nosuid,size=$size 0 0" >> /etc/fstab
        echo "Added tmpfs mount for $mount_point"
    fi
done

# Enable ZRAM for swap compression (better than SD card swapping)
if ! grep -q "zram" /etc/modules; then
    echo "zram" >> /etc/modules
    echo "options zram num_devices=1" > /etc/modprobe.d/zram.conf
    echo "KERNEL==\"zram0\", ATTR{disksize}=\"32M\",TAG+=\"systemd\"" > /etc/udev/rules.d/99-zram.rules
    echo "KERNEL==\"zram0\", ACTION==\"add\", RUN+=\"/sbin/mkswap /dev/zram0\"" >> /etc/udev/rules.d/99-zram.rules
    echo "/dev/zram0 none swap defaults 0 0" >> /etc/fstab
    echo "Configured ZRAM for memory optimization"
fi

# Disable swap on SD card to reduce wear
swapoff -a 2>/dev/null || true
systemctl mask swap.target

# Set vm swappiness to reduce memory swapping
echo "vm.swappiness = 10" > /etc/sysctl.d/98-swappiness.conf

###############################################################################
# 5. Disable Unnecessary Services                                             #
###############################################################################
echo "5. Disabling unnecessary services..."

# Services that are likely unnecessary for a headless weather display
SERVICES_TO_DISABLE=(
    "bluetooth.service"
    "hciuart.service"
    "triggerhappy.service"
    "avahi-daemon.service"
    "dhcpcd.service"      # Only if you use static IP
    "apt-daily.service"
    "apt-daily.timer"
    "apt-daily-upgrade.service"
    "apt-daily-upgrade.timer"
    "systemd-timesyncd.service"  # NTP - adjust if time accuracy is important
    "dphys-swapfile.service"
)

for service in "${SERVICES_TO_DISABLE[@]}"; do
    if systemctl is-enabled "$service" &>/dev/null; then
        systemctl disable "$service"
        systemctl stop "$service" 2>/dev/null || true
        echo "Disabled $service"
    fi
done

###############################################################################
# 6. PiJuice-specific Optimizations (if detected)                             #
###############################################################################
echo "6. Checking for PiJuice-specific optimizations..."

if [ -e /usr/bin/pijuice_cli ] || [ -d /home/pi/.local/lib/python*/dist-packages/pijuice ]; then
    echo "PiJuice detected, applying additional optimizations"

    # Configure wakeup alarms for power cycling
    # This requires the PiJuice software to be installed
    if command -v pijuice_cli >/dev/null; then
        # Set system task to halt system on low battery (prevents deep discharge)
        pijuice_cli --set-sys-task-parameters 'LOW_CHARGE,HALT,5' || true
        echo "Configured PiJuice to halt system when battery charge is very low"

        # Configure system to shut down cleanly on power button press
        pijuice_cli --set-button-functions 'SW1,SINGLE_PRESS,SYSDOWN,180' || true
        echo "Configured power button to trigger shutdown"
    fi
fi

###############################################################################
# 7. Kernel Parameter Optimizations                                           #
###############################################################################
echo "7. Applying kernel parameter optimizations..."

# Create sysctl configuration file
cat <<'EOF' > /etc/sysctl.d/99-power-savings.conf
# Reduce disk IO activity
vm.dirty_writeback_centisecs = 6000
vm.dirty_expire_centisecs = 6000
vm.dirty_ratio = 40
vm.dirty_background_ratio = 20

# Disable IPv6 if not needed
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1

# CPU power saving
kernel.nmi_watchdog = 0
EOF

# Apply new sysctl settings
sysctl -p /etc/sysctl.d/99-power-savings.conf

###############################################################################
# Complete                                                                    #
###############################################################################
echo "Power optimizations complete! The system should now consume significantly less power."
echo "For best results, reboot the system to apply all changes: sudo reboot"