#!/usr/bin/env bash
# Doku-Engine-Wrapper: rendert Markdown-Dokumente des Repos nach PDF (Typst).
#
#   docs/engine/render.sh [datei.md ...]
#
# Ohne Argumente werden alle Tarifplaene gerendert. Mit Argument jede
# Markdown-Datei des Repos — insbesondere Bestandsberichte:
#
#   python -m rechner_pipeline.toolbox.bestand_report --format md \
#       --out output/working/bericht.md ...        # Markdown + PNG-Grafiken
#   docs/engine/render.sh output/working/bericht.md
#
# Relative Bildpfade loest Quarto relativ zur Quelldatei auf; die Grafiken
# muessen also neben dem Markdown liegen (Default von --format md).
# Ausgaben landen neben den Quellen (gitignored). Nutzt das ghcr-Image der
# Engine; Fallback: lokaler Build aus docs/engine/Dockerfile (IMAGE=local).
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
