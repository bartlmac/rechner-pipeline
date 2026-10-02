#!/usr/bin/env bash
# Das Abbild der Arbeitsumgebung bauen: das Image (deploy/workshop/Dockerfile),
# darin die Code-Baeume auf festen Marken samt Selbstpruefung, dann das
# Dateisystem als tar.gz — die Datei, die einrichten.ps1 auf einem
# Windows-Rechner als WSL-Distribution importiert.
#
#   deploy/workshop/abbild_bauen.sh --marke <tag|zweig> [--basis <tag|zweig>]
#        [--quelle <pfad|url>] [--paket <verzeichnis>] [--out runs/workshop]
#        [--unveroeffentlicht]
#
#   --marke     der Stand des Hauptbaums ~/rechner-pipeline
#   --basis     ein zweiter Baum ~/rechner-pipeline-basis (der Stand ohne
#               Migration, auf dem ein Fall live startet)
#   --quelle    woher die Marken kommen; Vorgabe: dieses Repository
#   --paket     ein festgehaltener Fall zum Nachfahren (deploy/welt/README.md);
#               er liegt im Abbild unter ~/pakete/<name>, NEBEN den Baeumen —
#               ein Paket traegt die Aufloesung seines Falls. Nur ein Paket,
#               das seinen Pruefsummen entspricht, reist mit.
#   --out       Zielverzeichnis; Vorgabe runs/workshop (nicht versioniert)
#   --unveroeffentlicht
#               erlaubt eine Marke, die nicht in origin/main liegt. Ohne den
#               Schalter haelt das Skript an: Das Abbild truege sonst
#               unveroeffentlichte Arbeit auf fremde Rechner.
#
# Der Container, in dem die Baeume entstehen, hat KEIN Netz: So ist belegt,
# dass die Einrichtung auf dem Zielrechner ohne Netz auskommt. Im Abbild
# liegen keine Schluessel, keine Welt, kein gefuehrter Fall und nur die
# Geschichte der genannten Marken. Welt und Fall entstehen erst auf dem
# Zielrechner, mit dessen eigenen Schluesseln
# (deploy/welt/laufzeit_aufstellen.sh).

set -u -o pipefail

halt() { echo "HALT: $*" >&2; exit 2; }

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
MARKE=""; BASIS=""; QUELLE=""; PAKET=""; OUT="$REPO/runs/workshop"; UNVEROEFFENTLICHT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --marke)  MARKE="${2:-}";  shift 2 ;;
    --basis)  BASIS="${2:-}";  shift 2 ;;
    --quelle) QUELLE="${2:-}"; shift 2 ;;
    --paket)  PAKET="${2:-}";  shift 2 ;;
    --out)    OUT="${2:-}";    shift 2 ;;
    --unveroeffentlicht) UNVEROEFFENTLICHT=1; shift ;;
    *) halt "unbekanntes Argument: $1 (Aufruf im Kopf dieses Skripts)" ;;
  esac
done
[ -n "$MARKE" ] || halt "--marke ist Pflicht"
case "$MARKE$BASIS" in *[!A-Za-z0-9._/-]*) halt "Marken: nur Buchstaben, Ziffern, . _ / -" ;; esac
PAKETNAME=""
if [ -n "$PAKET" ]; then
  PAKET="$(realpath -m "$PAKET")"; PAKETNAME="$(basename "$PAKET")"
  for f in fall.conf rezept.sh SHA256SUMS; do [ -f "$PAKET/$f" ] || halt "--paket $PAKET: $f fehlt — kein Paket"; done
  case "$PAKETNAME" in *[!A-Za-z0-9._-]*) halt "--paket: der Name des Verzeichnisses traegt nur Buchstaben, Ziffern, Punkt und Strich" ;; esac
  ( cd "$PAKET" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1 ) \
    || halt "das Paket $PAKET stimmt nicht mit seinen Pruefsummen ueberein — es reist nicht mit"
fi
command -v docker >/dev/null 2>&1 || halt "docker fehlt"

# Die Quelle: ein Pfad wird lesend eingehaengt, eine URL im Container geholt.
EINHAENGEN=(); IM_CONTAINER="$QUELLE"; HERKUNFT=()
if [ -z "$QUELLE" ] || [ -d "$QUELLE" ]; then
  LOKAL="${QUELLE:-$REPO}"
  GITDIR="$(git -C "$LOKAL" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
    || halt "$LOKAL ist kein Git-Repository"
  for m in "$MARKE" $BASIS; do
    git -C "$LOKAL" rev-parse --verify -q "$m^{commit}" >/dev/null || halt "die Marke $m gibt es in $LOKAL nicht"
    if [ "$UNVEROEFFENTLICHT" -eq 0 ]; then
      git -C "$LOKAL" merge-base --is-ancestor "$m" origin/main 2>/dev/null \
        || halt "die Marke $m liegt nicht in origin/main — erst veroeffentlichen, oder fuer eine Probe auf dem eigenen Rechner --unveroeffentlicht"
    fi
  done
  EINHAENGEN=(-v "$GITDIR:/mnt/quelle:ro")
  IM_CONTAINER="/mnt/quelle"
  # origin im Abbild: die oeffentliche Adresse dieses Repositorys (https).
  URL="$(git -C "$LOKAL" remote get-url origin 2>/dev/null | sed -E 's#^git@([^:]+):#https://\1/#; s#^ssh://git@#https://#')"
  [ -n "$URL" ] && HERKUNFT=(--herkunft "$URL")
fi

IMAGE="rechner-pipeline-workshop"
echo "== Image bauen ($IMAGE)"
docker build --quiet -f "$REPO/deploy/workshop/Dockerfile" -t "$IMAGE" "$REPO" >/dev/null || halt "docker build scheiterte"

C="plv-workshop-bau-$$"
aufraeumen() { docker rm -f "$C" >/dev/null 2>&1; }
trap aufraeumen EXIT

echo "== Baeume anlegen und pruefen (Container ohne Netz)"
SCHRITTE="plv-einrichten baum --quelle $IM_CONTAINER --marke $MARKE ${HERKUNFT[*]}"
[ -n "$BASIS" ] && SCHRITTE="$SCHRITTE && plv-einrichten baum --quelle $IM_CONTAINER --marke $BASIS --name rechner-pipeline-basis ${HERKUNFT[*]}"
SCHRITTE="$SCHRITTE && plv-einrichten pruefen"
if [ -n "$PAKET" ]; then
  EINHAENGEN+=(-v "$PAKET:/mnt/paket:ro")
  SCHRITTE="$SCHRITTE && mkdir -p ~/pakete && cp -r /mnt/paket ~/pakete/$PAKETNAME && (cd ~/pakete/$PAKETNAME && sha256sum --quiet -c SHA256SUMS) && echo 'Paket: ~/pakete/$PAKETNAME'"
fi
# Die eingehaengte Quelle gehoert einem anderen Benutzer, wenn die uid des
# Hosts nicht 1000 ist: nur fuer diesen einen Lauf als sicher erklaeren.
docker run --name "$C" --network none "${EINHAENGEN[@]}" \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/mnt/quelle \
    "$IMAGE" bash -lc "$SCHRITTE" || halt "die Einrichtung im Container scheiterte — kein Abbild geschrieben"

mkdir -p "$OUT" || halt "$OUT laesst sich nicht anlegen"
NAME="plv-arbeitsumgebung-$(printf '%s' "$MARKE" | tr '/' '-')"
ZIEL="$OUT/$NAME.tar.gz"
[ -e "$ZIEL" ] && halt "$ZIEL liegt schon — ein Abbild wird nie ueberschrieben (anderes --out waehlen oder die Datei selbst entfernen)"
echo "== Dateisystem exportieren"
docker export "$C" | gzip > "$ZIEL.teil" || halt "der Export scheiterte"
mv "$ZIEL.teil" "$ZIEL"
( cd "$OUT" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256" )

echo "Abbild: $ZIEL ($(du -h "$ZIEL" | cut -f1))"
echo "SHA-256: $(cut -d' ' -f1 "$ZIEL.sha256")"
echo "Auf dem Windows-Rechner: einrichten.ps1 -Abbild <diese Datei> -Pruefsumme <SHA-256>"
