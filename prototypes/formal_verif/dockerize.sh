#!/usr/bin/env bash
# Host-side helper to build & run the BINSEC pipeline in Docker.
# Works on any host (Arch, etc.) without installing opam/binsec/lib32 locally.
#
#   ./dockerize.sh            build (if needed) + run full reproduction
#   ./dockerize.sh shell      build + drop into an interactive shell
#   ./dockerize.sh mount      run with the prototype bind-mounted (live edits)
#   ./dockerize.sh build      build the image only
#
# Uses docker if present, else podman.
set -euo pipefail
cd "$(dirname "$0")"

ENGINE="$(command -v docker || command -v podman || true)"
[ -n "$ENGINE" ] || { echo "need docker or podman on PATH" >&2; exit 1; }
IMG=formal-verif

build() { "$ENGINE" build -t "$IMG" .; }

case "${1:-run}" in
  build)  build ;;
  shell)  build; exec "$ENGINE" run --rm -it "$IMG" bash ;;
  mount)  build; exec "$ENGINE" run --rm -it -v "$PWD":/opt/formal_verif "$IMG" bash run_all.sh ;;
  run)    build; exec "$ENGINE" run --rm "$IMG" ;;
  *)      echo "usage: $0 [run|shell|mount|build]" >&2; exit 2 ;;
esac
