#!/usr/bin/env bash
# Der Zugang eines abgenommenen Falls in die Ablage seiner Welt (ADR-022;
# Bedienfolge: plv/betrieb/README.md, "Reihenfolge des Hochziehens").
#
#   werkzeuge/welt/zugang.sh <welt> probe
#       leeres Verzeichnis mit der Config des Falls, Zugangsprobe (zwei Laeufe
#       vom Betriebsbeginn ueber den Stichtag), Beleg im Fall
#   -> Beleg lesen (<fall>/abgeleitet/berichte/zugangsprobe.json), dann
#      werkzeuge/welt/fall_zeichnen.sh <welt> A-B2 angenommen "<begruendung>"
#   werkzeuge/welt/zugang.sh <welt> aufsetzen
#       Ablage der Welt neu aufsetzen: Die bisherige (ohne den uebernommenen
#       Bestand) wird zu daten.archiv-<zeit> und bleibt der Vergleichsstand
#   werkzeuge/welt/zugang.sh <welt> aufbau [<heute>]
#       Aufbaulauf vom Betriebsbeginn bis heute
#   werkzeuge/welt/zugang.sh <welt> belegen
#       Anfangsbestand der neuen Ablage belegen
#   -> Beleg lesen (<linie>/abgeleitet/anfangsbestand/beleg.md), dann
#   werkzeuge/welt/zugang.sh <welt> ab3 "<begruendung>"     A-B3 in der Linie zeichnen
#   werkzeuge/welt/zugang.sh <welt> binden                  Anfangsbestand binden, Tageslauf
#
# Jeder Schritt haelt beim ersten Fehler an und schreibt nach <welt>/zugang.log.
# Zwischen Probe und Aufbaulauf darf sich das Paket nicht bewegen (Config,
# Kernversion und Fingerabdruck des Pakets werden beim ersten Lauf, der den
# Eingang fuehrt, gegen die Probe gehalten). Mit dem Bestand der Vorfuehrung
# rechnet die Probe rund 20 Minuten, der Aufbaulauf rund 11.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; PHASE="${2:-}"; AUFRUF_ENTSCHEIDER="${ENTSCHEIDER:-}"
[ -n "$WELT" ] && [ -n "$PHASE" ] || { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
WELT="$(realpath -m "$WELT")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
EINST="$WELT/einstellungen.conf"
[ -f "$EINST" ] && [ -f "$WELT/fall.conf" ] || { echo "HALT: $EINST oder $WELT/fall.conf fehlt — Welt aufstellen, dann Fall anlegen"; exit 2; }
WELT_AUFRUF="$WELT"
# shellcheck disable=SC1090,SC1091
. "$EINST"
[ "$WELT" = "$WELT_AUFRUF" ] || { echo "HALT: $EINST gehoert zur Welt $WELT, aufgerufen wurde $WELT_AUFRUF — eine verschobene oder kopierte Welt wird nicht gefuehrt"; exit 2; }
. "$WELT/fall.conf"
[ -n "$AUFRUF_ENTSCHEIDER" ] && ENTSCHEIDER="$AUFRUF_ENTSCHEIDER"
for v in FALLNAME LINIE ORDNUNG MANDAT_FALL STICHTAG BETRIEB_KEY VORSTAND_KEY AKTUARIAT_KEY BETRIEB_MENSCH_KEY ENTSCHEIDER; do
  [ -n "${!v}" ] || { echo "HALT: $v fehlt in den Einstellungen der Welt"; exit 2; }
done
for k in BETRIEB_KEY VORSTAND_KEY AKTUARIAT_KEY BETRIEB_MENSCH_KEY ORDNUNG MANDAT_FALL; do
  [ -f "${!k}" ] || { echo "HALT: ${!k} ($k) nicht gefunden"; exit 2; }
done
FALL="$BAUM/faelle/$FALLNAME"
D="$WELT/daten"; LOG="$WELT/zugang.log"
CONFIG="$BAUM/plv/configs/bestand_gesamt.toml"  # die Config des Falls: mit der Generation des Zugangs
PROBE="$WELT/zugangsprobe"                      # leeres Verzeichnis, nur configs/bestand.toml
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BAUM/src"

[ -z "$(git -C "$BAUM" status --porcelain)" ] || { echo "HALT: der Codebaum $BAUM ist nicht sauber"; exit 2; }
ls "$FALL/entscheide"/A-M4-*.json >/dev/null 2>&1 || { echo "HALT: im Fall liegt keine Migrationsabnahme A-M4"; exit 2; }
cd "$BAUM" || exit 2

schritt() {  # schritt <name> <kommando...>: faehrt, protokolliert, haelt bei Exit != 0
  local name="$1"; shift
  { echo "### $(date -u +%Y-%m-%dT%H:%M:%SZ) $name"; echo "\$ $*"; } >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "HALT bei '$name' (Exit $rc) — siehe $LOG"; tail -c 900 "$LOG"; return 1; fi
  echo "ok   $name"
}

RING_PROBE=(--freigabe-schluessel "$VORSTAND_KEY" --freigabe-schluessel "$AKTUARIAT_KEY")
RING_BETRIEB=(--freigabe-schluessel "$VORSTAND_KEY" --freigabe-schluessel "$AKTUARIAT_KEY" --freigabe-schluessel "$BETRIEB_MENSCH_KEY")
RING_LINIE=(--freigabe-schluessel "$VORSTAND_KEY" --freigabe-schluessel "$BETRIEB_MENSCH_KEY")

case "$PHASE" in
  probe)
    [ ! -e "$PROBE" ] || { echo "HALT: $PROBE liegt schon — fuer eine neue Probe unter anderem Namen ablegen"; exit 1; }
    mkdir -p "$PROBE/configs" && cp "$CONFIG" "$PROBE/configs/bestand.toml" || exit 1
    echo "Zugangsprobe: Code $(git -C "$BAUM" rev-parse --short=12 HEAD), Config $(sha256sum "$CONFIG" | cut -c1-16), Stichtag $STICHTAG" | tee -a "$LOG"
    schritt "Zugangsprobe auf der leeren Ablage mit der Config des Falls" "$PY" -m rechner_pipeline.betrieb.zugangsprobe \
        --stand "$PROBE" --fall "$FALL" --stichtag "$STICHTAG" --schluessel "$BETRIEB_KEY" \
        --zeichnungsordnung "$ORDNUNG" "${RING_PROBE[@]}" --linie "$LINIE" || exit 1
    echo "BELEG: $FALL/abgeleitet/berichte/zugangsprobe.json — lesen, dann A-B2 zeichnen (fall_zeichnen.sh)."
    ;;
  aufsetzen)
    ls "$FALL/entscheide"/A-B2-*.json >/dev/null 2>&1 || { echo "HALT: im Fall liegt keine Zugangsabnahme A-B2"; exit 1; }
    schritt "Ablage neu aufsetzen (die bisherige wird Archiv)" "$PY" -m rechner_pipeline.betrieb.neuaufsetzen \
        --stand "$D" --fall "$FALL" --stichtag "$STICHTAG" --config "$CONFIG" "${RING_BETRIEB[@]}" \
        --betriebsschluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" --linie "$LINIE" || exit 1
    ls -d "$WELT"/daten* | tee -a "$LOG"
    ;;
  aufbau)
    HEUTE="${3:-$(date +%F)}"
    schritt "Aufbaulauf vom Betriebsbeginn bis $HEUTE" "$PY" -m rechner_pipeline.betrieb.tageslauf \
        --stand "$D" --heute "$HEUTE" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" || exit 1
    echo "Abschluesse: $(ls "$D/abschluesse" | wc -l), juengster $(ls "$D/abschluesse" | tail -1)" | tee -a "$LOG"
    ;;
  belegen)
    schritt "Anfangsbestand belegen" "$PY" -m rechner_pipeline.betrieb.anfangsbestand belegen --stand "$D" --linie "$LINIE" \
        --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" || exit 1
    echo "BELEG: $LINIE/abgeleitet/anfangsbestand/beleg.md — lesen, dann: zugang.sh <welt> ab3 \"<begruendung>\""
    ;;
  ab3)
    BEGRUENDUNG="${3:-}"; [ -n "$BEGRUENDUNG" ] || { echo "HALT: Begruendung fehlt"; exit 2; }
    schritt "A-B3 zeichnen (als mensch/betrieb)" "$PY" -m rechner_pipeline.gates.gate_entscheid --linie "$LINIE" --gate A-B3 \
        --entscheid angenommen --entscheider "$ENTSCHEIDER, als mensch/betrieb" --begruendung "$BEGRUENDUNG" \
        --repo-root "$BAUM" --zeichnungsordnung "$ORDNUNG" "${RING_LINIE[@]}" --mandat "$MANDAT_FALL" || exit 1
    ;;
  binden)
    schritt "Anfangsbestand binden" "$PY" -m rechner_pipeline.betrieb.anfangsbestand binden --stand "$D" --linie "$LINIE" \
        "${RING_LINIE[@]}" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" \
    && schritt "Tageslauf nach dem Binden" "$PY" -m rechner_pipeline.betrieb.tageslauf \
        --stand "$D" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" || exit 1
    echo "ZUGANG STEHT: $D — Abschluesse: $(ls "$D/abschluesse" | wc -l), juengster $(ls "$D/abschluesse" | tail -1)" | tee -a "$LOG"
    ;;
  *) echo "HALT: unbekannte Phase '$PHASE'"; exit 2 ;;
esac
