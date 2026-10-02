#!/usr/bin/env bash
# Eine Laufzeit aus einem festgehaltenen Fall aufstellen — in einem Aufruf:
# erst die Welt auf dem Stand VOR dem Fall, dann der Fall aus seinem Paket,
# bis zum Ende oder bis zu einem Haltepunkt.
#
#   deploy/welt/laufzeit_aufstellen.sh <welt> <paket> [--bis <haltepunkt>]
#
# Ein Fall, der das Zielsystem geaendert hat, braucht zwei Staende des
# Codebaums: Die Linie der Welt wird auf dem Stand abgenommen, den der Fall
# vorgefunden hat; nachgefahren wird auf dem Stand, den er hinterlassen hat —
# dem Stand dieses Baums. Den ersten nennt das Paket (Datei STAND, Zeile
# VOR=<commit>; paket_bauen.sh liest ihn aus der Linie des festgehaltenen
# Falls). Das Skript legt ihn als eigenen Baum in die Welt (<welt>/baum-vor,
# ein Klon dieses Baums auf dem Commit), stellt die Welt darauf auf
# (welt_aufstellen.sh) und faehrt danach das Paket auf diesem Baum nach
# (fall_nachfahren.sh).
#
# Wiederholbar: Steht die Welt schon (die vier Erstabnahmen liegen in der
# Linie), faehrt derselbe Aufruf nur noch das Paket weiter, hinter dem letzten
# erledigten Schritt. Ein Verzeichnis, das keine aufgestellte Welt ist, fasst
# das Skript nicht an — nach einem abgebrochenen Aufstellen beginnt ein neuer
# Versuch unter einem anderen Namen der Welt.
#
# Die Schluessel der Welt liegen, wenn SCHLUESSEL nichts anderes nennt, unter
# ~/.plv-schluessel/<name der welt>: je Welt ein eigenes Verzeichnis, damit
# ein zweiter Versuch und eine zweite Welt einander nicht im Weg stehen.
#
# Umgebung sonst wie bei welt_aufstellen.sh: MANDATGEBER, ENTSCHEIDER (nur
# beim Aufstellen), BAUM, PYTHON. Das Aufstellen rechnet einige Minuten, der
# Zugang eines Falls (Probe und Aufbaulauf) rund eine halbe Stunde.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; PAKET="${2:-}"
[ -n "$WELT" ] && [ -n "$PAKET" ] || { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
shift 2
HALT_BEI=()
while [ $# -gt 0 ]; do
  case "$1" in
    --bis) [ -n "${2:-}" ] || { echo "HALT: --bis verlangt einen Haltepunkt"; exit 2; }; HALT_BEI=(--bis "$2"); shift 2 ;;
    *) echo "HALT: unbekanntes Argument $1"; exit 2 ;;
  esac
done
halt() { echo "HALT: $*"; exit 2; }
WELT="$(realpath -m "$WELT")"; PAKET="$(realpath -m "$PAKET")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
VORBAUM="$WELT/baum-vor"
[ -d "$BAUM/src/rechner_pipeline" ] || halt "$BAUM ist kein Codebaum dieses Repositorys"
[ -x "$PY" ] || halt "Interpreter $PY fehlt — die Umgebung des Baums einrichten oder PYTHON setzen"
[ -f "$PAKET/rezept.sh" ] && [ -f "$PAKET/SHA256SUMS" ] || halt "$PAKET ist kein Paket"
[ -z "$(git -C "$BAUM" status --porcelain)" ] || halt "der Codebaum $BAUM ist nicht sauber"
case "$WELT/" in "$BAUM"/*) halt "die Welt liegt nicht im Codebaum" ;; esac

# Eine Welt steht, wenn ihre Linie die vier Erstabnahmen traegt.
steht() {
  [ "$(ls "$WELT/linie/entscheide" 2>/dev/null | sed -n 's/-[0-9a-f]\{64\}\.json$//p' | sort -u | tr '\n' ' ')" = "A-B3 A-K2 A-O1 A-T1 " ]
}

if steht; then
  echo "Die Welt $WELT steht schon — das Paket wird weitergefahren."
else
  [ ! -e "$WELT" ] || halt "$WELT liegt schon, ist aber keine aufgestellte Welt — ansehen; fuer einen neuen Versuch ein anderes Verzeichnis nennen"
  VOR="$(sed -n 's/^VOR=\([0-9a-f]\{40\}\)$/\1/p' "$PAKET/STAND" 2>/dev/null | head -1)"
  [ -n "$VOR" ] || halt "das Paket nennt den Stand nicht, auf dem die Linie seines Falls abgenommen wurde ($PAKET/STAND, Zeile VOR=<commit>) — die Welt von Hand aufstellen (welt_aufstellen.sh), dann fall_nachfahren.sh"
  git -C "$BAUM" cat-file -e "$VOR^{commit}" 2>/dev/null \
    || halt "den Stand $VOR des Pakets kennt dieser Codebaum nicht — das Paket gehoert zu einer anderen Geschichte des Repositorys"
  git -C "$BAUM" merge-base --is-ancestor "$VOR" HEAD \
    || halt "der Stand $VOR des Pakets ist kein Vorfahr dieses Baums — nachgefahren wird auf einem Stand, der aus ihm hervorgegangen ist"
  mkdir -p "$WELT" || exit 1
  git clone --quiet --no-checkout "$BAUM" "$VORBAUM" && git -C "$VORBAUM" checkout --quiet -b vor-dem-fall "$VOR" \
    || halt "der Baum auf dem Stand vor dem Fall liess sich nicht anlegen ($VORBAUM)"
  echo "Stand vor dem Fall: ${VOR:0:12} als eigener Baum unter $VORBAUM"
  BAUM="$VORBAUM" PYTHON="$PY" SCHLUESSEL="${SCHLUESSEL:-$HOME/.plv-schluessel/$(basename "$WELT")}" \
    bash "$HIER/welt_aufstellen.sh" "$WELT" || exit 1
fi

echo "Stand des Falls: $(git -C "$BAUM" rev-parse --short=12 HEAD) ($BAUM)"
BAUM="$BAUM" PYTHON="$PY" exec bash "$HIER/fall_nachfahren.sh" "$WELT" "$PAKET" "${HALT_BEI[@]}"
