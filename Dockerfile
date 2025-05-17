FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false

# Install essential packages and Poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install "poetry==$POETRY_VERSION"

# Install Playwright dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libcups2 \
        libxss1 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Copy the whole project
COPY . .

# Install dependencies with Poetry
RUN poetry install --no-interaction --only main --extras server

# Install Playwright browsers for rendering
RUN poetry run playwright install chromium

# Create directories and copy configuration
RUN mkdir -p /etc/rpi-weather-display/ \
    && cp config.example.yaml /etc/rpi-weather-display/config.yaml

# Create cache directory
RUN mkdir -p /var/cache/weather-display

# Expose port for the server
EXPOSE 8000

# Set entrypoint
CMD ["poetry", "run", "server", "--host", "0.0.0.0", "--config", "/etc/rpi-weather-display/config.yaml"]