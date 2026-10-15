#!/usr/bin/env bash
# Der taegliche Betriebsteil der Seite (ADR-029): pruefen, exportieren, A-B1
# zeichnen, den Zweig betrieb von plv-fiktion fuellen und schieben. Haelt bei
# jedem Fehler an und schiebt dann nichts; zurueckgedreht wird nichts.
#
#   betrieb_seite.sh <einstellungen> [lauf|pruefen|zweig] [--ohne-push]
#
#   lauf      (Vorgabe) alle Schritte: pruefen, exportieren, A-B1, zweig
#   pruefen   nur die Vorpruefung: der Tageslauf hat heute uebernommen, und
#             das Laufzeit-Image ist der Code-Stand, mit dem plv-fiktion
#             rendert (CODESTAND in main)
#   zweig     nur den Commit fuer den Zweig betrieb bauen und schieben, aus
#             dem Paket, dem Anker und der A-B1, die schon liegen
#   --ohne-push   alles bis auf den Push (Trockenlauf); der Commit liegt
#                 danach nur im Klon und wird angezeigt
#
# Die Einstellungen (Vorlage betrieb-seite.beispiel.conf) liest die Shell. Sie
# nennen Pfade, nie den Inhalt eines Schluessels. Export und A-B1 laufen im
# Laufzeit-Image (docker compose run, ohne Netz); jeder Schluessel kommt als
# einzelne Datei und nur lesend hinein. Der Zweig betrieb entsteht ohne
# Checkout aus einem eigenen Index und traegt genau: paket/ (die
# oeffentlichen Dateien des Pakets, ohne .parquet), anker.jsonl, A-B1.json.
# Geschoben wird nur auf refs/heads/betrieb, ohne Force, mit dem Deploy-Key
# allein (ssh -F /dev/null, sonst mischte ~/.ssh/config andere Schluessel
# dazu).
set -u -o pipefail

halt() { echo "HALT: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }

EINST="${1:-}"
MODUS="${2:-lauf}"
OHNE_PUSH=nein
for a in "${@:2}"; do [ "$a" = "--ohne-push" ] && OHNE_PUSH=ja; done
[ "$MODUS" = "--ohne-push" ] && MODUS=lauf
case "$MODUS" in lauf|pruefen|zweig) ;; *) halt "unbekannter Modus $MODUS (lauf|pruefen|zweig)" ;; esac
[ -n "$EINST" ] && [ -f "$EINST" ] || halt "Einstellungen fehlen: betrieb_seite.sh <einstellungen> [lauf|pruefen|zweig] [--ohne-push]"

AUSLIEFERUNG=ja
AUTOR_NAME="Betriebsdienst PLV"
AUTOR_MAIL="betrieb@plv-fiktion.invalid"
HEUTE=""
# shellcheck disable=SC1090
. "$EINST"
[ -n "$HEUTE" ] || HEUTE="$(date +%F)"
for v in PLV AUSGABE ANKER_DIR KLON; do
  [ -n "${!v:-}" ] || halt "$v fehlt in $EINST"
done
case "$AUSLIEFERUNG" in ja|nein) ;; *) halt "AUSLIEFERUNG ist ja oder nein, nicht $AUSLIEFERUNG" ;; esac
if [ "$AUSLIEFERUNG" = ja ]; then
  for v in FALL LINIE ORDNUNG VORSTAND_KEY BETRIEB_MENSCH_KEY MANDAT ENTSCHEIDER; do
    [ -n "${!v:-}" ] || halt "$v fehlt in $EINST (noetig fuer A-B1)"
  done
fi
PAKET="$AUSGABE/paket"
PY="python3 -I"

git_klon() { git --git-dir="$KLON" "$@"; }

# Ein Remote auf GitHub geht nur ueber den Deploy-Key; ein lokales (Probe,
# Test) braucht keinen.
ssh_fuer_remote() {
  local url
  url="$(git_klon remote get-url origin 2>/dev/null)" || halt "$KLON hat kein Remote origin"
  case "$url" in
    /*|file://*) unset GIT_SSH_COMMAND ;;
    *)
      [ -n "${DEPLOY_KEY:-}" ] && [ -f "$DEPLOY_KEY" ] || halt "DEPLOY_KEY fehlt oder ist keine Datei; ohne ihn wird nichts geholt und nichts geschoben"
      export GIT_SSH_COMMAND="ssh -F /dev/null -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -i $DEPLOY_KEY"
      ;;
  esac
}

holen() {
  ssh_fuer_remote
  git_klon fetch -q origin "+refs/heads/main:refs/remotes/origin/main" || halt "main von origin nicht geholt"
  if git_klon ls-remote --exit-code origin refs/heads/betrieb >/dev/null 2>&1; then
    git_klon fetch -q origin "+refs/heads/betrieb:refs/remotes/origin/betrieb" || halt "betrieb von origin nicht geholt"
  fi
}

compose() { docker compose --project-directory "$PLV" "$@"; }

laeuft_tageslauf() {
  case "$(systemctl --user is-active tageslauf.service 2>/dev/null)" in
    active|activating|reloading|deactivating) return 0 ;;
  esac
  return 1
}

# --- 1 pruefen ----------------------------------------------------------------
pruefen() {
  laeuft_tageslauf && halt "der Tageslauf laeuft gerade; danach erneut"
  local protokoll="$PLV/daten/journal/protokoll.jsonl"
  [ -f "$protokoll" ] || halt "$protokoll fehlt"
  local zeile
  zeile="$($PY -c '
import json, sys
z = json.loads([l for l in open(sys.argv[1], encoding="utf-8") if l.strip()][-1])
print(z.get("heute"), "ja" if z.get("uebernommen") else "nein",
      (z.get("pb1") or {}).get("urteil"), z.get("image_revision") or "-")
' "$protokoll")" || halt "die letzte Zeile von $protokoll ist nicht lesbar"
  read -r Z_HEUTE Z_UEBERNOMMEN Z_URTEIL Z_REVISION <<< "$zeile"
  [ "$Z_HEUTE" = "$HEUTE" ] || halt "der Tageslauf fuehrt $Z_HEUTE, nicht $HEUTE"
  [ "$Z_UEBERNOMMEN" = ja ] && [ "$Z_URTEIL" = gruen ] \
    || halt "der Tageslauf vom $HEUTE ist nicht uebernommen (P-B1 $Z_URTEIL)"
  ok "Tageslauf $HEUTE uebernommen, P-B1 gruen"

  local bild revision
  bild="$(compose config --images tageslauf)" || halt "Image der Laufzeit nicht lesbar"
  [ -n "$bild" ] || halt "compose nennt kein Image fuer tageslauf"
  revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$bild")" \
    || halt "Image $bild nicht vorhanden"
  [ "$revision" = "$Z_REVISION" ] \
    || halt "der Tageslauf lief mit $Z_REVISION, die Laufzeit nennt $bild ($revision)"
  holen
  local codestand
  codestand="$(git_klon show refs/remotes/origin/main:CODESTAND 2>/dev/null | tr -d '[:space:]')"
  [ -n "$codestand" ] || halt "main von plv-fiktion traegt kein CODESTAND"
  [ "$codestand" = "$revision" ] \
    || halt "plv-fiktion rendert mit $codestand, die Laufzeit laeuft auf $revision; erst CODESTAND per Pull Request nachziehen"
  ok "Image $bild = CODESTAND $codestand"
}

# --- 2 exportieren ------------------------------------------------------------
paket_angabe() {  # schema stand art ankersatz
  $PY -c '
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))
a = s.get("anker") or {}
print(s.get("schema_version"), s.get("stand"), a.get("art"), a.get("sha256"))
' "$PAKET/stand.json"
}

exportieren() {
  local art=momentaufnahme flag=()
  [ "$AUSLIEFERUNG" = ja ] && { art=auslieferung; flag=(--auslieferung); }
  mkdir -p "$AUSGABE" "$ANKER_DIR" || halt "$AUSGABE oder $ANKER_DIR nicht anlegbar"
  if [ -f "$PAKET/stand.json" ]; then
    read -r P_SCHEMA P_STAND P_ART P_SATZ <<< "$(paket_angabe)"
    if [ "$P_STAND" = "$HEUTE" ] && [ "$P_ART" = "$art" ]; then
      ok "Paket $HEUTE liegt schon ($art)"
      return
    fi
  fi
  compose run --rm -T --no-deps --entrypoint python \
    -v "$AUSGABE:/ausgabe" -v "$ANKER_DIR:/anker" \
    tageslauf -m rechner_pipeline.betrieb.seite --stand /daten \
    --paket /ausgabe/paket --anker /anker "${flag[@]}" \
    --schluessel /schluessel/betrieb.key --betriebsschluessel /schluessel/betrieb.key \
    --zeichnungsordnung /schluessel/zeichnungsordnung.json || halt "Export gescheitert"
  ok "Paket exportiert"
}

pruefe_paket() {
  local art=momentaufnahme
  [ "$AUSLIEFERUNG" = ja ] && art=auslieferung
  [ -f "$PAKET/stand.json" ] || halt "$PAKET/stand.json fehlt"
  read -r P_SCHEMA P_STAND P_ART P_SATZ <<< "$(paket_angabe)" || halt "$PAKET/stand.json nicht lesbar"
  [ "$P_SCHEMA" = 6 ] || halt "das Paket hat Schema $P_SCHEMA; der Betriebsteil braucht Schema 6 (Image aus einem main mit ADR-029)"
  [ "$P_STAND" = "$HEUTE" ] || halt "das Paket steht auf $P_STAND, nicht auf $HEUTE"
  [ "$P_ART" = "$art" ] || halt "das Paket ist als $P_ART exportiert, erwartet $art"
  [ -n "$P_SATZ" ] && [ "$P_SATZ" != None ] || halt "stand.json nennt keinen Ankersatz"
  # Ein Paket, das eine Luecke ausweist, liefert der Workflow nicht aus; es
  # bekommt dann weder eine A-B1 noch einen Commit.
  local luecken
  luecken="$($PY -c '
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))
print("; ".join(str(l.get("was")) for l in s.get("luecken") or []))
' "$PAKET/stand.json")" || halt "$PAKET/stand.json nicht lesbar"
  [ -z "$luecken" ] || halt "das Paket weist Luecken aus ($luecken); der Workflow liefert es nicht aus. Ein fehlender Image-Digest heisst: IMAGE_DIGEST in der .env der Laufzeit eintragen, den naechsten Tageslauf abwarten"
  ok "Paket Schema 6, Stand $P_STAND, $P_ART, Ankersatz ${P_SATZ:0:16}, ohne Luecke"
}

# --- 3 A-B1 -------------------------------------------------------------------
finde_ab1() {  # gibt den Pfad der angenommenen A-B1 aus, die den Satz bindet
  $PY -c '
import json, pathlib, sys
satz = sys.argv[2]
for p in sorted(pathlib.Path(sys.argv[1]).glob("A-B1-*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if (d.get("gate") == "A-B1" and d.get("entscheid") == "angenommen"
            and satz in [str(x) for x in (d.get("pflichtbelege") or {}).get("anker") or []]
            and (d.get("zeichnung") or {}).get("rolle") == "mensch/betrieb"):
        print(p)
        break
' "$FALL/entscheide" "$P_SATZ"
}

ab1() {
  B1="$(finde_ab1)"
  if [ -n "$B1" ]; then ok "A-B1 liegt schon: $(basename "$B1")"; return; fi
  local tag_de
  tag_de="$(date -d "$HEUTE" +%d.%m.%Y)"
  compose run --rm -T --no-deps --entrypoint python \
    -v "$FALL:/fall" -v "$LINIE:/linie:ro" -v "$ANKER_DIR:/anker:ro" \
    -v "$ORDNUNG:/ring/zeichnungsordnung.json:ro" \
    -v "$VORSTAND_KEY:/ring/vorstand.key:ro" \
    -v "$BETRIEB_MENSCH_KEY:/ring/betrieb-mensch.key:ro" \
    -v "$MANDAT:/ring/mandat.txt:ro" \
    tageslauf -m rechner_pipeline.gates.gate_entscheid \
    --fall /fall --linie /linie --gate A-B1 --entscheid angenommen \
    --entscheider "$ENTSCHEIDER" \
    --begruendung "Auslieferung des Stands vom $tag_de, gezeichnet von der Routine des Betriebsteils (Simulation)" \
    --repo-root /opt/rechner-pipeline \
    --zeichnungsordnung /ring/zeichnungsordnung.json \
    --freigabe-schluessel /ring/vorstand.key \
    --freigabe-schluessel /ring/betrieb-mensch.key \
    --mandat /ring/mandat.txt \
    --anker /anker/anker.jsonl --ankersatz "$P_SATZ" || halt "A-B1 nicht angenommen"
  B1="$(finde_ab1)"
  [ -n "$B1" ] || halt "A-B1 gezeichnet, aber kein Snapshot von mensch/betrieb bindet den Satz ${P_SATZ:0:16}"
  ok "A-B1 gezeichnet: $(basename "$B1")"
}

# --- 4 Zweig betrieb ----------------------------------------------------------
INDEX_DIR=""
raeume_index() { [ -n "$INDEX_DIR" ] && rm -f "$INDEX_DIR/index" "$INDEX_DIR/index.lock" && rmdir "$INDEX_DIR"; }

eintragen() {  # <datei> <pfad im zweig>, in den Index unter GIT_INDEX_FILE
  local blob
  blob="$(git_klon hash-object -w --no-filters -- "$1")" || halt "$1 nicht lesbar"
  git_klon update-index --add --cacheinfo "100644,$blob,$2" || halt "$2 nicht eingetragen"
}

oeffentliche_dateien() {  # stand.json und jede Datei aus "dateien" ohne .parquet, gegen ihre Summe gehalten
  $PY -c '
import hashlib, json, pathlib, re, sys
paket = pathlib.Path(sys.argv[1])
s = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
namen = ["stand.json"]
for name, summe in sorted((s.get("dateien") or {}).items()):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*", name):
        sys.exit(f"unzulaessiger Name im Paket: {name!r}")
    if name.endswith(".parquet"):
        continue
    datei = paket / name
    if not datei.is_file() or datei.is_symlink():
        sys.exit(f"{name}: fehlt im Paket oder ist keine gewoehnliche Datei")
    if hashlib.sha256(datei.read_bytes()).hexdigest() != summe:
        sys.exit(f"{name}: weicht von stand.json ab")
    namen.append(name)
print("\n".join(namen))
' "$PAKET"
}

zweig() {
  local namen
  namen="$(oeffentliche_dateien)" || halt "das Paket ist nicht so, wie stand.json es nennt; nichts geschoben"
  [ -f "$ANKER_DIR/anker.jsonl" ] || halt "$ANKER_DIR/anker.jsonl fehlt"
  grep -q '"art"' "$ANKER_DIR/anker.jsonl" || halt "$ANKER_DIR/anker.jsonl traegt keinen Satz"
  if [ "$AUSLIEFERUNG" = ja ]; then
    B1="$(finde_ab1)"
    [ -n "$B1" ] || halt "keine angenommene A-B1 von mensch/betrieb bindet den Satz ${P_SATZ:0:16}"
  fi
  [ "$MODUS" = zweig ] && holen
  # Ein eigener Index in einem eigenen Verzeichnis: Der Baum des Zweigs ist
  # genau, was hier eingetragen wird, unabhaengig von allem anderen im Klon.
  INDEX_DIR="$(mktemp -d "${TMPDIR:-/tmp}/betrieb-seite.XXXXXX")" || halt "kein temporaeres Verzeichnis"
  trap raeume_index EXIT
  export GIT_INDEX_FILE="$INDEX_DIR/index"
  git_klon read-tree --empty || halt "Index nicht anlegbar"
  while IFS= read -r name; do
    [ -n "$name" ] && eintragen "$PAKET/$name" "paket/$name"
  done <<< "$namen"
  eintragen "$ANKER_DIR/anker.jsonl" anker.jsonl
  [ "$AUSLIEFERUNG" = ja ] && eintragen "$B1" A-B1.json
  local baum vorher commit
  baum="$(git_klon write-tree)" || halt "Baum nicht schreibbar"
  unset GIT_INDEX_FILE
  vorher="$(git_klon rev-parse -q --verify 'refs/remotes/origin/betrieb^{commit}' || true)"
  if [ -n "$vorher" ] && [ "$(git_klon rev-parse "$vorher^{tree}")" = "$baum" ]; then
    ok "betrieb traegt diesen Stand schon ($(git_klon rev-parse --short "$vorher")); nichts zu schieben"
    return
  fi
  commit="$(GIT_AUTHOR_NAME="$AUTOR_NAME" GIT_AUTHOR_EMAIL="$AUTOR_MAIL" \
            GIT_COMMITTER_NAME="$AUTOR_NAME" GIT_COMMITTER_EMAIL="$AUTOR_MAIL" \
            git_klon commit-tree "$baum" ${vorher:+-p "$vorher"} -m "Stand vom $HEUTE")" \
    || halt "Commit nicht angelegt"
  git_klon update-ref refs/heads/betrieb-routine "$commit"
  git_klon show --stat --format='%h %s' "$commit" | head -n 40
  if [ "$OHNE_PUSH" = ja ]; then
    ok "Trockenlauf: Commit $(git_klon rev-parse --short "$commit") liegt im Klon (refs/heads/betrieb-routine), nicht geschoben"
    return
  fi
  ssh_fuer_remote
  git_klon push origin "$commit:refs/heads/betrieb" || halt "Push auf betrieb abgewiesen"
  ok "betrieb = $(git_klon rev-parse --short "$commit"), Stand $HEUTE"
}

case "$MODUS" in
  pruefen) pruefen ;;
  zweig) pruefe_paket; zweig ;;
  lauf)
    pruefen
    exportieren
    pruefe_paket
    [ "$AUSLIEFERUNG" = ja ] && ab1
    zweig
    ;;
esac
