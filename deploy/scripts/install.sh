#!/usr/bin/env bash
# E-Ink Weather Display — unattended installer for Raspberry Pi OS (Bookworm)
#
# One-liner:
#   curl -sSL https://raw.githubusercontent.com/sjnims/raspberry-pi-weather-display/main/deploy/scripts/install.sh | bash
#
# The script:
#   • installs Python 3.11 + Poetry
#   • clones the repository and installs dependencies via Poetry
#   • deploys /etc/systemd/system/rpi-weather-display.service
#   • applies power-saving tweaks via the optimize-power.sh script
#   • reboots once everything is configured
set -euo pipefail

readonly REPO="sjnims/rpi_weather_display"
readonly VERSION="${VERSION:-latest}"
readonly INSTALL_DIR="/opt/rpiweather"
readonly VENV_DIR="${INSTALL_DIR}/venv"
readonly SERVICE_FILE="/etc/systemd/system/rpi-weather-display.service"
readonly POETRY_URL="https://install.python-poetry.org"
readonly POETRY_CHECKSUM_URL="https://install.python-poetry.org/checksum.txt"
readonly BACKUP_DIR="/opt/rpiweather-backup-$(date +%Y%m%d_%H%M%S)"

info()  { echo -e "\e[32m[install]\e[0m $1"; }
warn()  { echo -e "\e[33m[install]\e[0m $1"; }
error() { echo -e "\e[31m[install]\e[0m $1" >&2; }

# Cleanup function for rollback
cleanup() {
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    error "Installation failed with exit code $exit_code"
    if [[ -d "$BACKUP_DIR" ]]; then
      warn "Rolling back changes..."
      # Restore any backed up files
      if [[ -f "$BACKUP_DIR/config.txt" ]]; then
        sudo cp "$BACKUP_DIR/config.txt" /boot/config.txt
      fi
    fi
  fi
}
trap cleanup EXIT

###############################################################################
# 0. Verify prerequisites                                                     #
###############################################################################
info "Checking system prerequisites"

# Check if running on Raspberry Pi
if [[ ! -f /proc/device-tree/model ]]; then
  error "This script is designed for Raspberry Pi only"
  exit 1
fi

# Create backup directory
sudo mkdir -p "$BACKUP_DIR"

# Check required commands
REQUIRED_CMDS=("python3" "git" "curl" "systemctl")
for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "$cmd" &>/dev/null; then
    error "Required command '$cmd' not found. Please install it first."
    exit 1
  fi
done

###############################################################################
# 1. Ensure Python 3.11 and system packages                                   #
###############################################################################
info "Updating apt & installing base packages"
if ! sudo apt-get update -qq; then
  error "Failed to update package lists"
  exit 1
fi

if ! sudo apt-get install -y python3.11 git wget wkhtmltopdf cpufrequtils iw curl; then
  error "Failed to install required packages"
  exit 1
fi

###############################################################################
# 2. Create application user & folders                                        #
###############################################################################
if ! id -u rpiweather &>/dev/null; then
  info "Creating system user 'rpiweather'"
  sudo useradd -r -d "$INSTALL_DIR" -s /usr/sbin/nologin rpiweather
fi

sudo mkdir -p "$INSTALL_DIR"
sudo chown rpiweather:rpiweather "$INSTALL_DIR"

###############################################################################
# 3. Clone the repo and install via Poetry                                    #
###############################################################################
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  info "Installing Poetry and setting up environment"
  
  # Download Poetry installer to temp file
  TEMP_SCRIPT=$(mktemp)
  TEMP_CHECKSUM=$(mktemp)
  
  info "Downloading Poetry installer"
  if ! curl -sSL "$POETRY_URL" -o "$TEMP_SCRIPT"; then
    error "Failed to download Poetry installer"
    rm -f "$TEMP_SCRIPT" "$TEMP_CHECKSUM"
    exit 1
  fi
  
  # TODO: Add checksum verification when Poetry provides official checksums
  # For now, at least verify the script is not empty and contains expected content
  if [[ ! -s "$TEMP_SCRIPT" ]] || ! grep -q "poetry" "$TEMP_SCRIPT"; then
    error "Downloaded Poetry installer appears to be invalid"
    rm -f "$TEMP_SCRIPT" "$TEMP_CHECKSUM"
    exit 1
  fi
  
  # Install Poetry as rpiweather user
  if ! sudo -u rpiweather python3 "$TEMP_SCRIPT"; then
    error "Failed to install Poetry"
    rm -f "$TEMP_SCRIPT" "$TEMP_CHECKSUM"
    exit 1
  fi
  
  rm -f "$TEMP_SCRIPT" "$TEMP_CHECKSUM"
  export PATH="/home/rpiweather/.local/bin:$PATH"

  # Clone repository with verification
  info "Cloning repository"
  if ! sudo -u rpiweather git clone "https://github.com/${REPO}.git" "$INSTALL_DIR"; then
    error "Failed to clone repository"
    exit 1
  fi
  
  cd "$INSTALL_DIR"
  
  # Verify git clone succeeded
  if [[ ! -f "$INSTALL_DIR/pyproject.toml" ]]; then
    error "Repository clone appears incomplete - missing pyproject.toml"
    exit 1
  fi
  
  # Configure and install dependencies
  if ! sudo -u rpiweather poetry config virtualenvs.in-project true; then
    error "Failed to configure Poetry"
    exit 1
  fi
  
  if ! sudo -u rpiweather poetry install --no-root; then
    error "Failed to install dependencies"
    exit 1
  fi
fi

###############################################################################
# 4. Deploy systemd unit                                                      #
###############################################################################
cat <<EOF | sudo tee "$SERVICE_FILE" >/dev/null
[Unit]
Description=E-Ink Weather Display
After=network-online.target

[Service]
Type=simple
User=rpiweather
ExecStart=$INSTALL_DIR/.venv/bin/weather run --config /home/rpiweather/config.yaml
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rpi-weather-display.service

###############################################################################
# 5. Apply comprehensive power optimizations                                  #
###############################################################################
info "Applying comprehensive power optimizations"

# Verify optimize-power.sh exists and is executable
OPTIMIZE_SCRIPT="${INSTALL_DIR}/deploy/scripts/optimize-power.sh"
if [[ ! -f "$OPTIMIZE_SCRIPT" ]]; then
  error "Power optimization script not found at $OPTIMIZE_SCRIPT"
  exit 1
fi

if ! sudo bash "$OPTIMIZE_SCRIPT"; then
  warn "Power optimization script reported errors, but continuing"
fi

###############################################################################
# 6. Verify installation                                                      #
###############################################################################
info "Verifying installation"

# Check service is loaded
if ! systemctl is-enabled rpi-weather-display.service &>/dev/null; then
  error "Service failed to enable properly"
  exit 1
fi

# Check config exists
if [[ ! -f "/home/rpiweather/config.yaml" ]]; then
  warn "Configuration file not found at /home/rpiweather/config.yaml"
  warn "Please create this file before starting the service"
fi

###############################################################################
# 7. Done                                                                     #
###############################################################################
info "Installation complete!"
info "To start the service: sudo systemctl start rpi-weather-display"
info "To check status: sudo systemctl status rpi-weather-display"
info "A reboot is recommended to apply all power optimizations"
info "Run 'sudo reboot' when ready"