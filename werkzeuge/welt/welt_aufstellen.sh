#!/usr/bin/env bash
# Eine Welt aufstellen: die Ablage der PLV ohne uebernommenen Bestand, eine
# Linie mit ihrem ersten Glied und die vier Erstabnahmen (A-K2, A-O1, A-T1,
# A-B3) samt gebundenem Anfangsbestand. Danach kann in dieser Welt ein Fall
# gefuehrt werden (fall_starten.sh, fall_zeichnen.sh). Jeder Schritt haelt
# beim ersten Fehler an und schreibt nach <welt>/aufstellen.log.
#
#   werkzeuge/welt/welt_aufstellen.sh <welt> [phase]
#
# Phasen (ohne Angabe: alle, in dieser Reihenfolge):
#   schluessel  NUR fuer eine Welt mit eigenen Schluesseln (Vorfuehrung,
#               Uebung, Probe): erzeugt je Rolle einen Schluessel (64 zufaellige
#               Byte, 0600, nie angezeigt), die Zeichnungsordnung, das Mandat
#               und <welt>/einstellungen.conf. Liegt die Einstellungsdatei
#               schon, wird die Phase uebersprungen — wer vorhandene Schluessel
#               nutzt, legt die Datei selbst an (Vorlage:
#               einstellungen.beispiel.conf).
#   ablage      Ablage anlegen und ohne uebernommenen Bestand bis BIS fuehren
#               (rechnet einige Minuten; zeichnet nur Protokollzeilen mit dem
#               Betriebsschluessel)
#   linie       Linienbereich und erstes Glied der Ordnungslinie
#   abnahmen    A-K2, A-O1, A-T1, A-B3 zeichnen, Anfangsbestand binden
#
# Umgebung, nur fuer die Phase schluessel (alles mit Vorgabe):
#   SCHLUESSEL   Verzeichnis der Schluessel, AUSSERHALB von Welt und Baum
#                (Vorgabe ~/.plv-schluessel)
#   BIS          letzter Tag der Ablage (Vorgabe 2025-12-31, der Tag vor dem
#                Zugangsstichtag der Baldrian-Lieferung)
#   VON          zuletzt abgenommener Kern- und Tarifwerksstand, gegen den die
#                Erstabnahme ihre Aenderung zeigt (ohne Angabe: der Stand des
#                Codebaums selbst; die Erstabnahme nimmt ihn ab, wie er ist)
#   MANDATGEBER  wer das Mandat der simulierten Rollen erteilt
#   ENTSCHEIDER  wer in den Snapshots als Entscheider steht
# Immer:
#   BAUM         der Codebaum (Vorgabe: der Baum dieses Skripts)
#   PYTHON       der Interpreter (Vorgabe <baum>/.venv/bin/python)
#
# Voraussetzung: Der Codebaum ist sauber (git status leer) und wird waehrend
# des Aufstellens nicht bewegt — die Abnahmen pinnen seinen Stand.
# Die Schluessel der menschlichen Rollen dieser Welt haben die Klasse
# simulation: Jede Zeichnung weist sich als simuliert aus und nennt das
# Mandat. Der Schluessel des Tageslaufs hat die Klasse betrieb.

HIER="$(cd "$(dirname "$0")" && pwd)"
WELT="${1:-}"; PHASE="${2:-alles}"
[ -n "$WELT" ] || { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
WELT="$(realpath -m "$WELT")"
BAUM="$(realpath -m "${BAUM:-$HIER/../..}")"
PY="${PYTHON:-$BAUM/.venv/bin/python}"
EINST="$WELT/einstellungen.conf"
LOG="$WELT/aufstellen.log"

case "$PHASE" in schluessel|ablage|linie|abnahmen|alles) ;; *) echo "HALT: unbekannte Phase $PHASE"; exit 2 ;; esac
[ -d "$BAUM/src/rechner_pipeline" ] || { echo "HALT: $BAUM ist kein Codebaum dieses Repositorys"; exit 2; }
[ -x "$PY" ] || { echo "HALT: Interpreter $PY fehlt — die Umgebung des Baums einrichten oder PYTHON setzen"; exit 2; }
[ -z "$(git -C "$BAUM" status --porcelain)" ] || { echo "HALT: der Codebaum $BAUM ist nicht sauber"; exit 2; }
case "$WELT/" in "$BAUM"/*) echo "HALT: die Welt liegt nicht im Codebaum"; exit 2 ;; esac
mkdir -p "$WELT" || exit 2
# Das Paket kommt aus DIESEM Baum, und der Baum bleibt beim Rechnen sauber.
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BAUM/src"
cd "$BAUM" || exit 2

schritt() {  # schritt <name> <kommando...>: faehrt, protokolliert, haelt bei Exit != 0
  local name="$1"; shift
  { echo "### $(date -u +%Y-%m-%dT%H:%M:%SZ) $name"; echo "\$ $*"; } >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "HALT bei '$name' (Exit $rc) — siehe $LOG"; tail -c 700 "$LOG"; return 1; fi
  echo "ok   $name"
}

schlicht() {  # schlicht <name> <wert>: der Wert steht spaeter in doppelten Anfuehrungszeichen in einer Datei, die die Shell liest
  case "$2" in *[\"\$\`\\]*|*$'\n'*) echo "HALT: $1 enthaelt ein Anfuehrungszeichen, \$, einen Rueckstrich oder einen Zeilenumbruch"; return 2 ;; esac
}

phase_schluessel() {
  if [ -e "$EINST" ]; then echo "ok   Einstellungen liegen schon: $EINST (Phase schluessel uebersprungen)"; return 0; fi
  local K; K="$(realpath -m "${SCHLUESSEL:-$HOME/.plv-schluessel}")"
  local mandatgeber="${MANDATGEBER:-die Leitung der Vorfuehrung}"
  local entscheider="${ENTSCHEIDER:-Teilnehmer der Vorfuehrung, simulierte Rolle unter Mandat}"
  schlicht WELT "$WELT" && schlicht SCHLUESSEL "$K" && schlicht MANDATGEBER "$mandatgeber" \
    && schlicht ENTSCHEIDER "$entscheider" && schlicht BIS "${BIS:-}" && schlicht VON "${VON:-}" || return 2
  case "$K/" in "$WELT"/*|"$BAUM"/*) echo "HALT: die Schluessel liegen ausserhalb von Welt und Codebaum (SCHLUESSEL=$K)"; return 2 ;; esac
  [ ! -e "$K/zeichnungsordnung.json" ] || { echo "HALT: $K traegt schon eine Zeichnungsordnung — fuer eine zweite Welt mit eigenen Schluesseln ein anderes Verzeichnis nennen (SCHLUESSEL=...)"; return 1; }
  mkdir -p "$K" && chmod 700 "$K" || return 2
  local rolle
  for rolle in betrieb vorstand rechenkern architektur aktuariat betrieb-mensch; do
    [ ! -e "$K/$rolle.key" ] || { echo "HALT: $K/$rolle.key liegt schon — ein Schluessel wird nie ueberschrieben"; return 1; }
    (umask 077; head -c 64 /dev/urandom > "$K/$rolle.key") || return 2
  done
  fp() { sha256sum "$K/$1.key" | cut -c1-64; }
  cat > "$K/zeichnungsordnung.json" <<EOF
{"schema_version": 2, "rollen": {
  "betrieb/tageslauf": {"schluessel_sha256": "$(fp betrieb)", "schluesselklasse": "betrieb", "gates": []},
  "mensch/vorstand": {"schluessel_sha256": "$(fp vorstand)", "schluesselklasse": "simulation", "gates": ["A-Z1", "A-M6"]},
  "mensch/rechenkern": {"schluessel_sha256": "$(fp rechenkern)", "schluesselklasse": "simulation", "gates": ["A-K2"]},
  "mensch/architektur": {"schluessel_sha256": "$(fp architektur)", "schluesselklasse": "simulation", "gates": ["A-O1"]},
  "mensch/aktuariat": {"schluessel_sha256": "$(fp aktuariat)", "schluesselklasse": "simulation", "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-T1"]},
  "mensch/betrieb": {"schluessel_sha256": "$(fp betrieb-mensch)", "schluesselklasse": "simulation", "gates": ["A-B1", "A-B2", "A-B3"]}
}}
EOF
  mkdir -p "$WELT/mandate" || return 2
  local stand text; stand="$(git -C "$BAUM" rev-parse --short=12 HEAD)"
  text="$(cat "$HIER/mandat.vorlage.txt")" || return 2
  # Der Ersatztext steht in Anfuehrungszeichen: Sonst liest die Shell ein &
  # darin als "das Gefundene".
  text="${text//@WELT@/"$WELT"}"; text="${text//@STAND@/"$stand"}"
  text="${text//@DATUM@/"$(date +%F)"}"; text="${text//@MANDATGEBER@/"$mandatgeber"}"
  printf '%s\n' "$text" > "$WELT/mandate/mandat.txt" || return 2
  chmod 0444 "$WELT/mandate/mandat.txt"
  cat > "$EINST" <<EOF
# Einstellungen der Welt $WELT — erzeugt von welt_aufstellen.sh am $(date +%F).
# Schluessel stehen hier nur als PFAD. Erlaeuterung: einstellungen.beispiel.conf.
WELT="$WELT"
LINIE="$WELT/linie"
BIS="${BIS:-2025-12-31}"
VON="${VON:-$(git -C "$BAUM" rev-parse HEAD)}"
ENTSCHEIDER="$entscheider"
ORDNUNG="$K/zeichnungsordnung.json"
MANDAT="$WELT/mandate/mandat.txt"
MANDAT_FALL="$WELT/mandate/mandat.txt"
STELLUNGNAHME="$HIER/stellungnahme-tbox-020.json"
TBOX_ARTEFAKT="docs/architektur/adr-024-tbox-020-tarifwerk-gevo-zustandsextrakt.md"
BETRIEB_KEY="$K/betrieb.key"
VORSTAND_KEY="$K/vorstand.key"
RECHENKERN_KEY="$K/rechenkern.key"
ARCHITEKTUR_KEY="$K/architektur.key"
AKTUARIAT_KEY="$K/aktuariat.key"
BETRIEB_MENSCH_KEY="$K/betrieb-mensch.key"
PROGRAMMLEITUNG_KEY="$K/programmleitung.key"
PROGRAMMLEITUNG_KLASSE=simulation
EOF
  echo "ok   Schluessel, Zeichnungsordnung und Mandat erzeugt: $K (sechs Rollen: fuenf der Klasse simulation, der Tageslauf der Klasse betrieb), $EINST"
}

lade_einstellungen() {
  [ -f "$EINST" ] || { echo "HALT: $EINST fehlt — Phase schluessel fahren oder die Datei nach einstellungen.beispiel.conf anlegen"; return 2; }
  local aufruf="$WELT"
  # shellcheck disable=SC1090
  . "$EINST"
  [ "$WELT" = "$aufruf" ] || { echo "HALT: $EINST gehoert zur Welt $WELT, aufgerufen wurde $aufruf — eine verschobene oder kopierte Welt wird nicht gefuehrt"; return 2; }
  local v
  for v in LINIE BIS ORDNUNG BETRIEB_KEY; do
    [ -n "${!v}" ] || { echo "HALT: $v fehlt in $EINST"; return 2; }
  done
  for v in ORDNUNG BETRIEB_KEY; do
    [ -f "${!v}" ] || { echo "HALT: ${!v} ($v) nicht gefunden"; return 2; }
  done
  D="$WELT/daten"; L="$LINIE"
}

zeichne() {  # zeichne <gate> <schluessel> <rolle> <begruendung>
  schritt "$1 zeichnen (als $3)" "$PY" -m rechner_pipeline.gates.gate_entscheid --linie "$L" --gate "$1" \
    --entscheid angenommen --entscheider "$ENTSCHEIDER, als $3" --begruendung "$4" --repo-root "$BAUM" \
    --zeichnungsordnung "$ORDNUNG" --freigabe-schluessel "$2" --mandat "$MANDAT"
}

phase_ablage() {
  lade_einstellungen || return
  [ ! -e "$D" ] || { echo "HALT: $D liegt schon — eine Ablage wird nie ueberschrieben"; return 1; }
  mkdir -p "$D/configs" \
  && cp "$BAUM/plv/configs/bestand_gesamt.toml" "$D/configs/bestand.toml" \
  && echo "Welt $WELT, Code $(git -C "$BAUM" rev-parse --short=12 HEAD), Ablage bis $BIS" | tee -a "$LOG" \
  && schritt "Ablage ohne uebernommenen Bestand bis $BIS fuehren" "$PY" -m rechner_pipeline.betrieb.tageslauf \
       --stand "$D" --heute "$BIS" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG"
}

phase_linie() {
  lade_einstellungen || return
  [ ! -e "$L" ] || { echo "HALT: $L liegt schon — eine Linie wird nie neu begonnen"; return 1; }
  schritt "Linienbereich anlegen" "$PY" -m rechner_pipeline.gates.stand_belegen linie --linie "$L" \
  && schritt "erstes Glied der Ordnungslinie" "$PY" -m rechner_pipeline.gates.stand_belegen ordnung --linie "$L" \
       --ordnung "$ORDNUNG" --vorgaenger keiner
}

phase_abnahmen() {
  lade_einstellungen || return
  local v
  for v in RECHENKERN_KEY ARCHITEKTUR_KEY AKTUARIAT_KEY BETRIEB_MENSCH_KEY MANDAT STELLUNGNAHME; do
    [ -n "${!v}" ] && [ -f "${!v}" ] || { echo "HALT: $v fehlt in $EINST oder die Datei liegt nicht"; return 2; }
  done
  for v in VON ENTSCHEIDER TBOX_ARTEFAKT; do
    [ -n "${!v}" ] || { echo "HALT: $v fehlt in $EINST"; return 2; }
  done
  [ -d "$D/abschluesse" ] && [ -d "$L/ordnung" ] || { echo "HALT: erst die Phasen ablage und linie"; return 1; }
  [ -z "$(ls "$L/entscheide" 2>/dev/null)" ] || { echo "HALT: in $L/entscheide liegen schon Abnahmen"; return 1; }
  schritt "Kernstand belegen" "$PY" -m rechner_pipeline.gates.kernstand_belegen --linie "$L" --repo-root "$BAUM" \
       --von "$VON" --begruendung "Erstabnahme des Stands beim Aufstellen der Welt" \
  && zeichne A-K2 "$RECHENKERN_KEY" mensch/rechenkern "Erstabnahme Kernstand beim Aufstellen der Welt" \
  && schritt "T-Box belegen" "$PY" -m rechner_pipeline.gates.stand_belegen tbox --linie "$L" --repo-root "$BAUM" \
       --artefakt "$TBOX_ARTEFAKT" --begruendung "Erstabnahme des Stands beim Aufstellen der Welt" \
  && cp "$STELLUNGNAHME" "$L/abgeleitet/tbox/stellungnahme.json" \
  && zeichne A-O1 "$ARCHITEKTUR_KEY" mensch/architektur "Erstabnahme T-Box beim Aufstellen der Welt" \
  && schritt "Tarifwerk belegen" "$PY" -m rechner_pipeline.gates.tarifwerk_belegen --linie "$L" --repo-root "$BAUM" \
       --von "$VON" --begruendung "Erstabnahme des Stands beim Aufstellen der Welt" \
  && zeichne A-T1 "$AKTUARIAT_KEY" mensch/aktuariat "Erstabnahme Tarifwerk beim Aufstellen der Welt" \
  && schritt "Anfangsbestand belegen" "$PY" -m rechner_pipeline.betrieb.anfangsbestand belegen --stand "$D" --linie "$L" \
       --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" \
  && zeichne A-B3 "$BETRIEB_MENSCH_KEY" mensch/betrieb "Erstabnahme Anfangsbestand der Ablage ohne uebernommenen Bestand" \
  && schritt "Anfangsbestand binden" "$PY" -m rechner_pipeline.betrieb.anfangsbestand binden --stand "$D" --linie "$L" \
       --freigabe-schluessel "$BETRIEB_MENSCH_KEY" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" \
  && schritt "Tageslauf nach dem Binden (derselbe Tag)" "$PY" -m rechner_pipeline.betrieb.tageslauf \
       --stand "$D" --heute "$BIS" --schluessel "$BETRIEB_KEY" --zeichnungsordnung "$ORDNUNG" \
  && echo "WELT STEHT: $WELT — Abnahmen: $(ls "$L/entscheide" | sed 's/-[0-9a-f]\{64\}\.json//' | tr '\n' ' ')| Abschluesse: $(ls "$D/abschluesse" | wc -l), juengster $(ls "$D/abschluesse" | tail -1)" | tee -a "$LOG"
}

case "$PHASE" in
  schluessel) phase_schluessel ;;
  ablage)     phase_ablage ;;
  linie)      phase_linie ;;
  abnahmen)   phase_abnahmen ;;
  alles)      phase_schluessel && phase_ablage && phase_linie && phase_abnahmen ;;
esac
