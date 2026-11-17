#!/bin/sh
# Writes build/clang-tidy/compile_commands.json for the host C++ tests,
# with the flags tests/conftest.py uses, so clang-tidy can read them:
#
#   tests/compile_db.sh
#   clang-tidy -p build/clang-tidy tests/test_*.cpp
#
# The headers in src/esphome/components/ come in through the tests. src/
# has the layout they include each other by (esphome/components/<name>/...).
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/build/clang-tidy"
COMPONENTS="$ROOT/src/esphome/components"
mkdir -p "$OUT"
{
  echo "["
  sep=""
  for src in "$ROOT"/tests/test_*.cpp; do
    printf '%s  {"directory": "%s", "file": "%s", "arguments": ["c++", "-std=c++17", "-Wall", "-Wextra", "-I%s", "-I%s", "-I%s", "-c", "%s"]}' \
      "$sep" "$ROOT" "$src" "$ROOT/src" "$COMPONENTS/daruma" "$COMPONENTS/daruma_weather" "$src"
    sep=",
"
  done
  echo
  echo "]"
} > "$OUT/compile_commands.json"
echo "$OUT/compile_commands.json"
