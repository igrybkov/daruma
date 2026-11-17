#!/bin/sh
# Prepares a CI checkout for an ESPHome build of the examples.
#
#   .github/scripts/prepare-build.sh
#
# It writes examples/secrets.yaml from secrets.example.yaml with an API key,
# and names the checked-out commit "ci-head", so the examples can fetch
# this checkout as their git package:
#
#   esphome -s daruma_url "file://$PWD" -s daruma_ref ci-head compile examples/box3.yaml
#
# The Wi-Fi keys stay placeholders. Never flash a build made this way.
# Outside CI it keeps an existing secrets.yaml and stops.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [ -e "$ROOT/examples/secrets.yaml" ] && [ -z "${CI:-}" ]; then
  echo "examples/secrets.yaml exists. Move it away first." >&2
  exit 1
fi
# In CI the key is the same on every run: it is compiled into main.cpp, and
# with a new key each time the compiler cache could never reuse that file.
# It is public, which is fine for a build nobody flashes. Elsewhere it is
# random.
if [ -n "${CI:-}" ]; then
  key=$(printf 'daruma ci build' | openssl dgst -sha256 -binary | openssl base64)
else
  key=$(openssl rand -base64 32)
fi
sed "s|^daruma_api_key:.*|daruma_api_key: \"$key\"|" \
  "$ROOT/examples/secrets.example.yaml" > "$ROOT/examples/secrets.yaml"
git -C "$ROOT" branch -f ci-head HEAD
