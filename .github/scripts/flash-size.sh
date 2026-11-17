#!/bin/sh
# Prints the flash use from an ESPHome compile log as a Markdown line.
#
#   .github/scripts/flash-size.sh compile.log >> "$GITHUB_STEP_SUMMARY"
set -eu
line=$(grep -E 'Flash: \[' "$1" | tail -n 1 || true)
if [ -z "$line" ]; then
  echo "Flash size: not found in the compile log."
  exit 0
fi
used=$(echo "$line" | sed -E 's/.*used ([0-9]+) bytes.*/\1/')
total=$(echo "$line" | sed -E 's/.*from ([0-9]+) bytes.*/\1/')
pct=$(echo "$line" | sed -E 's/.*\] +([0-9.]+%).*/\1/')
echo "**Flash:** $used of $total bytes ($pct of the app slot)."
