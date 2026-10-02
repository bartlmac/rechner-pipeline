#!/usr/bin/env bash
# Ein Gate des Falls einer Welt zeichnen — mit dem Ring, den das Gate braucht
# (ADR-026: welches Gate welche Schluessel liest).
#
#   deploy/welt/fall_zeichnen.sh <welt> ring <gate>
#       gibt die Argumente aus (--linie, --zeichnungsordnung, Ring, --mandat),
#       etwa fuer ontologie.entscheide oder ein Betriebskommando
#   deploy/welt/fall_zeichnen.sh <welt> <gate> angenommen|abgelehnt "<begruendung>" [weitere Argumente]
#       zeichnet das Gate im Fall (gates.gate_entscheid)
#
# Schluessel werden nur als PFAD gereicht. Der LETZTE Schluessel im Ring
# zeichnet; davor stehen die Schluessel, gegen die das Gate fremde Ketten
# prueft — immer der des Vorstands (Fallauftrag A-M6 und Glieder der Linie).
#
# Der Entscheider-Text kommt aus ENTSCHEIDER der Einstellungen oder der
# Umgebung des Aufrufs (ENTSCHEIDER="..." fall_zeichnen.sh ...); die Rolle
# haengt das Skript an. Die Rolle selbst bestimmt das Gate aus dem Schluessel,
# nicht aus diesem Text.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; AUFRUF_ENTSCHEIDER="${ENTSCHEIDER:-}"
[ -n "$WELT" ] && [ -n "${2:-}" ] || { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
WELT="$(realpath -m "$WELT")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
EINST="$WELT/einstellungen.conf"
[ -f "$EINST" ] && [ -f "$WELT/fall.conf" ] || { echo "HALT: $EINST oder $WELT/fall.conf fehlt — Welt aufstellen, dann Fall anlegen"; exit 2; }
# shellcheck disable=SC1090,SC1091
. "$EINST"; . "$WELT/fall.conf"
[ -n "$AUFRUF_ENTSCHEIDER" ] && ENTSCHEIDER="$AUFRUF_ENTSCHEIDER"
for v in FALLNAME LINIE ORDNUNG MANDAT_FALL VORSTAND_KEY AKTUARIAT_KEY ARCHITEKTUR_KEY RECHENKERN_KEY BETRIEB_MENSCH_KEY PROGRAMMLEITUNG_KEY ENTSCHEIDER; do
  [ -n "${!v}" ] || { echo "HALT: $v fehlt in den Einstellungen der Welt"; exit 2; }
done
FALL="$BAUM/faelle/$FALLNAME"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BAUM/src"

rolle_von() {
  case "$1" in
    A-M6) echo mensch/vorstand ;;
    A-Q1|A-M1|A-M2|A-M3|A-M4|A-T1) echo mensch/aktuariat ;;
    A-O1) echo mensch/architektur ;;
    A-K2) echo mensch/rechenkern ;;
    A-B1|A-B2) echo mensch/betrieb ;;
    A-M5) echo mensch/programmleitung ;;
    *) return 1 ;;
  esac
}

ring_von() {  # die Schluesseldateien in der Reihenfolge des Rings; der letzte zeichnet
  case "$1" in
    A-M6) echo "$VORSTAND_KEY" ;;
    A-Q1|A-M1|A-M2|A-M3|A-T1) echo "$VORSTAND_KEY $AKTUARIAT_KEY" ;;
    A-O1) echo "$VORSTAND_KEY $ARCHITEKTUR_KEY" ;;
    A-K2) echo "$VORSTAND_KEY $RECHENKERN_KEY" ;;
    A-B1) echo "$VORSTAND_KEY $BETRIEB_MENSCH_KEY" ;;
    # A-M4 liest A-Q1, A-M1 bis A-M3 und die Standabnahmen (A-K2, A-O1, A-T1,
    # im Fall oder als Verweis auf die Linie): alle vier Rollen im Ring.
    A-M4) echo "$VORSTAND_KEY $RECHENKERN_KEY $ARCHITEKTUR_KEY $AKTUARIAT_KEY" ;;
    A-B2) echo "$VORSTAND_KEY $AKTUARIAT_KEY $BETRIEB_MENSCH_KEY" ;;
    # A-M5 liest die A-M4-Kette, sobald eine im Fall liegt (auch abgelehnt).
    A-M5) if ls "$FALL/entscheide"/A-M4-*.json >/dev/null 2>&1; then
            echo "$VORSTAND_KEY $AKTUARIAT_KEY $PROGRAMMLEITUNG_KEY"
          else echo "$VORSTAND_KEY $PROGRAMMLEITUNG_KEY"; fi ;;
    *) return 1 ;;
  esac
}

ring_argumente() {
  local k; for k in $(ring_von "$1"); do
    [ -f "$k" ] || { echo "HALT: Schluesseldatei $k nicht gefunden" >&2; return 1; }
    printf -- '--freigabe-schluessel %s ' "$k"
  done
}

if [ "$2" = ring ]; then
  GATE="${3:-}"; rolle_von "$GATE" >/dev/null || { echo "HALT: unbekanntes Gate $GATE"; exit 2; }
  R="$(ring_argumente "$GATE")" || exit 2
  echo "--linie $LINIE --zeichnungsordnung $ORDNUNG $R--mandat $MANDAT_FALL"
  exit 0
fi

GATE="$2"; ENTSCHEID="${3:-}"; BEGRUENDUNG="${4:-}"
ROLLE="$(rolle_von "$GATE")" || { echo "HALT: unbekanntes Gate $GATE"; exit 2; }
case "$ENTSCHEID" in angenommen|abgelehnt) ;; *) echo "HALT: Entscheid muss angenommen oder abgelehnt sein"; exit 2 ;; esac
[ -n "$BEGRUENDUNG" ] || { echo "HALT: Begruendung fehlt"; exit 2; }
shift 4
R="$(ring_argumente "$GATE")" || exit 2
[ -f "$MANDAT_FALL" ] || { echo "HALT: Mandat $MANDAT_FALL nicht gefunden"; exit 2; }
[ -d "$FALL" ] || { echo "HALT: der Fall $FALL liegt nicht"; exit 2; }
ZUSATZ=(); [ "$ENTSCHEID" = abgelehnt ] && ZUSATZ=(--rolle "$ROLLE")

cd "$BAUM" || exit 2
echo "Zeichne $GATE ($ENTSCHEID) als $ROLLE — Entscheider: $ENTSCHEIDER, als $ROLLE"
# shellcheck disable=SC2086
exec "$PY" -m rechner_pipeline.gates.gate_entscheid --fall "$FALL" --linie "$LINIE" --gate "$GATE" \
  --entscheid "$ENTSCHEID" --entscheider "$ENTSCHEIDER, als $ROLLE" --begruendung "$BEGRUENDUNG" \
  --repo-root "$BAUM" --zeichnungsordnung "$ORDNUNG" $R --mandat "$MANDAT_FALL" "${ZUSATZ[@]}" "$@"
