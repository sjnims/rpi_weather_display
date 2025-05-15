"""Minimal tests for the refactored e-paper display module.

These tests focus on the helper functions and other changes made to improve testability.
"""
# ruff: noqa: S101
# ^ Ignores "Use of assert detected" - assertions are intentionally used in tests
# pyright: reportPrivateUsage=false
# ^ Allows tests to access private methods and attributes

from unittest.mock import patch

from rpi_weather_display.client.display import (
    EPaperDisplay,
    _import_it8951,
    _import_numpy,
)
from rpi_weather_display.models.config import DisplayConfig


class TestDisplayHelpers:
    """Tests for the helper functions in display.py."""

    def test_import_it8951(self) -> None:
        """Test _import_it8951 function."""
        # Test when import fails
        with patch("builtins.__import__", side_effect=ImportError("Mocked import error")):
            assert _import_it8951() is None

    def test_import_numpy(self) -> None:
        """Test _import_numpy function."""
        # Test when import fails
        with patch("builtins.__import__", side_effect=ImportError("Mocked import error")):
            assert _import_numpy() is None

    def test_get_bbox_dimensions(self) -> None:
        """Test _get_bbox_dimensions method."""
        config = DisplayConfig(
            width=1872,
            height=1404,
            rotate=0,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        display = EPaperDisplay(config)

        # Test with numpy not available
        with patch("rpi_weather_display.client.display._import_numpy", return_value=None):
            result = display._get_bbox_dimensions(([1, 2], [3, 4]), (100, 200))
            assert result is None

    def test_initialize_refactored(self) -> None:
        """Test the refactored initialize method."""
        config = DisplayConfig(
            width=1872,
            height=1404,
            rotate=0,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        display = EPaperDisplay(config)

        # Test when _import_it8951 returns None
        with (
            patch("rpi_weather_display.client.display._import_it8951", return_value=None),
            patch("builtins.print") as mock_print,
        ):
            display.initialize()
            mock_print.assert_called_with(
                "Warning: IT8951 library not available. Using mock display."
            )
            assert not display._initialized
