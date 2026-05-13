#!/bin/bash
# Copy v2 build outputs to a target font directory in a host application.
#
# Usage:
#   scripts/deploy.sh /path/to/app/assets/fonts
#   SARGAM_TARGET=/path/to/app/assets/fonts scripts/deploy.sh
#
# The target directory must already exist. Only the four v2 woff/woff2 files
# are copied; nothing else in the target is touched.
set -euo pipefail

TARGET="${1:-${SARGAM_TARGET:-}}"
if [ -z "$TARGET" ]; then
  echo "Usage: $0 <target-fonts-dir>" >&2
  echo "   or: SARGAM_TARGET=<target-fonts-dir> $0" >&2
  exit 2
fi
if [ ! -d "$TARGET" ]; then
  echo "Target dir not found: $TARGET" >&2
  exit 1
fi

SOURCE="$(cd "$(dirname "$0")/.." && pwd)/out"
for f in Lato-Sargam-v2.woff2 Lato-Sargam-v2.woff Lato-Sargam-v2-Bold.woff2 Lato-Sargam-v2-Bold.woff; do
  if [ ! -f "$SOURCE/$f" ]; then
    echo "Missing build output: $SOURCE/$f — run scripts/build.py first" >&2
    exit 1
  fi
  cp "$SOURCE/$f" "$TARGET/$f"
  echo "  → $TARGET/$f"
done

echo
echo "Deployed. Restart the host app's dev server / hard-refresh to pick up the new fonts."
