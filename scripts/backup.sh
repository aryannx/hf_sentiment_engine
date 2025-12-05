#!/usr/bin/env bash
set -euo pipefail

TS=$(date +"%Y%m%d_%H%M%S")
DEST="backups/${TS}"
mkdir -p "${DEST}"

echo "📦 Creating backup at ${DEST}"

for path in logs reports data/raw data/cache; do
  if [ -d "$path" ]; then
    tar -czf "${DEST}/$(basename $path).tar.gz" "$path"
  fi
done

echo "✅ Backup complete"

