#!/bin/sh
# Einstieg der Referenzumgebung: das Paket aus dem gemounteten Baum
# editierbar installieren (ohne Aufloesung — die Abhaengigkeiten stecken
# im Image), dann das eigentliche Kommando. Die Installation landet im
# Benutzerverzeichnis des Containers (PIP_USER), nicht im Arbeitsbaum.
set -eu
if [ ! -f /workspace/pyproject.toml ]; then
    echo "rp-dev: /workspace ist kein Repo-Wurzelverzeichnis — mit -v \"\$PWD\":/workspace starten" >&2
    exit 2
fi
python -m pip install --quiet --no-deps -e /workspace
exec "$@"
