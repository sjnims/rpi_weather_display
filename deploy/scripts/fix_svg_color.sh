#!/usr/bin/env bash
# fix_svg_color.sh — ensure every paint uses currentColor
#   1. Replaces any explicit RGB/hex values with currentColor
#   2. Adds fill="currentColor" where a path/shape has no fill at all
#
# Usage: ./fix_svg_color.sh [DIR]   # default: static/icons

set -euo pipefail
SRC_DIR="${1:-static/icons}"
BACKUP_EXT=".bak"

echo "🔧  Normalising SVG colours in: $SRC_DIR"

# A helper that adds missing fill="currentColor" via xmlstarlet
add_fill_attr () {
  local file="$1"
  xmlstarlet ed -L \
    -a '//*[not(@fill) and not(contains(@style,"fill"))]' \
    -t attr -n fill -v 'currentColor' \
    "$file"
}

for svg in $(find "$SRC_DIR" -type f -name '*.svg'); do
  echo " • $(basename "$svg")"

  # 1️⃣ Replace explicit hex/rgb values with currentColor (in-place, backup *.bak)
  sed -E -i"$BACKUP_EXT" \
    -e 's/(fill|stroke)="\s*#[0-9a-fA-F]{3,6}\s*"/\1="currentColor"/gI' \
    -e 's/(fill|stroke)="\s*rgb[a]?\([^"]+\)\s*"/\1="currentColor"/gI' \
    "$svg"

  # 2️⃣ Ensure every drawable element now has an explicit fill attr
  add_fill_attr "$svg"
done

echo "✅  Completed — originals preserved as *$BACKUP_EXT"
