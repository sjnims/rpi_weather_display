"""Moon phase calculation and icon mapping utilities."""

from typing import ClassVar

from rpi_weather_display.constants import (
    MOON_PHASE_CYCLE_DAYS,
    MOON_PHASE_FIRST_QUARTER_MAX,
    MOON_PHASE_FIRST_QUARTER_MIN,
    MOON_PHASE_FULL_MAX,
    MOON_PHASE_FULL_MIN,
    MOON_PHASE_LAST_QUARTER_MAX,
    MOON_PHASE_LAST_QUARTER_MIN,
    MOON_PHASE_NEW_THRESHOLD,
)


class MoonPhaseHelper:
    """Helper class for moon phase calculations and icon mapping."""

    # Moon phase names for the 28-day cycle
    PHASE_NAMES: ClassVar[list[str]] = [
        "new",  # 0
        "waxing-crescent-1",  # 0.04
        "waxing-crescent-2",  # 0.08
        "waxing-crescent-3",  # 0.12
        "waxing-crescent-4",  # 0.16
        "waxing-crescent-5",  # 0.20
        "waxing-crescent-6",  # 0.24
        "first-quarter",  # 0.25
        "waxing-gibbous-1",  # 0.29
        "waxing-gibbous-2",  # 0.33
        "waxing-gibbous-3",  # 0.37
        "waxing-gibbous-4",  # 0.41
        "waxing-gibbous-5",  # 0.45
        "waxing-gibbous-6",  # 0.49
        "full",  # 0.5
        "waning-gibbous-1",  # 0.54
        "waning-gibbous-2",  # 0.58
        "waning-gibbous-3",  # 0.62
        "waning-gibbous-4",  # 0.66
        "waning-gibbous-5",  # 0.70
        "waning-gibbous-6",  # 0.74
        "third-quarter",  # 0.75
        "waning-crescent-1",  # 0.79
        "waning-crescent-2",  # 0.83
        "waning-crescent-3",  # 0.87
        "waning-crescent-4",  # 0.91
        "waning-crescent-5",  # 0.95
        "waning-crescent-6",  # 0.99
    ]

    # Moon phase labels
    PHASE_LABELS: ClassVar[list[str]] = [
        "New Moon",  # 0
        "Waxing Crescent",  # 0.04-0.24
        "First Quarter",  # 0.25
        "Waxing Gibbous",  # 0.29-0.49
        "Full Moon",  # 0.5
        "Waning Gibbous",  # 0.54-0.74
        "Last Quarter",  # 0.75
        "Waning Crescent",  # 0.79-0.99
    ]

    @classmethod
    def get_moon_phase_icon(cls, phase: float | None) -> str:
        """Get moon phase icon filename based on phase value (0-1).

        The phase is a floating value between 0 and 1 representing the moon cycle:
        0: New Moon
        0.25: First Quarter
        0.5: Full Moon
        0.75: Last/Third Quarter

        Alt moon icons (wi-moon-alt-*) show the shadowed part of the moon with an outline.

        Args:
            phase: Moon phase value (0-1)

        Returns:
            Classname for the matching moon phase icon
        """
        if phase is None:
            return "wi-moon-alt-new"

        index = min(int(phase * MOON_PHASE_CYCLE_DAYS), 27)  # Ensure index is within bounds
        return f"wi-moon-alt-{cls.PHASE_NAMES[index]}"

    @classmethod
    def get_moon_phase_label(cls, phase: float | None) -> str:
        """Get text label for moon phase based on phase value (0-1).

        Args:
            phase: Moon phase value (0-1)

        Returns:
            Text label describing the moon phase
        """
        if phase is None:
            return "New Moon"

        # Get the general phase category
        if phase < MOON_PHASE_NEW_THRESHOLD or phase >= (1 - MOON_PHASE_NEW_THRESHOLD):
            return cls.PHASE_LABELS[0]  # New Moon
        elif phase < MOON_PHASE_FIRST_QUARTER_MIN:
            return cls.PHASE_LABELS[1]  # Waxing Crescent
        elif phase < MOON_PHASE_FIRST_QUARTER_MAX:
            return cls.PHASE_LABELS[2]  # First Quarter
        elif phase < MOON_PHASE_FULL_MIN:
            return cls.PHASE_LABELS[3]  # Waxing Gibbous
        elif phase < MOON_PHASE_FULL_MAX:
            return cls.PHASE_LABELS[4]  # Full Moon
        elif phase < MOON_PHASE_LAST_QUARTER_MIN:
            return cls.PHASE_LABELS[5]  # Waning Gibbous
        elif phase < MOON_PHASE_LAST_QUARTER_MAX:
            return cls.PHASE_LABELS[6]  # Last Quarter
        else:
            return cls.PHASE_LABELS[7]  # Waning Crescent