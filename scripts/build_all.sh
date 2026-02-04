#!/usr/bin/env bash
# build_all.sh
#
# Wrapper script to build both the standard EPUB and the Google Play version.
# Ensures both scripts are executable, then runs them in sequence.

set -euo pipefail

# Ensure build scripts are executable
chmod +x scripts/build_epub.sh scripts/build_gplay.sh

echo "==> Building standard EPUB..."
./scripts/build_epub.sh

echo "==> Building Google Play EPUB..."
./scripts/build_gplay.sh

echo "==> All builds completed successfully!"
echo "    Check the /build folder for output files."