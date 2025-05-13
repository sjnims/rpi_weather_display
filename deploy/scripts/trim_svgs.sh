#!/usr/bin/env bash
# trim_svgs.sh — trims whitespace around every SVG in static/icons/
# Requires: Inkscape ≥ 1.2 in PATH

set -euo pipefail

SRC_DIR="static/icons"
TMP_DIR="${SRC_DIR}/_trimmed"

mkdir -p "$TMP_DIR"

for svg in "$SRC_DIR"/*.svg; do
  fname=$(basename "$svg")
  inkscape "$svg" \
    --export-area-drawing \
    --export-plain-svg \
    --export-filename="$TMP_DIR/$fname"
done

# Overwrite originals (backup kept by git history)
mv "$TMP_DIR"/*.svg "$SRC_DIR"/
rmdir "$TMP_DIR"

echo "✅  Trimming complete."
