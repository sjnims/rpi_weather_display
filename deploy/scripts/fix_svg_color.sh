#!/usr/bin/env bash
# fix_svg_color.sh — ensure every paint uses currentColor
#   1. Replaces any explicit RGB/hex values with currentColor
#   2. Adds fill="currentColor" where a path/shape has no fill at all
#
# Usage: ./fix_svg_color.sh [DIR] [--dry-run]   # default: static/icons

set -euo pipefail

# Default values
SRC_DIR="static/icons"
DRY_RUN=false
BACKUP_DIR=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            # If it's not a flag, assume it's the directory
            if [[ ! "$1" =~ ^- ]]; then
                SRC_DIR="$1"
            else
                echo "Unknown option: $1"
                echo "Usage: $0 [DIR] [--dry-run]"
                exit 1
            fi
            shift
            ;;
    esac
done

# Check dependencies
if ! command -v xmlstarlet &>/dev/null; then
    echo "Error: xmlstarlet is required but not installed"
    echo "Install with: sudo apt-get install -y xmlstarlet"
    exit 1
fi

# Verify source directory exists
if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: Source directory '$SRC_DIR' not found"
    exit 1
fi

# Count SVG files
SVG_COUNT=$(find "$SRC_DIR" -type f -name '*.svg' | wc -l)
if [[ "$SVG_COUNT" -eq 0 ]]; then
    echo "Warning: No SVG files found in $SRC_DIR"
    exit 0
fi

echo "🔧  Normalising SVG colours in: $SRC_DIR"
echo "Found $SVG_COUNT SVG files to process"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN MODE] No changes will be made"
fi

# Create backup directory if not in dry-run mode
if [[ "$DRY_RUN" == "false" ]]; then
    BACKUP_DIR="${SRC_DIR}/_color_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    echo "Creating backup in $BACKUP_DIR"
fi

# A helper that adds missing fill="currentColor" via xmlstarlet
add_fill_attr () {
    local file="$1"
    local temp_file="$2"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        # In dry-run mode, just check if changes would be made
        local needs_fill
        needs_fill=$(xmlstarlet sel -t -c 'count(//*[not(@fill) and not(contains(@style,"fill"))])' "$file" 2>/dev/null || echo "0")
        if [[ "$needs_fill" != "0" ]]; then
            echo "    Would add fill=\"currentColor\" to $needs_fill elements"
        fi
    else
        # Make changes to temp file
        xmlstarlet ed \
            -a '//*[not(@fill) and not(contains(@style,"fill"))]' \
            -t attr -n fill -v 'currentColor' \
            "$file" > "$temp_file" 2>/dev/null || {
                echo "    Warning: xmlstarlet failed on $(basename "$file")"
                return 1
            }
    fi
}

# Process each SVG file
PROCESSED=0
FAILED=0
MODIFIED=0

# Use null-terminated strings to handle filenames with spaces
find "$SRC_DIR" -type f -name '*.svg' -print0 | while IFS= read -r -d '' svg; do
    fname=$(basename "$svg")
    echo " • Processing $fname"
    
    # Create backup if not in dry-run mode
    if [[ "$DRY_RUN" == "false" ]]; then
        cp "$svg" "$BACKUP_DIR/$fname"
    fi
    
    # Create temporary file for modifications
    TEMP_FILE=$(mktemp)
    cp "$svg" "$TEMP_FILE"
    
    # Track if file was modified
    FILE_MODIFIED=false
    
    # 1️⃣ Replace explicit hex/rgb values with currentColor
    if [[ "$DRY_RUN" == "true" ]]; then
        # Check if replacements would be made
        HEX_COUNT=$(grep -Eo '(fill|stroke)="\s*#[0-9a-fA-F]{3,6}\s*"' "$svg" 2>/dev/null | wc -l || echo "0")
        RGB_COUNT=$(grep -Eo '(fill|stroke)="\s*rgb[a]?\([^"]+\)\s*"' "$svg" 2>/dev/null | wc -l || echo "0")
        
        if [[ "$HEX_COUNT" -gt 0 ]]; then
            echo "    Would replace $HEX_COUNT hex color values"
            FILE_MODIFIED=true
        fi
        if [[ "$RGB_COUNT" -gt 0 ]]; then
            echo "    Would replace $RGB_COUNT rgb color values"
            FILE_MODIFIED=true
        fi
    else
        # Perform replacements
        sed -E -i \
            -e 's/(fill|stroke)="\s*#[0-9a-fA-F]{3,6}\s*"/\1="currentColor"/gI' \
            -e 's/(fill|stroke)="\s*rgb[a]?\([^"]+\)\s*"/\1="currentColor"/gI' \
            "$TEMP_FILE"
        
        # Check if file was modified
        if ! cmp -s "$svg" "$TEMP_FILE"; then
            FILE_MODIFIED=true
        fi
    fi
    
    # 2️⃣ Ensure every drawable element has an explicit fill attr
    if [[ "$DRY_RUN" == "false" ]]; then
        TEMP_FILE2=$(mktemp)
        if add_fill_attr "$TEMP_FILE" "$TEMP_FILE2"; then
            if [[ -s "$TEMP_FILE2" ]] && ! cmp -s "$TEMP_FILE" "$TEMP_FILE2"; then
                mv "$TEMP_FILE2" "$TEMP_FILE"
                FILE_MODIFIED=true
            fi
        fi
        rm -f "$TEMP_FILE2"
    else
        add_fill_attr "$svg" ""
    fi
    
    # Apply changes if not in dry-run mode
    if [[ "$DRY_RUN" == "false" ]] && [[ "$FILE_MODIFIED" == "true" ]]; then
        # Validate the modified file is not empty
        if [[ -s "$TEMP_FILE" ]]; then
            mv "$TEMP_FILE" "$svg"
            ((MODIFIED++)) || true
            echo "    ✓ Modified"
        else
            echo "    ✗ Error: Modified file is empty, keeping original"
            ((FAILED++)) || true
        fi
    elif [[ "$DRY_RUN" == "true" ]] && [[ "$FILE_MODIFIED" == "true" ]]; then
        ((MODIFIED++)) || true
    fi
    
    # Clean up temp file
    rm -f "$TEMP_FILE"
    
    ((PROCESSED++)) || true
done

# Report results
echo ""
echo "✅  Completed!"
echo "   Processed: $PROCESSED files"
echo "   Modified: $MODIFIED files"

if [[ "$FAILED" -gt 0 ]]; then
    echo "   Failed: $FAILED files"
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "This was a dry run - no changes were made"
    echo "Run without --dry-run to apply changes"
elif [[ "$MODIFIED" -gt 0 ]]; then
    echo "   Originals backed up in: $BACKUP_DIR"
fi