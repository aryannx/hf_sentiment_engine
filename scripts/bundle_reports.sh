#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-reports}"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="reports_bundle_${STAMP}.zip"

if [ ! -d "$OUT_DIR" ]; then
  echo "Output directory not found: $OUT_DIR" >&2
  exit 1
fi

cd "$OUT_DIR"
zip -r "$ARCHIVE" investor regulatory >/dev/null
echo "Bundled reports to $OUT_DIR/$ARCHIVE"

