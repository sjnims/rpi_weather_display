# Ultra-Low-Power Weather Display

A power-optimized weather display solution for Raspberry Pi Zero 2 W with e-paper display.

## Features

- Ultra-low-power consumption (60-90 days battery life)
- Beautiful e-paper weather display
- Server-client architecture for minimal client power usage
- Comprehensive power management
- Weather data from OpenWeatherMap API

## Hardware Requirements

- Raspberry Pi Zero 2 W
- PiJuice Zero HAT
- PiJuice 12,000 mAh LiPo battery
- Waveshare 10.3″ 1872 x 1404 E-paper IT8951 HAT

## Server Requirements

- Docker container running on Unraid server (or any Linux server)

## Installation

### Client Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/rpi-weather-display.git
   cd rpi-weather-display