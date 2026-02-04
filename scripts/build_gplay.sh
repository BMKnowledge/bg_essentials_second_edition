#!/usr/bin/env bash
#
# Builds a Google Play-compatible EPUB for "Tādātmya Vedānta".
#
# This script combines several steps into one:
#   1. Builds a raw EPUB from LaTeX source using Pandoc.
#   2. Patches the EPUB's navigation file to strip embedded TOC numbers.
#   3. Uses Calibre to perform a lossy EPUB -> MOBI -> EPUB conversion
#      to fix compatibility issues with Google Play Books.
#
# All output is placed in the /build directory.
#
# Dependencies:
#   - pandoc
#   - python3
#   - calibre (for 'ebook-convert' and 'ebook-polish')

set -euo pipefail

# --- Configuration ---
BUILD_DIR="build"
RAW_EPUB="$BUILD_DIR/raw_google_play_tadatmya_vedanta.epub"
PATCHED_EPUB="$BUILD_DIR/raw_google_play_tadatmya_vedanta_patched.epub"
FINAL_EPUB="$BUILD_DIR/tadatmya_vedanta_google_play.epub"

# --- Create build directory if it doesn't exist ---
mkdir -p "$BUILD_DIR"

# --- Helper Function for Logging ---
step() {
    echo -e "\n\x1b[1m\x1b[94m━━━━━━━━━━\x1b[0m"
    echo -e "$1"
    echo -e "\x1b[1m\x1b[94m━━━━━━━━━━\x1b[0m"
}

# --- STEP 1: Build Raw EPUB with Pandoc ---
step "Building raw EPUB with Pandoc…"
pandoc main_gplay.tex -o "$RAW_EPUB" \
  --toc \
  --metadata=title:"Tādātmya Vedānta" \
  --metadata=subtitle:"A Treatise on the Philosophy of the Hari Bhakta Sampradāya" \
  --metadata=lang:en \
  --metadata=date:"August 16, 2025" \
  --metadata=author:"Bhakti Marga Publications" \
  --metadata=rights:"© 2025 Bhakti Event GmbH. All rights reserved." \
  --metadata=description:"This work presents Tādātmya Vedānta, the philosophy of the Hari Bhakta Sampradāya, founded by Paramahamsa Vishwananda. It explores the building blocks of reality and their connection, the ultimate pinnacle of spiritual attainment, as well as the path to reach it. Both a philosophical treatise and devotional offering, it is an invitation to Just Love." \
  --metadata=subject:"Hinduism" \
  --metadata=subject:"Vedānta" \
  --metadata=subject:"Bhakti" \
  --metadata=identifier:"urn:isbn:YOUR-ISBN-13-HERE" \
  --resource-path=.:./assets/imgs:./assets/fonts \
  --epub-cover-image=./assets/imgs/front_cover.png \
  --top-level-division=chapter \
  --split-level=1 \
  --lua-filter=tag-titlepages.lua \
  --lua-filter=move_table_captions.lua \
  --css=default.css \
  --css=gplay.css \
  --verbose

# --- STEP 2: Strip TOC Numbers ---
step "Stripping embedded TOC numbers (patching nav.xhtml)…"
python3 scripts/strip_toc_numbers_for_gplay.py "$RAW_EPUB"
# The strip script writes its output to "${RAW_EPUB/.epub/_gplay.epub}"
mv "${RAW_EPUB/.epub/_gplay.epub}" "$PATCHED_EPUB"

# --- STEP 3: Run Google Play Compatibility Fixer (Calibre Conversion) ---
step "Running Calibre compatibility fixer…"

# WARNING: The MOBI file format is more limited in features than an EPUB.
# WARNING: When we convert to and from this format, some data may be lost or degraded.
# WARNING: For example, images may become lower quality.

# Define temporary file paths for the conversion process
MOBI_PATH="${PATCHED_EPUB/.epub/.mobi}"
EPUB_CONVERTED="${PATCHED_EPUB/.epub/_converted.epub}"

echo "--> Converting EPUB to MOBI..."
ebook-convert "$PATCHED_EPUB" "$MOBI_PATH"

echo "--> Converting MOBI back to EPUB..."
ebook-convert "$MOBI_PATH" "$EPUB_CONVERTED"

echo "--> Upgrading and polishing final EPUB to v3..."
ebook-polish -U "$EPUB_CONVERTED" "$FINAL_EPUB"

echo "--> Removing temporary files..."
rm "$MOBI_PATH" "$EPUB_CONVERTED"

# --- Final Cleanup ---
rm "$RAW_EPUB" "$PATCHED_EPUB"

step "Build complete."
echo -e "Final file created at: \x1b[1m\x1b[92m$FINAL_EPUB\x1b[0m\n"