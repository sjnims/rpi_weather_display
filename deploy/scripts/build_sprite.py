#!/usr/bin/env python3
"""
build_sprite.py - Combine individual SVG icons into a single <symbol> sprite.

This replaces the Node-based `svg-sprite` tool so we can drop the entire
npm / Node dependency chain.

Usage (from project root):

    python3 deploy/scripts/build_sprite.py
    # or customise:
    python3 deploy/scripts/build_sprite.py --src static/icons --out static/icons/sprite.svg

The script:
1. Iterates over every *.svg in the source directory.
2. Strips XML namespaces (keeps output compact and id-friendly).
3. Wraps the contents of each SVG in a <symbol> element whose `id`
   equals the original filename *without* the .svg extension.
4. Concatenates all <symbol> blocks into a single <svg> sprite that
   lives alongside the individual icons.

Resulting sprite IDs match the scheme we reference in templates:
    <use href="static/icons/sprite.svg#wi-refresh"> …
so no template changes are required.

© 2025 raspberry-pi-weather-display
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _strip_ns(tag: str) -> str:
    """Remove a namespace prefix like '{http://www.w3.org/2000/svg}'."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def build_sprite(src_dir: Path, out_path: Path, *, prefix: str = "") -> None:
    """
    Build a <symbol> sprite from all SVGs found in *src_dir*.

    Args:
        src_dir: Directory containing individual SVG files.
        out_path: Path to write the combined sprite.
        prefix: Optional string to prepend to every symbol id.
    """
    if not src_dir.is_dir():
        sys.exit(f"[sprite] ✖ Source directory not found: {src_dir}")

    symbols: list[ET.Element] = []

    for svg_file in sorted(src_dir.glob("*.svg")):
        tree = ET.parse(svg_file)
        root = tree.getroot()

        # Remove namespaces from *all* tags & attributes
        for el in root.iter():
            el.tag = _strip_ns(el.tag)
            el.attrib = {_strip_ns(k): v for k, v in el.attrib.items()}

        # Build <symbol>
        symbol = ET.Element(
            "symbol",
            {
                "id": f"{prefix}{svg_file.stem}",
                "viewBox": root.get("viewBox", "0 0 64 64"),
                "fill": "currentColor",
            },
        )
        symbol.extend(list(root))
        symbols.append(symbol)

    if not symbols:
        sys.exit(f"[sprite] ✖ No SVG files found in {src_dir}")

    sprite = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
        },
    )
    sprite.extend(symbols)

    out_path.write_text(
        ET.tostring(sprite, encoding="unicode", short_empty_elements=False),
        encoding="utf-8",
    )
    try:
        rel = out_path.relative_to(Path.cwd())
    except ValueError:
        rel = out_path
    print(f"[sprite] ✓ wrote {rel}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SVG sprite from icons directory")
    parser.add_argument(
        "--src",
        default="static/icons",
        type=str,
        help="directory containing individual SVG icons (default: static/icons)",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=str,
        help="output sprite file path (default: <src>/sprite.svg)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        type=str,
        help="optional prefix for every symbol id",
    )
    args = parser.parse_args()

    src_dir = Path(args.src)
    out_path = Path(args.out) if args.out else src_dir / "sprite.svg"

    build_sprite(src_dir, out_path, prefix=args.prefix)


if __name__ == "__main__":
    main()
