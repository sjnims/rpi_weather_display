#!/usr/bin/env bash
# trim_svgs.sh — trims whitespace around every SVG in static/icons/
# Requires: Inkscape ≥ 1.2 in PATH
# Usage: ./trim_svgs.sh [--dry-run]

set -euo pipefail

# Parse command line arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
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
if ! command -v inkscape &>/dev/null; then
    echo "Error: Inkscape is required but not installed"
    echo "Install with: sudo apt-get install -y inkscape"
    exit 1
fi

# Get Inkscape version
INKSCAPE_VERSION=$(inkscape --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
MAJOR_VERSION=$(echo "$INKSCAPE_VERSION" | cut -d. -f1)
MINOR_VERSION=$(echo "$INKSCAPE_VERSION" | cut -d. -f2)

if [[ "$MAJOR_VERSION" -lt 1 ]] || [[ "$MAJOR_VERSION" -eq 1 && "$MINOR_VERSION" -lt 2 ]]; then
    echo "Error: Inkscape version 1.2 or higher is required (found $INKSCAPE_VERSION)"
    exit 1
fi

# Configuration
SRC_DIR="static/icons"
TMP_DIR="${SRC_DIR}/_trimmed_$$"  # Use PID to ensure uniqueness
BACKUP_DIR="${SRC_DIR}/_backup_$(date +%Y%m%d_%H%M%S)"

# Verify source directory exists
if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: Source directory '$SRC_DIR' not found"
    exit 1
fi

# Count SVG files
SVG_COUNT=$(find "$SRC_DIR" -maxdepth 1 -name '*.svg' -type f | wc -l)
if [[ "$SVG_COUNT" -eq 0 ]]; then
    echo "Warning: No SVG files found in $SRC_DIR"
    exit 0
fi

echo "Found $SVG_COUNT SVG files to process"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would process the following files:"
    find "$SRC_DIR" -maxdepth 1 -name '*.svg' -type f | sort
    echo "[DRY RUN] Would create temporary directory: $TMP_DIR"
    echo "[DRY RUN] Would create backup directory: $BACKUP_DIR"
    exit 0
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"
echo "Creating backup in $BACKUP_DIR"

# Backup original files
find "$SRC_DIR" -maxdepth 1 -name '*.svg' -type f -exec cp {} "$BACKUP_DIR/" \;

# Create temporary directory
mkdir -p "$TMP_DIR"

# Process each SVG file
PROCESSED=0
FAILED=0

# Use null-terminated strings to handle filenames with spaces
find "$SRC_DIR" -maxdepth 1 -name '*.svg' -type f -print0 | while IFS= read -r -d '' svg; do
    fname=$(basename "$svg")
    echo -n "Processing $fname... "
    
    if inkscape "$svg" \
        --export-area-drawing \
        --export-plain-svg \
        --export-filename="$TMP_DIR/$fname" 2>/dev/null; then
        echo "✓"
        ((PROCESSED++)) || true
    else
        echo "✗ Failed"
        ((FAILED++)) || true
    fi
done

# Check if any files were processed successfully
if [[ ! -f "$TMP_DIR"/*.svg ]] 2>/dev/null; then
    echo "Error: No files were processed successfully"
    rm -rf "$TMP_DIR"
    exit 1
fi

# Atomic replacement: move all processed files at once
echo "Replacing original files..."
for svg in "$TMP_DIR"/*.svg; do
    if [[ -f "$svg" ]]; then
        fname=$(basename "$svg")
        # Validate the processed file is not empty
        if [[ -s "$svg" ]]; then
            mv "$svg" "$SRC_DIR/$fname"
        else
            echo "Warning: Processed file $fname is empty, skipping"
            ((FAILED++)) || true
        fi
    fi
done

# Clean up temporary directory
rm -rf "$TMP_DIR"

# Report results
echo "✅ Trimming complete!"
echo "   Processed: $PROCESSED files"
if [[ "$FAILED" -gt 0 ]]; then
    echo "   Failed: $FAILED files"
    echo "   Backup preserved in: $BACKUP_DIR"
    exit 1
else
    echo "   All files processed successfully"
    echo "   Backup available in: $BACKUP_DIR"
fi