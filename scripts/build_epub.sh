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

TIMESTAMP="$(date '+%y%m%d%H%M')"
OUTPUT_FILE="bg_essentials_${TIMESTAMP}.epub"
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

# 2b) EPUB-only asset swaps (print keeps the CMYK original):
#     Apple Books requires RGB images; CMYK JPEGs also render broken on Kindle.
#     Guruji_epub.jpg is an RGB, web-sized derivative of Guruji_cmyk.jpg.
perl -pi -e 's|assets/imgs/Guruji_cmyk\.jpg|assets/imgs/Guruji_epub.jpg|g' "$BUILD_DIR/main.flat.tex"

# Store identifier: replace with the real ISBN (urn:isbn:978...) once assigned.
# Apple Books and KDP both accept a UUID for books without an ISBN.
BOOK_IDENTIFIER="urn:uuid:36878984-4bbb-4719-88d1-3ebbc63c1bb2"

# 3) Build EPUB (no raw_tex needed now)
#    Cover: Apple Books requires >= 1400 px on the shorter side; front_cover_epub.jpg
#    is a native 2456x4347 render of the front panel of the 2026-02-18 hardcover
#    print PDF (GGP-Hardcover, Graphic Archive volume), cropped at the spine fold.
pandoc --from=latex --to=epub3 "$BUILD_DIR/main.flat.tex" -o "$OUTPUT_PATH" \
  --toc \
  --metadata=title:"Bhagavad Gītā Essentials Second Edition" \
  --metadata=lang:en \
  --metadata=date:"March 20, 2026" \
  --metadata=author:"Bhakti Marga Publications" \
  --metadata=rights:"© 2026 Bhakti Event GmbH. All rights reserved." \
  --metadata=subject:"Hinduism" \
  --metadata=subject:"Vedānta" \
  --metadata=subject:"Bhakti" \
  --metadata=identifier:"$BOOK_IDENTIFIER" \
  --resource-path=.:./assets/imgs:./assets/fonts \
  --epub-cover-image=./assets/imgs/front_cover_epub.jpg \
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

# Indent the verse speaker lines by 1em (styled via .uvaca / .said in epub.css).
# The verse converter strips the print \hspace*{1em}, so we re-apply it here as a
# CSS class, on two lines per speaker verse:
#   - Sanskrit: an <em> line that ENDS in "uvāca" (mid-verse occurrences such as
#     "tam uvāca hṛṣīkeśaḥ" do not end the line and are left untouched).
#   - English:  the translation <p> that OPENS with "X said:" followed by a
#     <br/>. The converter emits exactly one <br/> per translation (right after
#     "said:"), so this is unambiguous; we wrap that line in a block <span> and
#     drop the now-redundant <br/> so it renders like the Sanskrit line above it.
python3 - "$TMP_DIR/EPUB/text" <<'PY'
import sys, re, pathlib
textdir = pathlib.Path(sys.argv[1])
uvaca = re.compile(r'<em>([^<]*\buvāca)\s*</em>')
said = re.compile(r'(<p>)([^<]*\b(?:said|says):)\s*<br\s*/>\s*')
uv_total = sd_total = 0
for f in sorted(textdir.glob("*.xhtml")):
    s = f.read_text(encoding="utf-8")
    s, n1 = uvaca.subn(r'<em class="uvaca">\1</em>', s)
    s, n2 = said.subn(r'\1<span class="said">\2</span>', s)
    if n1 or n2:
        f.write_text(s, encoding="utf-8")
    uv_total += n1
    sd_total += n2
print(f"    speaker lines indented: {uv_total} Sanskrit (uvāca), {sd_total} English (said:)")
PY

# Give the untitled frontmatter chapters (\chapter{} in 00_dedication.tex,
# 0_invocations.tex, and 1_copyright.tex -> ch001/ch002/ch003) their TOC labels.
# Empty TOC anchors are an epubcheck ERROR (RSC-005) and Apple Books rejects
# EPUBs that fail epubcheck.
perl -0pi -e 's|(<a href="text/ch001\.xhtml#[^"]*") */>|$1>Dedication</a>|; s|(<a href="text/ch002\.xhtml#[^"]*") */>|$1>Invocations</a>|; s|(<a href="text/ch003\.xhtml#[^"]*") */>|$1>Copyright</a>|' "$TMP_DIR/EPUB/nav.xhtml"
perl -0pi -e 's|<text></text>(\s*</navLabel>\s*<content src="text/ch001\.xhtml)|<text>Dedication</text>$1|; s|<text></text>(\s*</navLabel>\s*<content src="text/ch002\.xhtml)|<text>Invocations</text>$1|; s|<text></text>(\s*</navLabel>\s*<content src="text/ch003\.xhtml)|<text>Copyright</text>$1|' "$TMP_DIR/EPUB/toc.ncx"

# Rebuild epub from scratch: the OCF spec requires `mimetype` to be the FIRST
# zip entry and STORED (uncompressed) — hence -X0 for it, then the rest.
rm -f "$OUTPUT_PATH"
(
  cd "$TMP_DIR"
  zip -X0 "../$OUTPUT_FILE" mimetype
  zip -Xr9 "../$OUTPUT_FILE" META-INF EPUB
)

echo "==> Done"