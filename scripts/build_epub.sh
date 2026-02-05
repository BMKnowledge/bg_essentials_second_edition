#!/usr/bin/env bash
#
# Build the EPUB using Pandoc, but first convert \Verse[...] blocks into a
# Pandoc-friendly LaTeX structure (\begin{verse} ...), so we can style verses
# reliably in EPUB (no raw HTML, no Lua).
#
# Pipeline:
#   1) latexpand main.tex -> build/main.flat.tex
#   2) convert verses in-place in build/main.flat.tex
#   3) pandoc build/main.flat.tex -> build/bg_essentials.epub
#   4) post-process nav.xhtml to remove landmarks nav

set -euo pipefail

BUILD_DIR="build"
OUTPUT_FILE="bg_essentials.epub"
OUTPUT_PATH="$BUILD_DIR/$OUTPUT_FILE"

mkdir -p "$BUILD_DIR"

echo "==> Building EPUB: $OUTPUT_PATH"

# 1) Flatten includes into a single LaTeX file (build artifact)
latexpand main.tex > "$BUILD_DIR/main.flat.tex"

# 2) Convert \Verse[...] {SA} {EN} into:
#    \par\noindent\textbf{ref}\par
#    \begin{verse}
#      \textit{...}\\
#      \textit{...}
#
#      \noindent English...
#    \end{verse}
#    \par
#
# This modifies ONLY the build artifact (safe).
python3 scripts/convert_verses.py "$BUILD_DIR/main.flat.tex" --inplace -o "$BUILD_DIR"

# 3) Build EPUB (no raw_tex needed now)
pandoc --from=latex --to=epub3 "$BUILD_DIR/main.flat.tex" -o "$OUTPUT_PATH" \
  --toc \
  --metadata=title:"Bhagavad Gītā Essentials Second Edition" \
  --metadata=lang:en \
  --metadata=date:"February 5, 2026" \
  --metadata=author:"Bhakti Marga Publications" \
  --metadata=rights:"© 2026 Bhakti Event GmbH. All rights reserved." \
  --metadata=subject:"Hinduism" \
  --metadata=subject:"Vedānta" \
  --metadata=subject:"Bhakti" \
  --metadata=identifier:"urn:isbn:YOUR-ISBN-13-HERE" \
  --resource-path=.:./assets/imgs:./assets/fonts \
  --epub-cover-image=./assets/imgs/front_cover.png \
  --metadata=cover-image:front_cover.png \
  --top-level-division=chapter \
  --split-level=1 \
  --css=default.css \
  --css=epub.css

echo "==> Successfully created $OUTPUT_PATH"


# 4) Post-process nav.xhtml to remove landmarks nav
TMP_DIR="$BUILD_DIR/epub_tmp"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

cp "$OUTPUT_PATH" "$BUILD_DIR/tmp.zip"
unzip -q "$BUILD_DIR/tmp.zip" -d "$TMP_DIR"
rm "$BUILD_DIR/tmp.zip"

# Remove the landmarks nav block (naive but usually sufficient)
perl -0pi -e 's|<nav[^>]*epub:type="landmarks"[\s\S]*?</nav>||' "$TMP_DIR/EPUB/nav.xhtml"

# Rebuild epub
(
  cd "$TMP_DIR"
  zip -Xr "../$OUTPUT_FILE" mimetype META-INF EPUB
)

echo "==> Done"