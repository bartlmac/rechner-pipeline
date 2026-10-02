#!/usr/bin/env bash
# Aus einem gefuehrten Fall ein Paket zum Nachfahren bauen (fall_nachfahren.sh).
#
#   deploy/welt/paket_bauen.sh <welt> <ziel> --rezept <rezept.sh>
#        [--erarbeitet <liste>] [--erwartung <liste>]
#
# Gelesen wird der Fall der Welt (<welt>/fall.conf); geschrieben wird allein
# das neue Verzeichnis <ziel>:
#
#   fall.conf        die Falldatei der Welt
#   rezept.sh        das genannte Rezept
#   erarbeitet/      je Zeile der Liste eine Datei oder ein Verzeichnis aus dem
#                    Fall (Pfad relativ zum Fall), unter demselben Pfad
#   nachlieferung/   jede Datei des Eingangs, die NICHT zur Lieferung der
#                    Falldatei gehoert — was die Quelle im Lauf nachgeliefert hat
#   ERWARTUNG        je Zeile der Liste die Pruefsumme der Datei im Fall
#   SHA256SUMS       Pruefsummen aller Dateien des Pakets
#
# Welche Dateien "erarbeitet" sind und welche Ergebnisse byteweise gleich sein
# muessen, entscheidet, wer das Rezept schreibt: Das Skript nimmt die Listen,
# es urteilt nicht. Es haelt aber Rezept und Paket zusammen — jedes
# `einlegen`, `registriere` und `erwarte` des Rezepts muss im Paket seine
# Datei bzw. seinen Eintrag haben, sonst entsteht kein Paket.
#
# Nie ins Paket: Zeichnungen (entscheide/), Schluessel, Belege mit
# Zeitstempeln. Ein Pfad der Liste unter entscheide/ wird verweigert.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; ZIEL="${2:-}"
[ -n "$WELT" ] && [ -n "$ZIEL" ] || { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
shift 2
REZEPT=""; L_ERARBEITET=""; L_ERWARTUNG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rezept)     REZEPT="${2:-}";       shift 2 ;;
    --erarbeitet) L_ERARBEITET="${2:-}"; shift 2 ;;
    --erwartung)  L_ERWARTUNG="${2:-}";  shift 2 ;;
    *) echo "HALT: unbekanntes Argument $1"; exit 2 ;;
  esac
done
halt() { echo "HALT: $*"; exit 2; }
WELT="$(realpath -m "$WELT")"; ZIEL="$(realpath -m "$ZIEL")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
[ -f "$WELT/fall.conf" ] || halt "$WELT/fall.conf fehlt — die Welt fuehrt keinen Fall"
[ -f "$REZEPT" ] || halt "--rezept <rezept.sh> angeben"
for l in "$L_ERARBEITET" "$L_ERWARTUNG"; do [ -z "$l" ] || [ -f "$l" ] || halt "Liste $l nicht gefunden"; done
[ ! -e "$ZIEL" ] || halt "$ZIEL liegt schon — ein Paket wird nie ueberschrieben"

FALLNAME="$(. "$WELT/fall.conf"; printf %s "${FALLNAME:-}")"
LIEFERDATEIEN="$(. "$WELT/fall.conf"; printf %s "${LIEFERDATEIEN:-}")"
case "$FALLNAME" in ''|*[!A-Za-z0-9._-]*) halt "FALLNAME in $WELT/fall.conf: nur Buchstaben, Ziffern, Punkt und Strich" ;; esac
FALL="$BAUM/faelle/$FALLNAME"
[ -d "$FALL/eingang" ] || halt "der Fall $FALL liegt nicht"

zeilen() { grep -v -E '^[[:space:]]*(#|$)' "$1" | sed 's/[[:space:]]*$//'; }
# Die Listen werden geprueft, BEVOR etwas entsteht: Ein Pfad bleibt im Fall
# und meidet die Zeichnungen.
for l in "$L_ERARBEITET" "$L_ERWARTUNG"; do
  [ -n "$l" ] || continue
  while IFS= read -r rel; do
    case "$rel" in
      /*|*..*) halt "Pfad $rel in $l: nur Pfade relativ zum Fall, ohne .." ;;
      entscheide|entscheide/*) halt "Pfad $rel in $l: Zeichnungen gehoeren nie ins Paket" ;;
    esac
  done < <(zeilen "$l")
done

TMP="$ZIEL.im-bau"
[ ! -e "$TMP" ] || halt "$TMP liegt noch von einem abgebrochenen Bau — erst ansehen und entfernen"
mkdir -p "$TMP/erarbeitet" "$TMP/nachlieferung" || exit 1
abbruch() { echo "HALT: $*"; echo "Der unfertige Bau liegt unter $TMP."; exit 1; }

cp "$WELT/fall.conf" "$TMP/fall.conf" && cp "$REZEPT" "$TMP/rezept.sh" || abbruch "Falldatei oder Rezept nicht kopierbar"

if [ -n "$L_ERARBEITET" ]; then
  while IFS= read -r rel; do
    [ -e "$FALL/$rel" ] || abbruch "erarbeitet: $rel liegt nicht im Fall"
    mkdir -p "$TMP/erarbeitet/$(dirname "$rel")" && cp -rp "$FALL/$rel" "$TMP/erarbeitet/$rel" || abbruch "erarbeitet: $rel nicht kopierbar"
  done < <(zeilen "$L_ERARBEITET")
fi

for datei in "$FALL/eingang"/*; do
  [ -f "$datei" ] || continue
  name="$(basename "$datei")"
  case " $(echo "$LIEFERDATEIEN" | tr '\n' ' ') " in *" $name "*) continue ;; esac
  cp -p "$datei" "$TMP/nachlieferung/$name" || abbruch "nachlieferung: $name nicht kopierbar"
done

: > "$TMP/ERWARTUNG"
if [ -n "$L_ERWARTUNG" ]; then
  while IFS= read -r rel; do
    [ -f "$FALL/$rel" ] || abbruch "erwartung: $rel ist keine Datei im Fall"
    printf '%s  %s\n' "$(sha256sum "$FALL/$rel" | cut -c1-64)" "$rel" >> "$TMP/ERWARTUNG"
  done < <(zeilen "$L_ERWARTUNG")
fi

# Rezept und Paket gehoeren zusammen.
rezept="$(sed -e ':a' -e '/\\$/N; s/\\\n/ /; ta' "$TMP/rezept.sh" | grep -v -E '^[[:space:]]*(#|$)')"
while read -r helfer arg _; do
  case "$helfer" in
    einlegen)    [ -e "$TMP/erarbeitet/$arg" ] || abbruch "das Rezept legt $arg ein, aber die Liste --erarbeitet nennt es nicht" ;;
    registriere) [ -f "$TMP/nachlieferung/$arg" ] || abbruch "das Rezept registriert $arg, aber im Eingang des Falls liegt keine solche Nachlieferung" ;;
    erwarte)     awk -v p="$arg" '$2 == p { f = 1 } END { exit !f }' "$TMP/ERWARTUNG" || abbruch "das Rezept erwartet $arg, aber die Liste --erwartung nennt es nicht" ;;
  esac
done <<< "$rezept"

( cd "$TMP" && find . -type f ! -name SHA256SUMS | sed 's#^\./##' | LC_ALL=C sort | while IFS= read -r d; do sha256sum "$d"; done > SHA256SUMS ) || abbruch "Pruefsummen nicht schreibbar"
mv "$TMP" "$ZIEL" || abbruch "das Paket liess sich nicht nach $ZIEL legen"

echo "Paket: $ZIEL — Fall $FALLNAME, $(find "$ZIEL/erarbeitet" -type f | wc -l) erarbeitete Datei(en), $(find "$ZIEL/nachlieferung" -type f | wc -l) Nachlieferung(en), $(wc -l < "$ZIEL/ERWARTUNG") Erwartung(en), Pruefsumme $(sha256sum "$ZIEL/SHA256SUMS" | cut -c1-12)"
