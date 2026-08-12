#!/usr/bin/env bash
# Doku-Engine-Wrapper: rendert Markdown-Dokumente des Repos nach PDF (Typst).
#
#   docs/engine/render.sh [datei.md ...]
#
# Ohne Argumente werden alle Tarifplaene gerendert. Ausgaben landen neben den
# Quellen (docs/**/**.pdf, gitignored). Nutzt das ghcr-Image der Engine;
# Fallback: lokaler Build aus docs/engine/Dockerfile (IMAGE=local).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ghcr.io/bartlmac/rechner-pipeline-docs:latest}"

if [[ "$IMAGE" == "local" ]]; then
  IMAGE="rechner-pipeline-docs:local"
  docker build -q -t "$IMAGE" "$REPO_ROOT/docs/engine" >&2
fi

dateien=("$@")
if [[ ${#dateien[@]} -eq 0 ]]; then
  mapfile -t dateien < <(cd "$REPO_ROOT" && ls docs/tarifplaene/*.md)
fi

for datei in "${dateien[@]}"; do
  echo "render: $datei" >&2
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$REPO_ROOT:/workspace" -w /workspace \
    "$IMAGE" render "$datei" --to typst
done
