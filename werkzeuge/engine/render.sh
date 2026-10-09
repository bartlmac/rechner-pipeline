#!/usr/bin/env bash
# Doku-Engine-Wrapper: rendert Markdown-Dokumente des Repos nach PDF (Typst).
#
#   werkzeuge/engine/render.sh [datei.md ...]
#
# Ohne Argumente werden alle Tarifplaene gerendert; mit Argument jede
# Markdown-Datei des Repos. Ausgaben landen neben den Quellen (gitignored).
# Nutzt das ghcr-Image der Engine; Fallback: lokaler Build aus
# werkzeuge/engine/Dockerfile (IMAGE=local).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ghcr.io/bartlmac/rechner-pipeline-docs:latest}"

if [[ "$IMAGE" == "local" ]]; then
  IMAGE="rechner-pipeline-docs:local"
  docker build -q -t "$IMAGE" "$REPO_ROOT/werkzeuge/engine" >&2
fi

dateien=("$@")
if [[ ${#dateien[@]} -eq 0 ]]; then
  mapfile -t dateien < <(cd "$REPO_ROOT" && ls plv/tarifplaene/*.md)
fi

for datei in "${dateien[@]}"; do
  echo "render: $datei" >&2
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$REPO_ROOT:/workspace" -w /workspace \
    "$IMAGE" render "$datei" --to typst
done
