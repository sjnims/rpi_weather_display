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
#   bash deploy/scripts/icons_build.sh [--dry-run]
# or simply:
#   ./deploy/scripts/icons_build.sh [--dry-run]       # after chmod +x
#
# The script exits on first error.

set -euo pipefail

# Parse command line arguments
DRY_RUN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

# Check dependencies
echo "[icons] Checking dependencies..."
MISSING_DEPS=()

# Check for required commands
for cmd in bash python3 inkscape xmlstarlet; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING_DEPS+=("$cmd")
    fi
done

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo "Error: Missing required dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Install missing dependencies:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y python3 inkscape xmlstarlet"
    exit 1
fi

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to root directory for consistent paths
cd "$ROOT_DIR"

# Verify required scripts exist
REQUIRED_SCRIPTS=(
    "$SCRIPT_DIR/trim_svgs.sh"
    "$SCRIPT_DIR/fix_svg_color.sh"
    "$SCRIPT_DIR/build_sprite.py"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [[ ! -f "$script" ]]; then
        echo "Error: Required script not found: $script"
        exit 1
    fi
done

# Verify source directory exists
if [[ ! -d "$ROOT_DIR/static/icons" ]]; then
    echo "Error: Icon directory not found: $ROOT_DIR/static/icons"
    exit 1
fi

# Count SVG files
SVG_COUNT=$(find "$ROOT_DIR/static/icons" -name '*.svg' -not -name 'sprite.svg' | wc -l)
if [[ "$SVG_COUNT" -eq 0 ]]; then
    echo "Warning: No SVG files found in static/icons/"
    echo "Nothing to process."
    exit 0
fi

echo "[icons] Found $SVG_COUNT SVG files to process"

if [[ -n "$DRY_RUN" ]]; then
    echo "[icons] Running in DRY RUN mode - no files will be modified"
fi

# Create a backup of the current sprite.svg if it exists and not in dry-run mode
if [[ -f "$ROOT_DIR/static/icons/sprite.svg" ]] && [[ -z "$DRY_RUN" ]]; then
    BACKUP_NAME="sprite.svg.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$ROOT_DIR/static/icons/sprite.svg" "$ROOT_DIR/static/icons/$BACKUP_NAME"
    echo "[icons] Backed up existing sprite.svg to $BACKUP_NAME"
fi

# Run the processing steps
echo ""
echo "[icons] Step 1/3: Trimming SVGs..."
if ! bash "$SCRIPT_DIR/trim_svgs.sh" $DRY_RUN; then
    echo "Error: SVG trimming failed"
    exit 1
fi

echo ""
echo "[icons] Step 2/3: Updating fill/stroke to currentColor..."
if ! bash "$SCRIPT_DIR/fix_svg_color.sh" "$ROOT_DIR/static/icons" $DRY_RUN; then
    echo "Error: Color normalization failed"
    exit 1
fi

echo ""
echo "[icons] Step 3/3: Building sprite.svg..."
if [[ -n "$DRY_RUN" ]]; then
    echo "[DRY RUN] Would run: python3 $SCRIPT_DIR/build_sprite.py --src $ROOT_DIR/static/icons"
    # Check if build_sprite.py would work
    if ! python3 "$SCRIPT_DIR/build_sprite.py" --help >/dev/null 2>&1; then
        echo "Warning: build_sprite.py appears to have issues"
    fi
else
    if ! python3 "$SCRIPT_DIR/build_sprite.py" --src "$ROOT_DIR/static/icons"; then
        echo "Error: Sprite building failed"
        exit 1
    fi
fi

echo ""
echo "[icons] ✅ All done!"

if [[ -n "$DRY_RUN" ]]; then
    echo "[icons] This was a dry run - no changes were made"
    echo "[icons] Run without --dry-run to apply changes"
else
    # Verify the sprite was created/updated
    if [[ -f "$ROOT_DIR/static/icons/sprite.svg" ]]; then
        SPRITE_SIZE=$(stat -f%z "$ROOT_DIR/static/icons/sprite.svg" 2>/dev/null || stat -c%s "$ROOT_DIR/static/icons/sprite.svg" 2>/dev/null || echo "0")
        if [[ "$SPRITE_SIZE" -gt 0 ]]; then
            echo "[icons] Successfully generated sprite.svg ($(( SPRITE_SIZE / 1024 )) KB)"
        else
            echo "Warning: sprite.svg exists but appears to be empty"
        fi
    else
        echo "Warning: sprite.svg was not created"
    fi
fi