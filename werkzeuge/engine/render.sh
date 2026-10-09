#!/usr/bin/env bash
# Doku-Engine-Wrapper: rendert Markdown-Dokumente des Repos nach PDF (Typst).
#
#   werkzeuge/engine/render.sh datei.md [datei.md ...]
#
# Rendert die genannten Markdown-Dateien des Repos; Ausgaben landen neben den
# Quellen (gitignored). Fuer die PLV gibt es keine PDFs (Entscheid des
# Maintainers 2026-10-09): Grundsatzdokumentation und Tarifplaene gelten in
# ihrer Markdown-Fassung, und eine Datei neben ihnen gehoert nicht zum
# abgenommenen Gegenstand. Ohne Datei oder mit einer Datei unter plv/ haelt
# das Skript an.
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
  echo "Aufruf: werkzeuge/engine/render.sh datei.md [datei.md ...]" >&2
  exit 2
fi
for datei in "${dateien[@]}"; do
  case "$datei" in
    plv/*|./plv/*)
      echo "HALT: $datei liegt unter plv/; fuer die PLV gibt es keine PDFs, massgeblich ist die Markdown-Fassung" >&2
      exit 2 ;;
  esac
done

for datei in "${dateien[@]}"; do
  echo "render: $datei" >&2
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$REPO_ROOT:/workspace" -w /workspace \
    "$IMAGE" render "$datei" --to typst
done
