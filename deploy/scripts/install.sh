#!/usr/bin/env bash
# E‑Ink Weather Display — unattended installer for Raspberry Pi OS (Bookworm)
#
# One‑liner:
#   curl -sSL https://raw.githubusercontent.com/sjnims/raspberry-pi-weather-display/main/deploy/scripts/install.sh | bash
#
# The script:
#   • installs Python 3.11 + Poetry
#   • clones the repository and installs dependencies via Poetry
#   • deploys /etc/systemd/system/rpi-weather-display.service
#   • applies power‑saving tweaks via the optimize-power.sh script
#   • reboots once everything is configured
set -euo pipefail

readonly REPO="sjnims/rpi_weather_display"
readonly VERSION="${VERSION:-latest}"
readonly INSTALL_DIR="/opt/rpiweather"
readonly VENV_DIR="${INSTALL_DIR}/venv"
readonly SERVICE_FILE="/etc/systemd/system/rpi-weather-display.service"

info()  { echo -e "\e[32m[install]\e[0m $1"; }
warn()  { echo -e "\e[33m[install]\e[0m $1"; }

###############################################################################
# 1. Ensure Python 3.11 and system packages                                   #
###############################################################################
info "Updating apt & installing base packages"
sudo apt-get update -qq
sudo apt-get install -y python3.11 git wget wkhtmltopdf cpufrequtils iw

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
  sudo -u rpiweather curl -sSL https://install.python-poetry.org | python3 -
  export PATH="/home/rpiweather/.local/bin:$PATH"

  sudo -u rpiweather git clone https://github.com/${REPO}.git "$INSTALL_DIR"
  cd "$INSTALL_DIR"
  sudo -u rpiweather poetry config virtualenvs.in-project true
  sudo -u rpiweather poetry install --no-root
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
sudo bash "${INSTALL_DIR}/deploy/scripts/optimize-power.sh"

###############################################################################
# 6. Done                                                                     #
###############################################################################
info "Installation complete. Rebooting…"
sudo reboot