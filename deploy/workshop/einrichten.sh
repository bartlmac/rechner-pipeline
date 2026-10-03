#!/usr/bin/env bash
# plv-einrichten — die Code-Baeume der Arbeitsumgebung anlegen und pruefen.
# Der Teil der Einrichtung, der IN der Umgebung laeuft (im Abbild als
# /usr/local/bin/plv-einrichten; Umgebung: deploy/workshop/Dockerfile).
#
#   plv-einrichten baum --quelle <url|pfad> --marke <tag|zweig>
#                       [--name rechner-pipeline] [--herkunft <url>]
#       legt ~/<name> auf der Marke an oder zieht einen unberuehrten Baum auf
#       eine neue Marke nach (Schritt "stand"), und richtet .venv ein (Schritt
#       "umgebung"): Die gepinnten Abhaengigkeiten kommen aus der Umgebung,
#       das Paket editierbar aus DIESEM Baum. Braucht ausser fuer eine
#       --quelle im Netz kein Netz. Beide Schritte sind einzeln aufrufbar:
#       plv-einrichten stand <wie baum> / plv-einrichten umgebung [--name ...]
#   plv-einrichten pruefen [--gruendlich] [--name <baum>]
#       Selbstpruefung: System, Werkzeuge und je Baum Stand, Paketherkunft,
#       Abhaengigkeiten und Referenzwerte des Rechenkerns. --gruendlich
#       faehrt je Baum die volle Suite, --name beschraenkt auf einen Baum.
#       Exit 0 = bereit, 1 = nicht bereit.
#
# Nichts wird verworfen: Ein Baum mit eigener Arbeit (nicht committet oder
# ueber die Marke hinaus committet) wird nicht nachgezogen. Das Skript haelt
# an und nennt den Ausweg.

set -u

halt() { echo "HALT: $*" >&2; exit 2; }

aufruf() {
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
  exit 2
}

stand() {
  local quelle="" marke="" name="rechner-pipeline" herkunft=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --quelle)   quelle="${2:-}";   shift 2 ;;
      --marke)    marke="${2:-}";    shift 2 ;;
      --name)     name="${2:-}";     shift 2 ;;
      --herkunft) herkunft="${2:-}"; shift 2 ;;
      *) halt "unbekanntes Argument: $1" ;;
    esac
  done
  [ -n "$quelle" ] && [ -n "$marke" ] || halt "--quelle und --marke sind Pflicht"
  case "$name" in ''|*[!A-Za-z0-9._-]*) halt "--name: nur Buchstaben, Ziffern, Punkt und Strich" ;; esac
  local ziel="$HOME/$name"

  if [ -d "$ziel/.git" ]; then
    [ -z "$(git -C "$ziel" status --porcelain)" ] \
      || halt "$ziel traegt nicht committete Arbeit — erst committen oder sichern, dann erneut aufrufen"
    # Ein Baum ohne Commit ist der Rest eines gescheiterten ersten Versuchs
    # (die Marke liess sich nicht holen): Dort gibt es nichts zu schuetzen.
    if git -C "$ziel" rev-parse -q --verify HEAD >/dev/null 2>&1; then
      [ "$(git -C "$ziel" rev-parse HEAD)" = "$(cat "$ziel/.git/plv-marke-commit" 2>/dev/null)" ] \
        || halt "$ziel steht nicht mehr auf seiner Marke (eigene Commits) — fuer eine neue Marke einen zweiten Baum anlegen (--name)"
    fi
  else
    [ -e "$ziel" ] && halt "$ziel liegt schon und ist kein Git-Baum"
    git init --quiet --initial-branch=arbeit "$ziel" || halt "git init in $ziel scheiterte"
    git -C "$ziel" config user.name "PLV Arbeitsumgebung"
    git -C "$ziel" config user.email "arbeitsumgebung@plv.invalid"
  fi

  git -C "$ziel" fetch --quiet --no-tags "$quelle" "$marke" \
    || halt "die Marke $marke liess sich aus $quelle nicht holen"
  git -C "$ziel" checkout --quiet -B arbeit FETCH_HEAD || halt "der Wechsel auf $marke scheiterte"
  # Die Quelle des Baus (etwa ein eingehaengter Pfad) ist auf dem Zielrechner
  # nicht erreichbar: origin zeigt auf die oeffentliche Herkunft, wenn sie
  # genannt ist, sonst auf die Quelle selbst, wenn sie eine URL ist.
  case "$quelle" in *://*) [ -n "$herkunft" ] || herkunft="$quelle" ;; esac
  git -C "$ziel" remote remove origin 2>/dev/null
  [ -n "$herkunft" ] && git -C "$ziel" remote add origin "$herkunft"
  local commit; commit="$(git -C "$ziel" rev-parse HEAD)"
  printf '%s\n' "$marke" > "$ziel/.git/plv-marke"
  printf '%s\n' "$commit" > "$ziel/.git/plv-marke-commit"
  echo "Stand: $ziel — Marke $marke, Commit ${commit:0:12}"
}

umgebung() {
  local name="rechner-pipeline"
  while [ $# -gt 0 ]; do
    case "$1" in
      --name) name="${2:-}"; shift 2 ;;
      --quelle|--marke|--herkunft) shift 2 ;;   # Angaben des Schritts "stand"
      *) halt "unbekanntes Argument: $1" ;;
    esac
  done
  local ziel="$HOME/$name"
  [ -f "$ziel/pyproject.toml" ] || halt "$ziel ist kein Baum dieses Repositorys (pyproject.toml fehlt)"
  # Das Paket kommt aus diesem Baum, alles andere aus der Umgebung — ohne
  # Aufloesung und ohne Netz (die Bauwerkzeuge liegen gepinnt im Image).
  # --without-pip: Ein eigenes pip braechte ein eigenes, ungepinntes
  # setuptools mit, und das stuende im Suchpfad VOR dem gepinnten der
  # Umgebung. pip selbst ist ueber die Umgebung erreichbar.
  if [ ! -x "$ziel/.venv/bin/python" ]; then
    python3 -m venv --system-site-packages --without-pip "$ziel/.venv" \
      || halt "die Umgebung $ziel/.venv liess sich nicht anlegen"
  fi
  "$ziel/.venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-cache-dir \
      --no-deps --no-index --no-build-isolation -e "$ziel" \
    || halt "das Paket liess sich nicht aus $ziel installieren"
  echo "Umgebung: $ziel/.venv — das Paket kommt aus diesem Baum"
}

pruefen() {
  local gruendlich=0 fehler=0 baeume=0 nur=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --gruendlich) gruendlich=1; shift ;;
      --name) nur="${2:-}"; shift 2 ;;
      *) halt "unbekanntes Argument: $1" ;;
    esac
  done
  zeile() { printf '  %-5s %s\n' "$1" "$2"; }
  nein()  { zeile HALT "$1"; fehler=1; }

  echo "Selbstpruefung der Arbeitsumgebung"
  # shellcheck disable=SC1091
  zeile "" "System: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unbekannt}"), $(uname -m)"
  if python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' 2>/dev/null; then
    zeile ok "Python $(python3 -c 'import platform; print(platform.python_version())')"
  else
    nein "Python 3.11 erwartet, gefunden: $(python3 -V 2>&1)"
  fi
  local w fehlend=""
  for w in git tmux watch script scriptreplay; do command -v "$w" >/dev/null 2>&1 || fehlend="$fehlend $w"; done
  if [ -z "$fehlend" ]; then zeile ok "Werkzeuge: git, tmux, watch, script, scriptreplay"; else nein "Werkzeuge fehlen:$fehlend"; fi

  local g b py marke commit ausgabe n
  for g in "$HOME"/*/.git; do
    b="$(dirname "$g")"
    [ -f "$g/plv-marke" ] && [ -f "$b/pyproject.toml" ] || continue
    [ -z "$nur" ] || [ "$(basename "$b")" = "$nur" ] || continue
    baeume=$((baeume + 1))
    marke="$(cat "$g/plv-marke")"; commit="$(git -C "$b" rev-parse HEAD 2>/dev/null)"
    py="$b/.venv/bin/python"
    echo "Baum $b"
    if [ "$commit" = "$(cat "$g/plv-marke-commit" 2>/dev/null)" ]; then
      zeile ok "Stand: Marke $marke, Commit ${commit:0:12}"
    else
      zeile "" "Stand: Commit ${commit:0:12}, ueber die Marke $marke hinaus (eigene Commits)"
    fi
    n="$(git -C "$b" status --porcelain | wc -l)"
    if [ "$n" -eq 0 ]; then zeile ok "Baum sauber"; else zeile "" "nicht committet: $n Datei(en)"; fi
    if [ ! -x "$py" ]; then nein ".venv fehlt — plv-einrichten baum erneut aufrufen"; continue; fi
    # Die Falle zweier Baeume: ein Interpreter, der das Paket still aus dem
    # anderen Baum laedt.
    if "$py" -c 'import pathlib, sys, rechner_pipeline
sys.exit(0 if pathlib.Path(rechner_pipeline.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1]).resolve()) else 1)' "$b/src" 2>/dev/null; then
      zeile ok "Paket kommt aus diesem Baum"
    else
      nein "das Paket rechner_pipeline kommt NICHT aus $b/src"
    fi
    local tests=""
    for w in tests/test_abhaengigkeiten.py tests/test_kern.py; do [ -f "$b/$w" ] && tests="$tests $w"; done
    if [ "$gruendlich" -eq 1 ]; then
      n="$(nproc 2>/dev/null || echo 4)"; [ "$n" -gt 12 ] && n=12
      echo "  volle Suite (-n $n, einige Minuten) ..."
      ausgabe="$(cd "$b" && "$py" -m pytest -q -rs -n "$n" --dist loadfile -p no:cacheprovider 2>&1)"
      if [ $? -eq 0 ]; then
        zeile ok "Suite: $(printf '%s\n' "$ausgabe" | grep -E ' passed' | tail -1)"
        printf '%s\n' "$ausgabe" | grep -E '^SKIPPED' | sed 's/^/        /'
      else
        printf '%s\n' "$ausgabe" | tail -15 | sed 's/^/        /'; nein "die Suite ist nicht gruen"; fi
    elif [ -n "$tests" ]; then
      # shellcheck disable=SC2086
      ausgabe="$(cd "$b" && "$py" -m pytest -q -p no:cacheprovider $tests 2>&1)"
      if [ $? -eq 0 ]; then zeile ok "Abhaengigkeiten geschlossen, Referenzwerte des Rechenkerns getroffen ($(printf '%s\n' "$ausgabe" | grep -E ' passed' | tail -1))"; else
        printf '%s\n' "$ausgabe" | tail -15 | sed 's/^/        /'; nein "Abhaengigkeiten oder Referenzwerte des Rechenkerns weichen ab"; fi
    else
      zeile "" "keine Pruefdateien in diesem Baum (tests/test_abhaengigkeiten.py, tests/test_kern.py)"
    fi
  done
  [ "$baeume" -gt 0 ] || nein "kein Baum${nur:+ namens $nur} unter $HOME — plv-einrichten baum aufrufen"

  if [ "$fehler" -eq 0 ]; then echo "ERGEBNIS: bereit ($baeume Baum/Baeume)"; else echo "ERGEBNIS: NICHT bereit"; fi
  return "$fehler"
}

case "${1:-}" in
  stand)    shift; stand "$@" ;;
  umgebung) shift; umgebung "$@" ;;
  baum)     shift; stand "$@" && umgebung "$@" ;;
  pruefen)  shift; pruefen "$@"; exit $? ;;
  *)        aufruf ;;
esac
