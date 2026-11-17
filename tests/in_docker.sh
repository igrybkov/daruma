#!/usr/bin/env bash
# Run a command in Linux, as CI does: Ubuntu 24.04 with SDL2 and ffmpeg
# from apt. For a check that the screen tests pass on Linux too.
#
#   tests/in_docker.sh                          the golden check and the screen tests
#   tests/in_docker.sh uv run --no-sync pytest demos -k corgi
#   tests/in_docker.sh bash                     a shell
#
# The repository is mounted at /repo. Its .venv is a Docker volume, so the
# Linux environment never mixes with the host's.
# Caches (uv, Python, PlatformIO) and the build folder (DARUMA_WORK) live
# in the volume daruma-linux-cache, so a second run starts warm. Remove the
# volumes to start cold:
#
#   docker volume rm daruma-linux-cache daruma-linux-venv
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image="daruma-linux-tests:24.04"

docker build --quiet -t "$image" - >/dev/null <<'EOF'
FROM ubuntu:24.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl ffmpeg git libsdl2-dev \
 && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
ENV UV_CACHE_DIR=/cache/uv \
    UV_PYTHON_INSTALL_DIR=/cache/python \
    UV_LINK_MODE=copy \
    PLATFORMIO_CORE_DIR=/cache/platformio \
    DARUMA_WORK=/cache/work
WORKDIR /repo
EOF

if [ $# -eq 0 ]; then
  set -- bash -c 'uv sync --locked --only-group test --no-install-project \
    && uv run --no-sync pytest demos -n auto -p no:cacheprovider --basetemp="$DARUMA_WORK/pytest"'
fi

tty=()
if [ -t 0 ] && [ -t 1 ]; then tty=(-it); fi

exec docker run --rm "${tty[@]}" \
  -v "$repo:/repo" \
  -v daruma-linux-venv:/repo/.venv \
  -v daruma-linux-cache:/cache \
  "$image" "$@"
