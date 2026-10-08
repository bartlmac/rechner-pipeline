#!/usr/bin/env bash
# Einen festgehaltenen Fall in einer aufgestellten Welt nachfahren — ohne
# Agenten, Schritt fuer Schritt, bis zum Ende oder bis zu einem Haltepunkt.
#
#   werkzeuge/welt/fall_nachfahren.sh <welt> <paket> [--bis <haltepunkt>] [--wechseln]
#
# Ein festgehaltener Fall ist ein PAKET (Verzeichnis):
#   fall.conf        der Fall: Name, Lieferung, Stichtag, Auftrag (wie fuer fall_starten.sh)
#   rezept.sh        die Schritte in ihrer Reihenfolge (siehe unten)
#   erarbeitet/      was im Fall ein Agent oder ein Mensch erarbeitet hat und kein
#                    Kommando neu erzeugt — abgelegt unter demselben Pfad wie im Fall
#   nachlieferung/   was die Quelle im Lauf des Falls nachgeliefert hat
#   ERWARTUNG        "<sha256>  <pfad im fall>" je Ergebnis, das byteweise gleich sein muss
#   SHA256SUMS       Pruefsummen aller Dateien des Pakets
# Keine Schluessel, keine Zeichnungen: Gezeichnet wird beim Nachfahren neu, mit
# den Schluesseln der Welt.
#
# Im Rezept stehen NUR diese Helfer, je Zeile einer (Fortsetzungszeilen mit \);
# alles andere verweigert das Skript, bevor es beginnt:
#
#   anlegen                             Fall anlegen, Lieferung laut fall.conf registrieren
#   vorlage                             die Vorlage des Auftrags erzeugen (auch neu, nach einer Nachlieferung)
#   registriere <pfad>                  nachlieferung/<pfad> im Fall registrieren
#   einlegen <pfad>                     erarbeitet/<pfad> in den Fall legen (nie ueber anderes hinweg)
#   schritt "<name>" <kommando ...>     ein Kommando fahren; Exit != 0 haelt an
#   entscheide <diskrepanz> <wert> "<begruendung>" [--beleg <pfad>]
#                                       eine Diskrepanz der Quellen endgueltig aufloesen (als Aktuariat)
#   entscheide_alle <quelle> "<begruendung>"
#                                       alle vorlaeufig aufgeloesten zur Lesart dieser Quelle entscheiden
#   zeichne <gate> "<begruendung>"      das Gate annehmen, mit dem Ring der Welt — es sei denn, ein Mensch
#                                       hat es an einem Haltepunkt schon selbst gezeichnet (siehe unten)
#   zugang <phase> [argument]           eine Phase des Zugangs in die Ablage der Welt fahren (zugang.sh):
#                                       probe, aufsetzen, aufbau [<heute>], belegen, ab3 "<begruendung>", binden
#   haltepunkt <name>                   hier endet ein Lauf mit --bis <name>
#   erwarte <pfad im fall>              die Datei gegen ERWARTUNG halten; Abweichung haelt an
#
# In den Kommandos verfuegbar: $PY (Interpreter), $F (faelle/<name>, relativ
# zum Codebaum, in dem das Rezept laeuft), $A ($F/abgeleitet), $WELT, $LINIE,
# $ORDNUNG, $STICHTAG, $PAKET, $(ring <gate>) fuer Kommandos, die den Ring
# eines Gates brauchen, und $(abgenommen <gate>) fuer den Commit, auf dem die
# Linie der Welt das Gate zuletzt angenommen hat — das --von eines Belegs, der
# die Aenderung gegen den abgenommenen Stand zeigt. Ein Rezept nennt so keinen
# Commit der Welt, in der es festgehalten wurde.
#
# An einem Haltepunkt kann ein Mensch selbst zeichnen (fall_zeichnen.sh, fuer
# A-B3 zugang.sh ab3): Liegt die Annahme, die das Rezept als naechste leisten
# wuerde, schon im Fall, zeichnet es nicht noch einmal. Ist die juengste
# Zeichnung des Gates eine Ablehnung, haelt der Lauf — ueber eine Ablehnung
# zeichnet das Rezept nie hinweg.
#
# Ein Lauf merkt sich, wie weit er kam (<welt>/nachfahren.stand). Ein zweiter
# Aufruf faehrt hinter dem letzten erledigten Schritt weiter: nach einem
# Haltepunkt oder einem behobenen Fehler, ohne etwas doppelt zu fahren.
# Fuehrt die Welt schon einen ANDEREN Fall, haelt das Skript an; --wechseln
# legt dessen Falldatei beiseite (<welt>/fall-frueher-<name>.conf) und macht
# den nachgefahrenen Fall zum Fall der Welt. Der fruehere Fall bleibt liegen.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; PAKET="${2:-}"
[ -n "$WELT" ] && [ -n "$PAKET" ] || { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
shift 2
HALT_BEI=""; WECHSELN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --bis) HALT_BEI="${2:-}"; [ -n "$HALT_BEI" ] || { echo "HALT: --bis verlangt einen Haltepunkt"; exit 2; }; shift 2 ;;
    --wechseln) WECHSELN=1; shift ;;
    *) echo "HALT: unbekanntes Argument $1"; exit 2 ;;
  esac
done
WELT="$(realpath -m "$WELT")"; PAKET="$(realpath -m "$PAKET")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
EINST="$WELT/einstellungen.conf"; STANDDATEI="$WELT/nachfahren.stand"; LOG="$WELT/nachfahren.log"
HELFER="anlegen vorlage registriere einlegen schritt entscheide entscheide_alle zeichne zugang haltepunkt erwarte"

halt() { echo "HALT: $*"; exit 2; }
[ -f "$EINST" ] || halt "$EINST fehlt — erst die Welt aufstellen (welt_aufstellen.sh)"
for f in fall.conf rezept.sh SHA256SUMS; do [ -f "$PAKET/$f" ] || halt "$PAKET/$f fehlt — kein Paket"; done
[ -d "$BAUM/src/rechner_pipeline" ] || halt "$BAUM ist kein Codebaum dieses Repositorys"
[ -x "$PY" ] || halt "Interpreter $PY fehlt"

# Das Paket ist, was seine Pruefsummen sagen — und nichts darueber hinaus.
( cd "$PAKET" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1 ) || halt "das Paket $PAKET stimmt nicht mit seinen Pruefsummen ueberein (sha256sum -c SHA256SUMS)"
ohne="$(cd "$PAKET" && find . -type f ! -name SHA256SUMS | sed 's#^\./##' | LC_ALL=C sort | LC_ALL=C comm -23 - <(sed 's/^[0-9a-f]\{64\} [ *]//' SHA256SUMS | LC_ALL=C sort))"
[ -z "$ohne" ] || halt "im Paket liegen Dateien ohne Pruefsumme: $(echo "$ohne" | tr '\n' ' ')"
PAKET_SHA="$(sha256sum "$PAKET/SHA256SUMS" | cut -c1-64)"

# Das Rezept: nur Helfer. Freier Shell-Code liefe bei einer Fortsetzung noch einmal.
fremd="$(sed -e ':a' -e '/\\$/N; s/\\\n/ /; ta' "$PAKET/rezept.sh" | grep -v -E '^[[:space:]]*(#|$)' \
         | grep -v -E "^[[:space:]]*($(echo "$HELFER" | tr ' ' '|'))([[:space:]]|\$)" | head -3)"
[ -z "$fremd" ] || halt "im Rezept steht eine Zeile, die kein Helfer ist: $(echo "$fremd" | head -1 | cut -c1-120)"
if [ -n "$HALT_BEI" ]; then
  grep -q -E "^[[:space:]]*haltepunkt[[:space:]]+$HALT_BEI([[:space:]]|\$)" "$PAKET/rezept.sh" \
    || halt "den Haltepunkt $HALT_BEI gibt es im Rezept nicht (vorhanden: $(grep -E '^[[:space:]]*haltepunkt[[:space:]]' "$PAKET/rezept.sh" | awk '{print $2}' | tr '\n' ' '))"
fi

# Die Einstellungen der Welt setzen eigene Namen (auch BIS und VON); die Namen
# dieses Laufs (HALT_BEI, STANDDATEI, PAKET, ...) kommen darin nicht vor.
WELT_AUFRUF="$WELT"
# shellcheck disable=SC1090
. "$EINST"
[ "$WELT" = "$WELT_AUFRUF" ] || { echo "HALT: $EINST gehoert zur Welt $WELT, aufgerufen wurde $WELT_AUFRUF — eine verschobene oder kopierte Welt wird nicht gefuehrt"; exit 2; }
FALLNAME="$(. "$PAKET/fall.conf"; printf %s "${FALLNAME:-}")"
STICHTAG="$(. "$PAKET/fall.conf"; printf %s "${STICHTAG:-}")"
case "$FALLNAME" in ''|*[!A-Za-z0-9._-]*) halt "FALLNAME im Paket: nur Buchstaben, Ziffern, Punkt und Strich" ;; esac
F="faelle/$FALLNAME"; A="$F/abgeleitet"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BAUM/src"
cd "$BAUM" || exit 2

# Wie weit ein frueherer Lauf kam — nur fuer DASSELBE Paket.
ERLEDIGT=0
if [ -f "$STANDDATEI" ]; then
  read -r stand_paket stand_fall ERLEDIGT < "$STANDDATEI"
  [ "$stand_fall" = "$FALLNAME" ] && [ "$stand_paket" = "$PAKET_SHA" ] \
    || halt "$STANDDATEI gehoert zu einem anderen Paket oder Fall ($stand_fall) — eine Welt faehrt EIN Paket nach; fuer ein anderes eine andere Welt"
  case "$ERLEDIGT" in ''|*[!0-9]*) halt "$STANDDATEI ist nicht lesbar" ;; esac
fi

# Der Fall der Welt: derselbe (Fortsetzung), keiner, oder ein anderer (nur mit --wechseln).
if [ -f "$WELT/fall.conf" ]; then
  laufend="$(. "$WELT/fall.conf"; printf %s "${FALLNAME:-}")"
  if [ "$laufend" != "$FALLNAME" ]; then
    [ "$WECHSELN" -eq 1 ] || halt "die Welt fuehrt den Fall $laufend — mit --wechseln wird seine Falldatei beiseitegelegt und $FALLNAME der Fall der Welt"
    [ ! -e "$WELT/fall-frueher-$laufend.conf" ] || halt "$WELT/fall-frueher-$laufend.conf liegt schon"
    mv "$WELT/fall.conf" "$WELT/fall-frueher-$laufend.conf" || exit 1
    echo "Der Fall $laufend ist beiseitegelegt ($WELT/fall-frueher-$laufend.conf); er selbst bleibt liegen."
  fi
fi

NR=0
merke() { printf '%s %s %s\n' "$PAKET_SHA" "$FALLNAME" "$NR" > "$STANDDATEI.neu" && mv "$STANDDATEI.neu" "$STANDDATEI"; }
erledigt() {  # zaehlt den Schritt; wahr, wenn ein frueherer Lauf ihn schon gefahren hat
  NR=$((NR + 1))
  if [ "$NR" -le "$ERLEDIGT" ]; then printf '  -    %3d  %s (schon gefahren)\n' "$NR" "$1"; return 0; fi
  return 1
}
bruch() { printf '  HALT %3d  %s\n' "$NR" "$1"; echo "Nach der Behebung derselbe Aufruf: Er faehrt bei diesem Schritt weiter."; exit 1; }
fahre() {  # fahre <name> <kommando...>: protokolliert, haelt bei Exit != 0, merkt den Schritt
  local name="$1"; shift
  { echo "### $(date -u +%Y-%m-%dT%H:%M:%SZ) Schritt $NR: $name"; echo "\$ $*"; } >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then tail -c 900 "$LOG"; echo; bruch "$name (Exit $rc) — siehe $LOG"; fi
  printf '  ok   %3d  %s\n' "$NR" "$name"
  merke
}

schritt() { local name="$1"; shift; erledigt "$name" && return 0; fahre "$name" "$@"; }

anlegen() {
  erledigt "Fall anlegen, Lieferung registrieren" && return 0
  fahre "Fall anlegen, Lieferung registrieren" bash "$HIER/fall_starten.sh" "$WELT" anlegen "$PAKET/fall.conf"
}

vorlage() { erledigt "Vorlage des Auftrags" && return 0; fahre "Vorlage des Auftrags" bash "$HIER/fall_starten.sh" "$WELT" vorlage; }

registriere() {
  local rel="$1"; erledigt "registriere $rel" && return 0
  [ -f "$PAKET/nachlieferung/$rel" ] || bruch "registriere: nachlieferung/$rel liegt nicht im Paket"
  fahre "registriere $rel" "$PY" -m rechner_pipeline.fall registrieren --fall "$F" --datei "$PAKET/nachlieferung/$rel"
}

einlegen() {
  local rel="$1"; erledigt "einlegen $rel" && return 0
  [ -e "$PAKET/erarbeitet/$rel" ] || bruch "einlegen: erarbeitet/$rel liegt nicht im Paket"
  fahre "einlegen $rel" lege_ein "$PAKET/erarbeitet/$rel" "$BAUM/$F/$rel"
}
lege_ein() {  # Datei oder Verzeichnis; nie ueber eine ANDERE Datei hinweg
  local von="$1" nach="$2" d
  if [ -d "$von" ]; then
    while IFS= read -r d; do lege_ein "$von/$d" "$nach/$d" || return 1; done < <(cd "$von" && find . -type f | sed 's#^\./##' | LC_ALL=C sort)
    return 0
  fi
  if [ -e "$nach" ]; then
    cmp -s "$von" "$nach" && return 0
    echo "im Fall liegt schon eine andere Datei: $nach"; return 1
  fi
  mkdir -p "$(dirname "$nach")" && cp -p "$von" "$nach"
}

# Eine Diskrepanz wird beim Nachfahren NEU entschieden, mit dem Schluessel der
# Welt: Die Entscheidung in der A-Box traegt die Zeichnung ihrer Rolle, und
# eine mitgebrachte A-Box truege die Schluessel des festgehaltenen Laufs.
entscheide() {
  local diskrepanz="${1:-}" wert="${2:-}" grund="${3:-}"; erledigt "Diskrepanz $diskrepanz entscheiden" && return 0
  [ -n "$diskrepanz" ] && [ -n "$grund" ] || bruch "entscheide: Diskrepanz, Wert und Begruendung angeben"
  fahre "Diskrepanz $diskrepanz entscheiden" "$PY" -m rechner_pipeline.ontologie.entscheide --fall "$F" \
      --entscheider "$ENTSCHEIDER, als mensch/aktuariat" --zeichnungsordnung "$ORDNUNG" \
      --freigabe-schluessel "$AKTUARIAT_KEY" --mandat "$MANDAT_FALL" \
      --diskrepanz "$diskrepanz" --wert "$wert" --begruendung "$grund" "${@:4}"
}
entscheide_alle() {
  local quelle="${1:-}" grund="${2:-}"; erledigt "vorlaeufige Entscheide zur Lesart von $quelle" && return 0
  [ -n "$quelle" ] && [ -n "$grund" ] || bruch "entscheide_alle: Quelle und Begruendung angeben"
  fahre "vorlaeufige Entscheide zur Lesart von $quelle" "$PY" -m rechner_pipeline.ontologie.entscheide --fall "$F" \
      --entscheider "$ENTSCHEIDER, als mensch/aktuariat" --zeichnungsordnung "$ORDNUNG" \
      --freigabe-schluessel "$AKTUARIAT_KEY" --mandat "$MANDAT_FALL" \
      --alle-vorlaeufigen --quelle "$quelle" --begruendung "$grund"
}

# Wer an einem Haltepunkt selbst gezeichnet hat, dessen Zeichnung gilt: Das
# Rezept zeichnet nicht ein zweites Mal, und nie ueber eine Ablehnung hinweg.
declare -A ZEICHNUNGEN=()   # je Gate: die wievielte Zeichnung des Rezepts
von_hand() {  # von_hand <name> <gezeichnet.py-Argumente...>: wahr, wenn der Schritt entfaellt
  local name="$1" lage; shift
  lage="$("$PY" "$HIER/gezeichnet.py" "$@")" || bruch "$name: die Zeichnungen lassen sich nicht lesen"
  case "$lage" in
    gezeichnet) printf '  -    %3d  %s (liegt schon: von Hand gezeichnet)\n' "$NR" "$name"; return 0 ;;
    abgelehnt)  bruch "$name: die juengste Zeichnung ist eine Ablehnung — das Rezept zeichnet nicht ueber sie hinweg; nach einer Ablehnung fuehrt ein Mensch den Fall weiter" ;;
  esac
  return 1
}

zeichne() {
  local gate="$1" grund="${2:-}"
  ZEICHNUNGEN[$gate]=$(( ${ZEICHNUNGEN[$gate]:-0} + 1 ))
  erledigt "$gate zeichnen" && return 0
  [ -n "$grund" ] || bruch "zeichne $gate: Begruendung fehlt"
  von_hand "$gate zeichnen" "$BAUM/$F/entscheide" "$gate" "${ZEICHNUNGEN[$gate]}" && return 0
  fahre "$gate zeichnen" bash "$HIER/fall_zeichnen.sh" "$WELT" "$gate" angenommen "$grund"
}

zugang() {
  local phase="${1:-}"; erledigt "Zugang: $phase" && return 0
  [ -n "$phase" ] || bruch "zugang: Phase fehlt"
  if [ "$phase" = ab3 ]; then
    von_hand "Zugang: ab3" "$LINIE/entscheide" A-B3 --beleg anfangsbestand "$LINIE/abgeleitet/anfangsbestand/beleg.json" && return 0
  fi
  fahre "Zugang: $phase" bash "$HIER/zugang.sh" "$WELT" "$@"
}

ring() { bash "$HIER/fall_zeichnen.sh" "$WELT" ring "$1"; }

abgenommen() { "$PY" "$HIER/abgenommen.py" "$LINIE/entscheide" "$1"; }

haltepunkt() {
  local name="$1"
  if erledigt "Haltepunkt $name"; then
    [ "$HALT_BEI" != "$name" ] || halt "der Haltepunkt $name liegt schon hinter diesem Lauf (Schritt $NR von $ERLEDIGT erledigten)"
    return 0
  fi
  merke
  printf '  ---  %3d  Haltepunkt %s\n' "$NR" "$name"
  if [ "$HALT_BEI" = "$name" ]; then
    echo "Haltepunkt $name erreicht. Derselbe Aufruf ohne --bis (oder mit einem spaeteren Haltepunkt) faehrt weiter." | tee -a "$LOG"
    exit 0
  fi
}

erwarte() {
  local rel="$1" soll ist; erledigt "erwarte $rel" && return 0
  soll="$(awk -v p="$rel" '$2 == p { print $1 }' "$PAKET/ERWARTUNG" 2>/dev/null)"
  [ -n "$soll" ] || bruch "erwarte: fuer $rel steht nichts in ERWARTUNG"
  [ -f "$BAUM/$F/$rel" ] || bruch "erwarte: $F/$rel ist nicht entstanden"
  ist="$(sha256sum "$BAUM/$F/$rel" | cut -c1-64)"
  if [ "$ist" != "$soll" ]; then
    printf '         erwartet %s\n         gefunden %s\n' "$soll" "$ist"
    bruch "erwarte $rel: andere Bytes als im festgehaltenen Fall"
  fi
  printf '  ok   %3d  erwarte %s (byte-gleich)\n' "$NR" "$rel"; merke
}

echo "Nachfahren: Fall $FALLNAME aus $PAKET (Paket ${PAKET_SHA:0:12}), Welt $WELT, Code $(git -C "$BAUM" rev-parse --short=12 HEAD 2>/dev/null)$( [ "$ERLEDIGT" -gt 0 ] && echo ", weiter nach Schritt $ERLEDIGT" )" | tee -a "$LOG"

# shellcheck disable=SC1091
. "$PAKET/rezept.sh"

echo "NACHGEFAHREN: $FALLNAME, $NR Schritte. Protokoll: $LOG" | tee -a "$LOG"
