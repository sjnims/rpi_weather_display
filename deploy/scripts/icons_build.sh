#!/usr/bin/env bash
# icons_build.sh — Master script to regenerate the icon sprite
# Runs:
#   1. trim_svgs.sh         (remove whitespace)
#   2. fix_svg_color.sh     (fill → currentColor)
#   3. build_sprite.py      (assemble sprite.svg)
#
# All paths are resolved relative to this script location so it can be
# invoked from anywhere inside the repo.
#
# Usage:
#   bash deploy/scripts/icons_build.sh
# or simply:
#   ./deploy/scripts/icons_build.sh        # after chmod +x
#
# The script exits on first error.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[icons] Trimming SVGs …"
bash "$SCRIPT_DIR/trim_svgs.sh"

echo "[icons] Updating fill/stroke to currentColor …"
bash "$SCRIPT_DIR/fix_svg_color.sh"

echo "[icons] Building sprite.svg …"
python3 "$SCRIPT_DIR/build_sprite.py" --src "$ROOT_DIR/static/icons"

echo "[icons] All done!"