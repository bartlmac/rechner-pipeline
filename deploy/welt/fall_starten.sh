#!/usr/bin/env bash
# Einen Fall in einer aufgestellten Welt bis zur Unterschrift des Vorstands
# vorbereiten. Zeichnet NICHTS.
#
#   deploy/welt/fall_starten.sh <welt> anlegen <fall.conf>
#       legt den Fall an (Scope bestand) und registriert die Lieferung, die
#       die Falldatei nennt. Die Falldatei wird als <welt>/fall.conf abgelegt:
#       Eine Welt fuehrt EINEN Fall. Braucht weder Mandat noch Schluessel.
#   deploy/welt/fall_starten.sh <welt> vorlage
#       stellt den Schluessel der Programmleitung bereit und erzeugt die
#       Vorlage des Fallauftrags. Wiederholbar: Nach einer Nachlieferung
#       erzeugt derselbe Aufruf die Vorlage neu.
#
# Danach: <fall>/abgeleitet/auftrag/fallauftrag.md lesen, dann zeichnet der
# Vorstand:  deploy/welt/fall_zeichnen.sh <welt> A-M6 angenommen "<begruendung>"
#
# Der Schluessel der Programmleitung: Liegt die Datei schon, wird sie benutzt;
# sonst entsteht sie in der Phase vorlage (64 zufaellige Byte, 0600, nie
# angezeigt). Er steht in keiner Ordnung (ADR-026).
#
# Falldatei (Beispiel: fall-baldrian-klv-tg2015.conf): FALLNAME, LIEFERUNG
# (Verzeichnis, relativ zum Codebaum), LIEFERDATEIEN, STICHTAG, BESCHREIBUNG,
# AUFTRAG.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; PHASE="${2:-}"; FALLDATEI="${3:-}"
[ -n "$WELT" ] && [ -n "$PHASE" ] || { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
WELT="$(realpath -m "$WELT")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
# Die Falldatei gilt relativ zum Verzeichnis des Aufrufs, nicht zum Codebaum,
# in den das Skript gleich wechselt.
[ -z "$FALLDATEI" ] || FALLDATEI="$(realpath -m "$FALLDATEI")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
EINST="$WELT/einstellungen.conf"
[ -f "$EINST" ] || { echo "HALT: $EINST fehlt — erst die Welt aufstellen (welt_aufstellen.sh)"; exit 2; }
[ -d "$BAUM/src/rechner_pipeline" ] || { echo "HALT: $BAUM ist kein Codebaum dieses Repositorys"; exit 2; }
[ -x "$PY" ] || { echo "HALT: Interpreter $PY fehlt"; exit 2; }
WELT_AUFRUF="$WELT"
# shellcheck disable=SC1090
. "$EINST"
[ "$WELT" = "$WELT_AUFRUF" ] || { echo "HALT: $EINST gehoert zur Welt $WELT, aufgerufen wurde $WELT_AUFRUF — eine verschobene oder kopierte Welt wird nicht gefuehrt"; exit 2; }
[ -d "$LINIE/ordnung" ] || { echo "HALT: Linie $LINIE nicht gefunden — erst die Welt aufstellen"; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BAUM/src"

lade_fall() {
  [ -f "$WELT/fall.conf" ] || { echo "HALT: $WELT/fall.conf fehlt — erst: fall_starten.sh <welt> anlegen <fall.conf>"; return 2; }
  # shellcheck disable=SC1091
  . "$WELT/fall.conf"
  local v
  for v in FALLNAME LIEFERUNG LIEFERDATEIEN STICHTAG BESCHREIBUNG AUFTRAG; do
    [ -n "${!v}" ] || { echo "HALT: $v fehlt in $WELT/fall.conf"; return 2; }
  done
  case "$FALLNAME" in *[!A-Za-z0-9._-]*) echo "HALT: FALLNAME: nur Buchstaben, Ziffern, Punkt und Strich"; return 2 ;; esac
  FALL="$BAUM/faelle/$FALLNAME"
  case "$LIEFERUNG" in /*) ;; *) LIEFERUNG="$BAUM/$LIEFERUNG" ;; esac
  LOG="$WELT/fall.log"
}

schritt() {  # schritt <name> <kommando...>: faehrt, protokolliert, haelt bei Exit != 0
  local name="$1"; shift
  { echo "### $(date -u +%Y-%m-%dT%H:%M:%SZ) $name"; echo "\$ $*"; } >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "HALT bei '$name' (Exit $rc) — siehe $LOG"; tail -c 700 "$LOG"; return 1; fi
  echo "ok   $name"
}

phase_anlegen() {
  [ -n "$FALLDATEI" ] && [ -f "$FALLDATEI" ] || { echo "Aufruf: fall_starten.sh <welt> anlegen <fall.conf>"; return 2; }
  [ ! -e "$WELT/fall.conf" ] || { echo "HALT: diese Welt fuehrt schon einen Fall ($WELT/fall.conf) — je Fall eine eigene Welt"; return 2; }
  cp "$FALLDATEI" "$WELT/fall.conf" || return 2
  lade_fall || { rm -f "$WELT/fall.conf"; return 2; }
  if [ -e "$FALL" ]; then rm -f "$WELT/fall.conf"; echo "HALT: $FALL liegt schon — ein Fall wird nie ueberschrieben"; return 2; fi
  local f
  for f in $LIEFERDATEIEN; do
    [ -f "$LIEFERUNG/$f" ] || { rm -f "$WELT/fall.conf"; echo "HALT: $LIEFERUNG/$f fehlt"; return 2; }
  done
  mkdir -p "$(dirname "$FALL")" || return 2
  echo "Fall $FALL, Code $(git -C "$BAUM" rev-parse --short=12 HEAD), Linie $LINIE" | tee -a "$LOG"
  schritt "Fall anlegen (Scope bestand)" "$PY" -m rechner_pipeline.fall anlegen --fall "$FALL" --scope bestand \
      --beschreibung "$BESCHREIBUNG" || return 1
  for f in $LIEFERDATEIEN; do
    schritt "registrieren $f" "$PY" -m rechner_pipeline.fall registrieren --fall "$FALL" --datei "$LIEFERUNG/$f" || return 1
  done
  schritt "Status des Falls" "$PY" -m rechner_pipeline.fall status --fall "$FALL" || return 1
  echo "FALL LIEGT: $FALL ($(ls "$FALL/eingang" | wc -l) Dateien im Eingang). Nichts beauftragt, nichts gezeichnet." | tee -a "$LOG"
}

phase_vorlage() {
  lade_fall || return
  local v
  for v in ORDNUNG MANDAT_FALL PROGRAMMLEITUNG_KEY PROGRAMMLEITUNG_KLASSE; do
    [ -n "${!v}" ] || { echo "HALT: $v fehlt in $EINST"; return 2; }
  done
  [ -d "$FALL/eingang" ] || { echo "HALT: $FALL liegt nicht — erst die Phase anlegen"; return 2; }
  [ -f "$ORDNUNG" ] || { echo "HALT: Ordnung $ORDNUNG nicht gefunden"; return 2; }
  [ -f "$MANDAT_FALL" ] || { echo "HALT: Mandat $MANDAT_FALL nicht gefunden — sein Hash geht in die Vorlage"; return 2; }
  if [ ! -e "$PROGRAMMLEITUNG_KEY" ]; then
    (umask 077; head -c 64 /dev/urandom > "$PROGRAMMLEITUNG_KEY") || { echo "HALT: Schluessel der Programmleitung nicht anlegbar"; return 1; }
    echo "ok   Schluessel der Programmleitung erzeugt: $PROGRAMMLEITUNG_KEY (Fingerabdruck $(sha256sum "$PROGRAMMLEITUNG_KEY" | cut -c1-16))" | tee -a "$LOG"
  else
    echo "ok   Schluessel der Programmleitung liegt schon: $PROGRAMMLEITUNG_KEY" | tee -a "$LOG"
  fi
  local mandate=() rolle
  for rolle in mensch/aktuariat mensch/architektur mensch/betrieb mensch/rechenkern; do
    mandate+=(--mandat "$rolle=$MANDAT_FALL")
  done
  [ "$PROGRAMMLEITUNG_KLASSE" = simulation ] && mandate+=(--mandat "mensch/programmleitung=$MANDAT_FALL")
  schritt "Vorlage des Fallauftrags" "$PY" -m rechner_pipeline.gates.fall_belegen auftrag --fall "$FALL" \
      --linie "$LINIE" --zeichnungsordnung "$ORDNUNG" \
      --programmleitung-schluessel "$PROGRAMMLEITUNG_KEY" --programmleitung-klasse "$PROGRAMMLEITUNG_KLASSE" \
      "${mandate[@]}" --auftrag "$AUFTRAG" || return 1
  echo "VORLAGE LIEGT: $FALL/abgeleitet/auftrag/fallauftrag.md — lesen, dann zeichnet der Vorstand A-M6." | tee -a "$LOG"
}

cd "$BAUM" || exit 2
case "$PHASE" in
  anlegen) phase_anlegen ;;
  vorlage) phase_vorlage ;;
  *) echo "Aufruf: fall_starten.sh <welt> anlegen <fall.conf> | vorlage"; exit 2 ;;
esac
