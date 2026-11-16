#!/bin/sh
# Builds and runs the host C++ tests. Run it from anywhere:
#
#   tests/run_cpp.sh
#
# The headers include each other as an ESPHome build sees them
# (esphome/components/<name>/...), so the tests compile against a scratch
# folder where esphome/components points at this repository's components/.
# test_frames.cpp needs a fixture; test_frames.py builds and runs it.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
mkdir -p "$OUT/include/esphome"
ln -s "$ROOT/components" "$OUT/include/esphome/components"
for test in test_agenda test_ha_calls test_input test_layout test_pomodoro_rules test_prompts \
    test_signals test_weather; do
  echo "== $test"
  c++ -std=c++17 -Wall -Wextra -I "$OUT/include" -I "$ROOT/components/daruma" \
    -I "$ROOT/components/daruma_weather" \
    "$ROOT/tests/$test.cpp" -o "$OUT/$test"
  "$OUT/$test"
done
