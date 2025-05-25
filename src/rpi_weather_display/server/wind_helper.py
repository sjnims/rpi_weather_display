"""Wind direction and speed utilities."""

from typing import ClassVar

from rpi_weather_display.constants import (
    BEAUFORT_SCALE_DIVISOR,
    CARDINAL_DIRECTIONS_COUNT,
    DEGREES_PER_CARDINAL,
)


class WindHelper:
    """Helper class for wind-related calculations."""

    # Define the 16 cardinal directions
    CARDINAL_DIRECTIONS: ClassVar[list[str]] = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    @classmethod
    def get_beaufort_scale(cls, wind_speed: float) -> int:
        """Convert wind speed to Beaufort scale.

        Args:
            wind_speed: Wind speed in configured units

        Returns:
            Beaufort scale number (1-12)
        """
        return min(int(wind_speed / BEAUFORT_SCALE_DIVISOR) + 1, 12)

    @classmethod
    def get_wind_direction_angle(cls, degrees: float) -> float:
        """Convert wind direction to rotation angle.

        Args:
            degrees: Wind direction in degrees (0-360)

        Returns:
            Rotation angle for display
        """
        return degrees  # Pass through as is

    @classmethod
    def get_wind_direction_cardinal(cls, degrees: float) -> str:
        """Convert wind degrees to 16-point cardinal direction.

        Args:
            degrees: Wind direction in degrees (0-360)

        Returns:
            Cardinal direction as string (N, NNE, NE, etc.)
        """
        # Normalize the angle to 0-360 range
        degrees = degrees % 360

        # Calculate the index in the directions list
        # Add half of DEGREES_PER_CARDINAL to ensure proper rounding
        index = int(round(degrees / DEGREES_PER_CARDINAL)) % CARDINAL_DIRECTIONS_COUNT

        # Return the cardinal direction
        return cls.CARDINAL_DIRECTIONS[index]