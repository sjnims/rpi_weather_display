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
# Usage: sudo ./optimize-power.sh [--dry-run]

set -euo pipefail

# Parse command line arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

# Ensure running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Define backup directory
BACKUP_DIR="/opt/power-optimize-backup-$(date +%Y%m%d_%H%M%S)"

# Logging functions
info()  { echo -e "\e[32m[optimize]\e[0m $1"; }
warn()  { echo -e "\e[33m[optimize]\e[0m $1"; }
error() { echo -e "\e[31m[optimize]\e[0m $1" >&2; }

# Check if running on Raspberry Pi
if [[ ! -f /proc/device-tree/model ]]; then
    error "This script is designed for Raspberry Pi only"
    exit 1
fi

# Check dependencies
check_dependencies() {
    local missing_deps=()
    local deps=("iw" "rfkill" "tvservice" "systemctl")
    
    for cmd in "${deps[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        info "Install with: sudo apt-get install -y iw rfkill libraspberrypi-bin"
        exit 1
    fi
}

# Create backup
create_backup() {
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would create backup directory: $BACKUP_DIR"
        return
    fi
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup critical files
    if [[ -f /boot/config.txt ]]; then
        cp /boot/config.txt "$BACKUP_DIR/"
        info "Backed up /boot/config.txt to $BACKUP_DIR/"
    fi
    
    if [[ -f /etc/fstab ]]; then
        cp /etc/fstab "$BACKUP_DIR/"
        info "Backed up /etc/fstab to $BACKUP_DIR/"
    fi
    
    # Save current service states
    systemctl list-unit-files --state=enabled > "$BACKUP_DIR/enabled-services.txt"
    
    # Save current CPU governor and frequency
    if [[ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > "$BACKUP_DIR/cpu-governor.txt"
        cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq > "$BACKUP_DIR/cpu-max-freq.txt" 2>/dev/null || true
    fi
}

# Execute command with dry-run support
execute() {
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would execute: $*"
        return 0
    else
        "$@"
    fi
}

# Apply setting to boot config once
apply_once() {
    local setting="$1"
    local config="/boot/config.txt"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        if ! grep -qF "$setting" "$config" 2>/dev/null; then
            info "[DRY RUN] Would add to $config: $setting"
        fi
        return
    fi
    
    if ! grep -qF "$setting" "$config"; then
        echo "$setting" | tee -a "$config" >/dev/null
        info "Added to boot config: $setting"
    fi
}

info "Starting comprehensive power optimizations for maximum battery life..."

# Check dependencies
check_dependencies

# Create backup
create_backup

###############################################################################
# 1. CPU and Performance Optimizations                                        #
###############################################################################
info "1. Applying CPU optimizations..."

# Check if CPU frequency control is available
if [[ -d /sys/devices/system/cpu/cpu0/cpufreq ]]; then
    # Set CPU governor to powersave (immediate effect)
    if [[ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]]; then
        execute echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
        info "Set CPU governor to powersave"
    else
        warn "CPU governor control not available"
    fi
    
    # Set maximum CPU frequency to 700 MHz (immediate effect)
    if [[ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq ]]; then
        execute echo 700000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq
        info "Limited CPU frequency to 700 MHz"
    else
        warn "CPU frequency control not available"
    fi
else
    warn "CPU frequency scaling not available on this system"
fi

# Make CPU settings persistent across reboots
if command -v cpufrequtils &>/dev/null; then
    execute echo 'GOVERNOR="powersave"' > /etc/default/cpufrequtils
    execute systemctl enable cpufrequtils.service
    info "Configured cpufrequtils for persistent CPU settings"
fi

# Apply boot config changes for permanent effect
CONFIG=/boot/config.txt

apply_once "# Weather display power optimization settings"
apply_once "arm_freq=700"              # Limit ARM CPU frequency
apply_once "arm_freq_min=700"          # Set minimum to same as max to prevent scaling

# Enable SPI for Waveshare e-paper display
apply_once "dtparam=spi=on"            # Enable SPI interface
apply_once "dtoverlay=spi0-hw-cs"      # Hardware chip select for SPI0

# Disable CPU cores if it's a multi-core system (Zero 2 W has 4 cores)
# This is aggressive, but for a device that's mostly sleeping, we can use just one core
for i in /sys/devices/system/cpu/cpu[1-3]; do
    if [[ -d "$i" ]] && [[ -f "$i/online" ]]; then
        if execute echo 0 > "$i/online" 2>/dev/null; then
            info "Disabled CPU core: $(basename "$i")"
        fi
    fi
done

###############################################################################
# 2. Hardware Power Savings                                                   #
###############################################################################
info "2. Applying hardware power optimizations..."

# HDMI (immediate effect and boot config)
if command -v tvservice &>/dev/null; then
    execute /usr/bin/tvservice -o
    info "Disabled HDMI output"
else
    warn "tvservice not found - cannot disable HDMI"
fi

apply_once "dtparam=hdmi_force_hotplug=0"  # Don't detect HDMI on boot

# Bluetooth
if command -v rfkill &>/dev/null; then
    execute rfkill block bluetooth
    info "Disabled Bluetooth"
else
    warn "rfkill not found - cannot disable Bluetooth"
fi
apply_once "dtoverlay=disable-bt"  # Permanent at boot

# Disable onboard LEDs
for led in led0 led1; do
    if [[ -d "/sys/class/leds/$led" ]]; then
        execute echo 0 > "/sys/class/leds/$led/brightness"
        info "Disabled LED: $led"
    fi
done

# Make LED settings persistent
apply_once "dtparam=act_led_trigger=none"
apply_once "dtparam=act_led_activelow=on"
apply_once "dtparam=pwr_led_trigger=none"
apply_once "dtparam=pwr_led_activelow=on"

###############################################################################
# 3. WiFi Power Optimizations                                                 #
###############################################################################
info "3. Applying WiFi power optimizations..."

# Check if WiFi interface exists
if ip link show wlan0 &>/dev/null; then
    # Enable WiFi power saving mode (immediate effect)
    if command -v iw &>/dev/null; then
        if execute iw dev wlan0 set power_save on; then
            info "Enabled WiFi power saving"
        fi
        if execute iw dev wlan0 set ps_timeout 30; then
            info "Set WiFi power save timeout to 30ms"
        fi
    else
        warn "iw command not found - cannot configure WiFi power saving"
    fi
else
    warn "WiFi interface wlan0 not found"
fi

# Create service for WiFi power saving at boot
if [[ "$DRY_RUN" == "false" ]]; then
    cat <<'EOF' > /etc/systemd/system/wifi-powersave.service
[Unit]
Description=Enable WiFi APS-SD power save
After=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'if ip link show wlan0 >/dev/null 2>&1; then /sbin/iw dev wlan0 set power_save on && /sbin/iw dev wlan0 set ps_timeout 30; fi'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    execute systemctl daemon-reload
    execute systemctl enable wifi-powersave.service
    info "Created WiFi power save service"
fi

# Add WiFi sleep script to disable when not in use
if [[ "$DRY_RUN" == "false" ]]; then
    cat <<'EOF' > /usr/local/bin/wifi-sleep.sh
#!/bin/bash
# Toggle WiFi on/off - use with: wifi-sleep.sh on|off
if [ "$1" = "off" ]; then
    if command -v rfkill >/dev/null; then
        rfkill block wifi
        echo "WiFi disabled"
    else
        echo "rfkill not found - cannot disable WiFi"
        exit 1
    fi
elif [ "$1" = "on" ]; then
    if command -v rfkill >/dev/null; then
        rfkill unblock wifi
        sleep 3
        # Re-apply power saving
        if command -v iw >/dev/null && ip link show wlan0 >/dev/null 2>&1; then
            /sbin/iw dev wlan0 set power_save on
        fi
        echo "WiFi enabled with power saving"
    else
        echo "rfkill not found - cannot enable WiFi"
        exit 1
    fi
else
    echo "Usage: $0 on|off"
    exit 1
fi
EOF
    chmod +x /usr/local/bin/wifi-sleep.sh
    info "Created WiFi sleep control script"
fi

###############################################################################
# 4. Filesystem and Memory Optimizations                                      #
###############################################################################
info "4. Applying filesystem optimizations..."

# Configure tmpfs to reduce SD card wear
for mount_point in "/var/log" "/tmp"; do
    size="20m"
    if [ "$mount_point" = "/tmp" ]; then size="50m"; fi

    if ! grep -q "$mount_point tmpfs" /etc/fstab; then
        if [[ "$DRY_RUN" == "false" ]]; then
            echo "tmpfs $mount_point tmpfs defaults,noatime,nosuid,size=$size 0 0" >> /etc/fstab
            info "Added tmpfs mount for $mount_point"
        else
            info "[DRY RUN] Would add tmpfs mount for $mount_point"
        fi
    fi
done

# Enable ZRAM for swap compression (better than SD card swapping)
if ! grep -q "zram" /etc/modules 2>/dev/null; then
    if [[ "$DRY_RUN" == "false" ]]; then
        echo "zram" >> /etc/modules
        echo "options zram num_devices=1" > /etc/modprobe.d/zram.conf
        echo "KERNEL==\"zram0\", ATTR{disksize}=\"32M\",TAG+=\"systemd\"" > /etc/udev/rules.d/99-zram.rules
        echo "KERNEL==\"zram0\", ACTION==\"add\", RUN+=\"/sbin/mkswap /dev/zram0\"" >> /etc/udev/rules.d/99-zram.rules
        echo "/dev/zram0 none swap defaults 0 0" >> /etc/fstab
        info "Configured ZRAM for memory optimization"
    else
        info "[DRY RUN] Would configure ZRAM for memory optimization"
    fi
fi

# Disable swap on SD card to reduce wear
execute swapoff -a 2>/dev/null || true
execute systemctl mask swap.target

# Set vm swappiness to reduce memory swapping
if [[ "$DRY_RUN" == "false" ]]; then
    echo "vm.swappiness = 10" > /etc/sysctl.d/98-swappiness.conf
fi

###############################################################################
# 5. Disable Unnecessary Services                                             #
###############################################################################
info "5. Disabling unnecessary services..."

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
    if systemctl is-enabled "$service" &>/dev/null 2>&1; then
        execute systemctl disable "$service"
        execute systemctl stop "$service" 2>/dev/null || true
        info "Disabled $service"
    fi
done

###############################################################################
# 6. PiJuice-specific Optimizations (if detected)                             #
###############################################################################
info "6. Checking for PiJuice-specific optimizations..."

if command -v pijuice_cli &>/dev/null; then
    info "PiJuice detected, applying additional optimizations"

    # Configure wakeup alarms for power cycling
    # Set system task to halt system on low battery (prevents deep discharge)
    if execute pijuice_cli --set-sys-task-parameters 'LOW_CHARGE,HALT,5' 2>/dev/null; then
        info "Configured PiJuice to halt system when battery charge is very low"
    else
        warn "Failed to configure PiJuice low charge behavior"
    fi

    # Configure system to shut down cleanly on power button press
    if execute pijuice_cli --set-button-functions 'SW1,SINGLE_PRESS,SYSDOWN,180' 2>/dev/null; then
        info "Configured power button to trigger shutdown"
    else
        warn "Failed to configure PiJuice button functions"
    fi
else
    info "PiJuice CLI not found - skipping PiJuice-specific optimizations"
fi

###############################################################################
# 7. Kernel Parameter Optimizations                                           #
###############################################################################
info "7. Applying kernel parameter optimizations..."

# Create sysctl configuration file
if [[ "$DRY_RUN" == "false" ]]; then
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
    execute sysctl -p /etc/sysctl.d/99-power-savings.conf
    info "Applied kernel power saving parameters"
else
    info "[DRY RUN] Would create /etc/sysctl.d/99-power-savings.conf"
fi

###############################################################################
# Complete                                                                    #
###############################################################################
info "Power optimizations complete!"
if [[ "$DRY_RUN" == "true" ]]; then
    info "This was a dry run - no changes were made"
    info "Run without --dry-run to apply changes"
else
    info "Backup saved to: $BACKUP_DIR"
    info "The system should now consume significantly less power."
    info "For best results, reboot the system to apply all changes: sudo reboot"
fi