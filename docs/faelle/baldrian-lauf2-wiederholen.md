# Den zweiten Baldrian-Lauf wiederholen

Pfefferminzia Lebensversicherung — Programm Bestandsmigration.
Arbeitsanleitung zum Abschlussbericht des zweiten Migrationslaufs
(`baldrian-lauf2.md`): wie ein Dritter den Lauf auf demselben
Systemstand nachstellt — einschliesslich des eigenen Bestands der
Pfefferminzia, der nicht aus der Baldrian-Lieferung stammt.

Alle Zahlen und Pruefsummen dieser Anleitung sind am 30.09.2026 auf
frischen Auscheckungen der genannten Staende nachgemessen worden, nicht
aus dem Lauftag abgeschrieben; eine Fremdprobe hat die Anleitung danach
in einem frischen Klon Schritt fuer Schritt nachgefahren (alle
Referenzwerte aus Abschnitt 8 bit-gleich, alle fuenf Zeichnungen
angenommen). Wo die Wiederholung vom Lauftag abweicht, steht es in
Abschnitt 9.

## 1 Der Systemstand des Laufs

| Commit | Datum | Kern | Quelltext-Pruefsumme | Bedeutung |
|---|---|---|---|---|
| `4b1abf048ac84bfeecce12a67f18983648990799` | 02.09.2026 | 3.3.0 | `ef1af1a32af7919d02f8b6826302949ad097de25f189957a420045a196ef2a43` | **Stand des Laufs.** Alle fuenf Zeichnungen des Laufs (A-Q1 fd793260, A-M1 fb1550c0, A-M2 411ac21c, A-M3 d260e621, A-M4 32682e95; gezeichnet am 02.09.2026, 00:48-00:49 Uhr) binden diese Pruefsumme. |
| `96588b8af43eb33a0b21ead1e731360bf96cf84f` | 06.09.2026 | 3.4.0 | — | Zusammenfuehrung des Fallzweigs in den Hauptzweig (PR 11). Enthaelt 4b1abf04; zur Einordnung, nicht zum Nachrechnen. |
| `1dc736b440edade4e92f174e10ede089863630bf` | 08.09.2026 | 3.5.0 | `7591ac1ae622433f1bad356f3d69bdb6f4c846ce32d2718941be8b9ad9624be3` | Hauptzweig-Stand, auf dem ausserhalb des Programms erstmals nachgerechnet wurde. Liefert dieselben Kennzahlen wie der Lauf (Abschnitt 10), aber mit anderen Kommando-Optionen. |

Die Quelltext-Pruefsumme ist der SHA-256 ueber alle `.py`- und
`.xml`-Dateien unter `src/rechner_pipeline`; jeder Beleg und jeder
Snapshot traegt sie als `quellcode_sha256`. Wer seinen Stand pruefen
will, rechnet sie nach:

```
python -c "from pathlib import Path; from rechner_pipeline.gates._provenienz import systemstand; print(systemstand(Path('.').resolve()))"
```

Nach dem Lauf wurden die fuenf Gates zweimal neu gezeichnet: am
07.09.2026 auf `f7c545d` (Korrekturen 24 und 25, Nachtrag im
Abschlussbericht) und am 20.09.2026 auf `17091b39` (Korrekturen 26 und
27, `dev-docs/annahmen-2026-09-20.md`). Diese Staende sind die geltende
Spitze der Snapshots, nicht der Stand des Laufs. Wer den Lauf wiederholen
will, nimmt `4b1abf04`.

## 2 Was das Repository traegt — und was nicht

**Im Repository:** der Code, die Lieferung `lieferungen/baldrian-2/`
und die Skills. Bei `4b1abf04` liegen zwoelf Dateien der Lieferung im
Repository; die vier Auskunftsschreiben kamen erst mit `ce89ad6`
(02.09.2026) hinzu und sind auf dem Hauptzweig. Die Pruefsummen der
sechzehn Dateien sind die des Eingangsregisters des Laufs — wer sie
registriert, bekommt dasselbe Register bis auf die Zeitstempel:

| Datei | SHA-256 (Anfang) |
|---|---|
| `Tarifrechner_KLV_TG2015.xlsm` | `e0cd0a03298f2a19` |
| `Mitteilung_143_KLV_TG2015.pdf` | `a5cde1fb1a05d253` |
| `AVB_KLV_TG2015.pdf` | `3a279db47f9ea69b` |
| `LIEFERSCHEIN.md` | `80bdd432f99e769c` |
| `baldrian_bestandsabzug_2026-01-01.csv` | `9ecb8bcd90d706ca` |
| `baldrian_bestandsabzug_2027-01-01.csv` | `a6f01126d1236757` |
| `baldrian_gevo_metadaten.csv` | `d9327a8b79557328` |
| `baldrian_gevo_protokoll_2026.csv` | `860ff4b92699bf05` |
| `baldrian_erwartungswerte_stichtag.json` | `c98585b0f635681c` |
| `baldrian_erwartungswerte_verlauf.json` | `f3448668a8b4af23` |
| `baldrian_erwartungswerte_geschaeftsvorfaelle.json` | `812e7e2d67434b1d` |
| `baldrian_erwartungswerte_stichprobe.json` | `8a3f648e1310da9a` |
| `auskunft-1-dynamiksatz-und-herabsetzungsanteile.md` | `b4f83b55de956fa8` |
| `auskunft-2-herabsetzungsanteile-stichprobe.md` | `0a2f46fb522625cf` |
| `auskunft-3-tarifzins-widerspruch.md` | `38e515aa1e39187c` |
| `auskunft-4-herabsetzungsanteile-kernverwaltung.md` | `15c79a8f321785d6` |

**Nicht im Repository:** der Fall-Arbeitsbereich `faelle/` (A-Box,
Spez, Entscheide, Belege, Snapshots — er ist bewusst nicht versioniert),
der Freigabeschluessel und die Zeichnungsordnung (sie gehoeren nie in ein
Repository) und das Paket der Stufe-1-Artefakte aus Abschnitt 7 (beim
Programm erhaeltlich).

## 3 Drei Sorten Schritte — und was Wiederholung jeweils heisst

Die Pipeline besteht aus drei Sorten Schritten. Die Unterscheidung ist
keine Feinheit, sondern der Kern der Architektur: das Modell schlaegt
vor, deterministischer Code entscheidet, der Mensch zeichnet.

| Sorte | Schritte | Was Wiederholung bedeutet |
|---|---|---|
| **Kommando** (deterministisch) | `fall anlegen/registrieren`, `gates.extract`, `quellen.tarifplan_staging`, `quellen.bestand_profil`, `gates.abox_merge`, `gates.abox_validate` (P-Q3), Spez-Erzeugung, `gates.generation_golden` (P-K1), `gates.transformation_anwenden`, `gates.bestand_uebernehmen`, `gates.verankerung_belegen`, `gates.bestand_validate` (P-B1), `gates.aktuartest_lauf`/`aktuartest`, `gates.migrationssuite_lauf`, `bestand.cli_fortschreibung`, `bestand.cli_report`, `gates.abnahmebericht` | Gleiche Eingaben, gleiche Bytes. Ausnahme sind die Ledger und Belege: sie tragen Zeitstempel, Versuchszaehler, Zweigname und Dirty-Flag (Abschnitt 9). |
| **Agentenschritt** (Modell schlaegt vor) | je Quelle ein Fragment nach Skill `extrahiere-quellfragment` samt Verifikationspass; `fragmente/akteure.json`; die TransformationsSpec nach Skill `transformiere-quellbestand`; die Vorlagen fuer die menschlichen Gates | Nicht byte-gleich, sondern gleichwertig: P-Q3 gruen ohne Luecken, P-K1 616/616, Spec deckt alle Pflichtfelder, 834 Quellzeilen ergeben 834 Zielzeilen ohne Befund. Dass ein zweiter Agent zum selben Ergebnis kommt, ist Teil der Vorfuehrung. |
| **Menschlicher Entscheid** | vierzehn Diskrepanz-Aufloesungen (`ontologie.entscheide`), fuenf Gate-Zeichnungen (`gates.gate_entscheid`), die Registrierung der Auskunftsschreiben auf Rueckfrage | Eigene Entscheide mit eigenem Schluessel. Die Entscheide des Laufs stehen im Abschlussbericht (Abschnitte 3 und 5) und in der A-Box des Pakets; wer sie uebernimmt, uebernimmt sie bewusst. |

Daraus folgen zwei Wege: **Weg A** (Abschnitt 6) faehrt alle drei Sorten
selbst und braucht dafuer eine Agenten-Umgebung (Claude Code oder Codex
mit den Skills des Repositorys). **Weg B** (Abschnitt 7) uebernimmt die
Agentenschritte und Entscheide der Stufe 1 aus dem Paket und ist ab
dort reine Kommandofolge — jeder mit dem Repository kann ihn fahren. Der
eigene Bestand (Abschnitt 5) ist auf beiden Wegen reines Kommando.

## 4 Umgebung einrichten

```
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline
git checkout 4b1abf048ac84bfeecce12a67f18983648990799
python3 -m venv .venv                # Windows: py -m venv .venv
source .venv/bin/activate            # Windows, Git Bash: source .venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python -m pip install pypdf==6.16.2
python -c "import rechner_pipeline.kern as k; print(k.__version__)"    # 3.3.0
```

`pypdf` ist bei `4b1abf04` in `pyproject.toml` gepinnt, fehlt aber in
`requirements.txt`; ohne die Nachinstallation bricht
`quellen.tarifplan_staging` mit `ModuleNotFoundError` ab. Python 3.11
oder neuer; ausserhalb des venv heisst der Interpreter auf Debian
`python3`, im aktivierten venv `python`. Das Kommando aus Abschnitt 1
gibt danach ein Woerterbuch aus; erwartet sind `commit 4b1abf04...`,
`branch HEAD`, `dirty nein` und `quellcode_sha256 ef1af1a3...`. Alle
Kommandos dieser Anleitung laufen aus der Repository-Wurzel mit
`--repo-root .`; `gates.abnahmebericht` und die Belege lesen den
Git-Stand, die Auscheckung muss also ein Git-Klon sein. Unter Windows
entfaellt die POSIX-Rechtepruefung des Freigabeschluessels (Abschnitt
6.4), alles andere ist gleich.

Optional, etwa zehn Minuten: `python -m pytest -q` muss auf diesem
Stand gruen sein.

## 5 Der eigene Bestand der Pfefferminzia (ohne Baldrian)

Die Pfefferminzia ist ein erfundenes Unternehmen; ihr Bestand ist
synthetisch und wird deterministisch aus einer Config erzeugt (Saat in
der Config, ADR-020). Es braucht keine Lieferung dafuer. Der Lauf hat
zwei Auspraegungen davon benutzt:

**Der Gesamtbestand vor der Uebernahme** (3130 Vertraege KLV und BU,
elf Generationen, Horizont 2046) — der Bestandsbericht davon liegt im
Fall als `abgeleitet/bestand-vor/`:

```
python -m rechner_pipeline.bestand.cli_fortschreibung --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --out-dir runs/bestand-vor
python -m rechner_pipeline.bestand.cli_report --portfolio runs/bestand-vor/bestand_gesamt.parquet \
    --historie runs/bestand-vor/historie.parquet --ledger runs/bestand-vor/ledger.parquet \
    --scheiben runs/bestand-vor/scheiben.parquet --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --titel "Bestandsbericht PLV Eigenbestand VOR der Uebernahme" \
    --out runs/bestand-vor/bestandsbericht.html
```

Erwartet: `3130 Basisvertraege, 0 Neuzugaenge, 11193 GeVos`. Byte-gleich
mit dem Lauf: `bestand.parquet` `740ecdde`, `bestand_gesamt.parquet`
`775d24bd`, `historie.parquet` `38e115ee`, `ledger.parquet` `32b9e816`,
`scheiben.parquet` `14cef7ea`, `zugaenge.parquet` `2fe105ff`,
`bestandsbericht.html` `df354abd`.

**Der KLV-Eigenbestand zum Migrationsstichtag** (2220 Vertraege, neun
Generationen KLV-1994 bis KLV-2022; die eigene KLV-2015 ist nicht die
uebernommene TG2015 der Baldrian) — er ist der Traeger, in den die 834
Baldrian-Vertraege uebernommen werden. Der Fortschreibungslauf des Falls
(Abschnitt 7.5, Schritt 15) erzeugt ihn selbst; einzeln entsteht er so:

```
python -m rechner_pipeline.bestand.cli_fortschreibung --config configs/bestand_klv.toml \
    --bis 2026-01-01 --neuzugang-ab 2026-01-01 --out-dir runs/eigen-2026
```

Erwartet: `2220` Vertraege, `bestand.parquet` `ddd18d4b` — dieselben
Bytes wie `bestand-nach/bestand.parquet` des Laufs (der Eigenanteil vor
dem Zufuegen der Uebernahme). Ohne `--neuzugang-ab` entstehen 2330
Vertraege (KLV-2022 mit 150 statt 40): das ist nicht der Bestand des
Laufs. Fuer den Lauf mit `--uebernahme` reicht `configs/bestand_klv.toml`
nicht — die Fall-Config aus Abschnitt 7.3 muss die TG2015 kennen, sonst
endet der Lauf mit `Tarifgeneration 'TG2015' nicht in Config`.

## 6 Weg A — den Lauf vollstaendig selbst fahren

Massgeblich ist der Skill `.claude/skills/migrationsfall-durchfuehren/
SKILL.md` des ausgecheckten Stands; diese Anleitung nennt nur, was er
fuer diesen Fall bedeutet.

### 6.1 Fall anlegen und Lieferung registrieren

```
python -m rechner_pipeline.fall anlegen --fall faelle/baldrian-lauf2-w --scope bestand \
    --beschreibung "Wiederholung Lauf 2 Baldrian KLV TG2015"
for f in lieferungen/baldrian-2/*; do
  python -m rechner_pipeline.fall registrieren --fall faelle/baldrian-lauf2-w --datei "$f"
done
python -m rechner_pipeline.fall status --fall faelle/baldrian-lauf2-w
```

Die vier Auskunftsschreiben liegen bei `4b1abf04` nicht im Baum. Aus
dem Hauptzweig holen, ohne die Auscheckung zu veraendern, und dann wie
oben registrieren — im Lauf geschah das erst, als die Rueckfragen
gestellt waren (Dynamiksatz und Herabsetzungsanteile, Tarifzins); wer
die Vorfuehrung nachstellen will, registriert sie ebenfalls erst dann:

```
mkdir -p ../auskuenfte
for n in 1-dynamiksatz-und-herabsetzungsanteile 2-herabsetzungsanteile-stichprobe \
         3-tarifzins-widerspruch 4-herabsetzungsanteile-kernverwaltung; do
  git show 96588b8:lieferungen/baldrian-2/auskunft-$n.md > ../auskuenfte/auskunft-$n.md
done
for f in ../auskuenfte/*; do
  python -m rechner_pipeline.fall registrieren --fall faelle/baldrian-lauf2-w --datei "$f"
done
```

### 6.2 Vorverdichtung (Kommandos, byte-gleich)

```
F=faelle/baldrian-lauf2-w
python -m rechner_pipeline.gates.extract --repo-root . --input $F/eingang/Tarifrechner_KLV_TG2015.xlsm \
    --out-dir $F/abgeleitet/vorverdichtung/xlsm-TG2015 --adapter excel --diagnostics-dir $F/abgeleitet/diagnostics
python -m rechner_pipeline.quellen.tarifplan_staging --input $F/eingang/Mitteilung_143_KLV_TG2015.pdf \
    --out $F/abgeleitet/vorverdichtung/meldung-TG2015.json
python -m rechner_pipeline.quellen.tarifplan_staging --input $F/eingang/AVB_KLV_TG2015.pdf \
    --out $F/abgeleitet/vorverdichtung/avb-TG2015.json
python -m rechner_pipeline.quellen.bestand_profil --input $F/eingang/baldrian_bestandsabzug_2026-01-01.csv \
    --out $F/abgeleitet/vorverdichtung/bestand-2026-01-01.json
python -m rechner_pipeline.quellen.bestand_profil --input $F/eingang/baldrian_bestandsabzug_2027-01-01.csv \
    --out $F/abgeleitet/vorverdichtung/bestand-2027-01-01.json
```

Erwartet: elf Dateien unter `xlsm-TG2015/`
(`Tarifrechnung_table_values.csv` `f31b44e4`), Meldung drei Absaetze,
Bedingungen zwei Absaetze, Profile mit 834 bzw. 811 Zeilen (`30dd55f5`,
`67dfc00a`). Vier Dateien tragen den Fallpfad und haengen damit am
Fallnamen: `export_manifest.json`, `input_bundle.json`,
`meldung-TG2015.json` und `avb-TG2015.json` ergeben im Fall
`faelle/baldrian-lauf2-w` `d3ac582d`, `61575d6a`, `c5c895d8`,
`ce619246`; im Fall des Lauftags (`faelle/baldrian-klv-tg2015-lauf2`)
`ac8aee6f`, `2d0826a7`, `8e39132f`, `ffaa69ba`. Inhaltlich
unterscheiden sie sich nur in diesem Pfad. Die Vorverdichtung ist das
Einzige, was ein Agent von den Quellen sieht.

### 6.3 Agentenschritte (Stufe 1 und 1b)

In der Agenten-Umgebung den Skill `migrationsfall-durchfuehren` auf den
Fall ansetzen. Er erzeugt je Quelle ein Fragment
(`abgeleitet/abox/fragmente/tg2015-tarifrechner.json`,
`tg2015-tarifmeldung.json`), `akteure.json`, den Merge zur A-Box
(`gates.abox_merge`, mit Ledger), Gate P-Q3, die TransformationsSpec
fuer den Bestandsabzug und deren Anwendung (834 Zeilen ohne Befund).
Die Spez entsteht ueber die Python-Schnittstelle, es gibt bei `4b1abf04`
kein Kommando dafuer:

```
python - <<'PY'
from pathlib import Path
from rechner_pipeline.ontologie.abox import ABox
from rechner_pipeline.spez.erzeugen import baue_spez
from rechner_pipeline.spez.validierung import speichere_spez, validate_spez
from rechner_pipeline.spez.fachspez import speichere_fachspez
fall = Path("faelle/baldrian-lauf2-w/abgeleitet")
abox = ABox.model_validate_json((fall / "abox/abox.json").read_text(encoding="utf-8"))
spez = baue_spez(abox, "klv/tg2015")
assert spez.urteil.ergebnis == "parametrierung", spez.urteil
assert validate_spez(spez, abox) == []
print(speichere_spez(spez, fall), speichere_fachspez(spez, abox, fall))
PY
python -m rechner_pipeline.gates.generation_golden --fall $F --generation klv/tg2015 --repo-root . \
    --diagnostics-dir $F/abgeleitet/diagnostics
```

Was der Lauf an dieser Stelle gefunden hat (Abschlussbericht, Abschnitt
3): vierzehn Diskrepanzen zwischen Tarifmeldung und Tarifrechner in
sechs Tarifzellen — je Zelle `tafel` und `zins`, in den beiden
Hausversicherungs-Zellen zusaetzlich `beta1`. Der Tafel-Konflikt ist
keiner (der Rechner nennt nur den Basisnamen der Unisex-Mischung), der
Zins-Konflikt (1,25 % Meldung gegen 1,75 % Rechner) wurde nach
Auskunftsschreiben 3 zur Meldung entschieden, mit dem Abzugsabgleich als
Beleg. Ein zweiter Agent muss dieselben vierzehn finden; entscheiden
darf er sie nicht.

### 6.4 Schluessel, Zeichnungsordnung, A-Q1

Bei `4b1abf04` gibt es kein Kommando, das Schluessel oder Ordnung
erzeugt; beides ist ein Handgriff. Der Schluessel: mindestens 32
zufaellige Byte, Rechte 0600, genau ein Hardlink, ausserhalb des Falls.
Die Ordnung folgt bei diesem Stand dem Schema 1 (`models/zeichnung.py`):
Rolle, Fingerabdruck des Schluessels (SHA-256 der Schluesseldatei),
Gates.

```
mkdir -p ../sicher && chmod 700 ../sicher
(umask 077; head -c 32 /dev/urandom > ../sicher/plv-aktuar.key)
FP=$(sha256sum ../sicher/plv-aktuar.key | cut -c1-64)
cat > ../sicher/zeichnungsordnung.json <<EOF
{
  "schema_version": 1,
  "rollen": {
    "plv-aktuar": {
      "schluessel_sha256": "$FP",
      "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4"]
    }
  }
}
EOF
```

Die Diskrepanzen entscheidet der Mensch je Einzelfall — mit Beleg, wo
eine deterministische Rechnung die Lesart stuetzt:

```
python -m rechner_pipeline.ontologie.entscheide --fall $F --diskrepanz "klv/tg2015/zelle:nichtraucher,einzel#zins" \
    --wert 0.0125 --entscheider plv-aktuar --begruendung "Auskunftsschreiben 3: ..." \
    --beleg abgeleitet/berichte/abzugsabgleich-zins.json \
    --zeichnungsordnung ../sicher/zeichnungsordnung.json --freigabe-schluessel ../sicher/plv-aktuar.key
```

Danach P-Q3 erneut, dann die Zeichnung:

```
python -m rechner_pipeline.gates.abox_validate --fall $F --repo-root .
python -m rechner_pipeline.gates.gate_entscheid --fall $F --gate A-Q1 --entscheid angenommen \
    --entscheider plv-aktuar --rolle mensch --begruendung "..." \
    --zeichnungsordnung ../sicher/zeichnungsordnung.json --freigabe-schluessel ../sicher/plv-aktuar.key --repo-root .
```

Ohne A-Box verweigert A-Q1 mit `keine A-Box ... ohne Stage 1 gibt es
nichts abzunehmen` (Exit 20, kein Snapshot; der Ledger
`abgeleitet/diagnostics/gate_entscheid_aq1.gate.json` haelt den Versuch
als `failed` fest) — das ist der Vertrag, kein Defekt.

### 6.5 Ab hier Kommandofolge

Weiter mit Abschnitt 7.3 (Fall-Config) und 7.5 (Kommandofolge ab
Schritt 3); die Schritte 1 und 2 dort hat Weg A schon gefahren.

## 7 Weg B — deterministisch ab der A-Box

### 7.1 Das Paket der Stufe-1-Artefakte

Das Paket ist das Ergebnis der Agentenschritte und der vierzehn
Entscheide des Laufs — 27 Dateien unter `abgeleitet/` (dazu `README.txt`
und `SHA256SUMS`), unter 0,5 MB, ohne Schluessel und ohne Snapshots. Es
liegt beim Programm und wird auf Anfrage weitergegeben; `SHA256SUMS`
bindet jede Datei.

| Pfad unter `abgeleitet/` | Inhalt |
|---|---|
| `abox/abox.json` (`402dbc6f`), `abox/coverage.json` (`ec3134b3`) | die zusammengefuehrte A-Box mit den vierzehn Aufloesungen; Coverage |
| `abox/fragmente/akteure.json`, `tg2015-tarifmeldung.json`, `tg2015-tarifrechner.json` | die beiden Fragmente und ihre Akteure (Modell, Skill, Stand) |
| `diagnostics/abox_merge.gate.json`, `abox_merge.historie.jsonl` | der Merge-Ledger, den P-Q3 gegen die Fragmente nachrechnet |
| `berichte/abzugsabgleich-zins.json` | der Beleg der Zins-Entscheidung |
| `spez/klv-tg2015.spez.json` (`4763f783`), `fachspez/klv-tg2015.md` (`b8ee000d`) | Spez und Fachspez, Projektion der A-Box |
| `vorverdichtung/` (15 Dateien) | die Vorverdichtung aller fuenf Quellen — inhaltlich identisch mit dem, was Abschnitt 6.2 erzeugt; vier Dateien tragen den Fallpfad des Lauftags |
| `transformation/bestandsabzug-2026-01-01.spec.json` (`f5c7888d`) | die TransformationsSpec des Bestandsabzugs |
| `bestand-config.toml` | die Fall-Config des Lauftags (Abschnitt 7.3) |

### 7.2 Fall anlegen, Paket einlegen, A-Q1 zeichnen

Fall anlegen und alle sechzehn Dateien registrieren wie in 6.1 (die
Auskunftsschreiben diesmal gleich mit). Das Paket auspacken und dort
pruefen, dann den Inhalt seines Verzeichnisses `abgeleitet/` in den
Fall kopieren (`README.txt` und `SHA256SUMS` bleiben draussen):

```
cd <paket> && sha256sum -c SHA256SUMS && cd -        # 28 x OK
cp -a <paket>/abgeleitet/. faelle/baldrian-lauf2-w/abgeleitet/
```

Schluessel und Ordnung wie in 6.4 anlegen. Dann:

```
F=faelle/baldrian-lauf2-w
python -m rechner_pipeline.gates.abox_validate --fall $F --repo-root .
python -m rechner_pipeline.gates.gate_entscheid --fall $F --gate A-Q1 --entscheid angenommen \
    --entscheider plv-aktuar --rolle mensch --begruendung "Wiederholung Lauf 2: Stufe 1 aus dem Paket uebernommen" \
    --zeichnungsordnung ../sicher/zeichnungsordnung.json --freigabe-schluessel ../sicher/plv-aktuar.key --repo-root .
```

Erwartet: P-Q3 `passed`, 18 Formelpruefungen, 14 aufgeloest, 0 offen;
`coverage.json` wird neu geschrieben und ist byte-gleich. A-Q1
`angenommen`, Snapshot unter `entscheide/A-Q1-<sha256>.json` mit 26
gebundenen Artefakten (28, wenn vorher Abschnitt 6.2 im selben Fall
gefahren wurde: die beiden `extract`-Ledger kommen dazu). Die
Aufloesungen in der A-Box tragen die
Zeichnungsordnung des Laufs, nicht die eigene; wer das Paket einlegt,
uebernimmt die Entscheide des Laufs und zeichnet das mit A-Q1.

### 7.3 Die Fall-Config

`bestand-config.toml` ist `configs/bestand_klv.toml` plus ein
`[[generation]]`-Block fuer die TG2015 mit `sample_size = 0` (die
Vertraege werden uebernommen, nicht erzeugt), den Rechnungsgrundlagen
aus `abgeleitet/bestand/generation-zellen.toml` (schreibt Schritt 4 der
Kommandofolge aus der Spez) und den sechs `[[generation.zelle]]`-Bloecken
daraus. Das Paket bringt die Config des Lauftags mit.

Achtung, dokumentierter Fehler des Laufs: Die Config des Lauftags traegt
fuer die TG2015 `zins = 0.0175` und `beta1 = 0.0` in den beiden
Hausversicherungs-Zellen — den Stand vor der A-Q1-Entscheidung.
`generation-zellen.toml`, aus der gezeichneten Spez erzeugt, traegt
`zins = 0.0125` und `beta1 = 0.01`. Am Lauftag ist die Config nach der
Zeichnung nicht nachgezogen worden (Korrektur 24 vom 07.09.2026,
Nachtrag im Abschlussbericht). Wer den gefuehrten Bestand byte-gleich
zum Lauftag will, nimmt die Paket-Config; wer ihn fachlich richtig will,
zieht die drei Werte aus `generation-zellen.toml` nach. Die
Pruefstrecke (P-K1, A-M1 bis A-M3, Migrationssuite) liest die Config
nicht und ist davon unberuehrt.

### 7.4 Die Auskuenfte als Parameter

Die Parameter der Kommandofolge, die nicht aus dem Code stammen, stehen
als `provenienz.parameter` im Schichtbeleg des Laufs:

```
LIEF="--erhoehungssatz 0.05 --red-verfahren teilkuendigung --scheiben-mit-gamma1 \
      --red-anteil-kandidat 0.5 --red-anteil-kandidat 0.6 --red-anteil-kandidat 0.75 \
      --red-anteil 7000396=0.60 --red-anteil 7000679=0.60"
```

Aus den Auskunftsschreiben stammen `--erhoehungssatz` (Dynamiksatz,
Auskunft 1), `--red-anteil-kandidat` (die drei ueblichen
Herabsetzungsanteile, Auskunft 1) und `--red-anteil` fuer die Policen
7000396 und 7000679 (Auskuenfte 2 und 4: bei diesen beiden
reproduzieren alle drei Kandidaten den gelieferten Ankerwert gleich gut,
die Wahl ist nicht ableitbar; das abgebende Unternehmen hat den Anteil
genannt). `--red-verfahren teilkuendigung`, `--scheiben-mit-gamma1` und
`--stoab-je-baustein` sind die Ausgestaltung des migrierten Tarifplans
aus dem Bedingungswerk der Lieferung (Abschlussbericht und
`baldrian-lauf2-veraenderungen.md`, Abschnitt 1).

Ohne die beiden `--red-anteil` endet A-M1 mit 98/100, A-M2 mit 98/100
und die Migrationssuite mit 832/834 — genau die Policen 7000396 und
7000679, mit Residuen von 12,76 bis 250,00 EUR. Ohne alle
Auskunftsparameter bricht der Schichtbeleg (Schritt 7,
`gates.verankerung_belegen`) mit Exit 1 ab: `Police 7000004: mehrere
Alt-Ereignisse sind ohne --erhoehungssatz unterbestimmt`; die Uebernahme
(Schritt 4) nimmt auf diesem Stand noch keine Auskunftsparameter. Beides
ist Vertrag, kein Defekt: Was die Quelle nicht hergibt, wird als
Auskunft registriert, nicht geraten.

### 7.5 Die Kommandofolge

Aus der Repository-Wurzel, `F` und `LIEF` wie oben gesetzt. Die Folge
ist die gemessene Reihenfolge des Lauftags; die Titel sind die des
Laufs (sie stehen im Abnahmebericht).

```
A=$F/abgeleitet; T=$A/transformation/bestandsabzug-2026-01-01; B=$A/bestand; N=$A/bestand-nach; R=$A/berichte
CFG=$A/bestand-config.toml; S=abgeleitet/schichten/verankerung_schichten.json

# 1 P-Q3, 2 P-K1
python -m rechner_pipeline.gates.abox_validate --fall $F --repo-root .
python -m rechner_pipeline.gates.generation_golden --fall $F --generation klv/tg2015 --repo-root . --diagnostics-dir $A/diagnostics
# 3 Transformation: Zeilen
python -m rechner_pipeline.gates.transformation_anwenden --fall $F --spec $T.spec.json --anwenden --zeilen $T.zeilen.json
# 4 Uebernahme (schreibt bestand/, merkmale, verankerung, generation-zellen.toml)
python -m rechner_pipeline.gates.bestand_uebernehmen --fall $F --zeilen $T.zeilen.json --tarif-generation TG2015 \
    --stichtag 2026-01-01 --vorgeschichte baldrian_gevo_metadaten.csv --generation-spez klv/tg2015 --out-dir $B
# 5 Transformation: Ergebnis mit Ziel (bindet den fertigen Bestand)
python -m rechner_pipeline.gates.transformation_anwenden --fall $F --spec $T.spec.json --anwenden --zeilen $T.zeilen.json \
    --ergebnis $T.ergebnis.json --ziel $B/bestand.parquet
# 6 P-B1 auf der Uebernahme (jetzt muss die Fall-Config liegen, Abschnitt 7.3)
python -m rechner_pipeline.gates.bestand_validate --portfolio $B/bestand.parquet --historie $B/historie.parquet \
    --ledger $B/ledger.parquet --bis 2026-01-01 --config $CFG --repo-root . --diagnostics-dir $A/diagnostics
# 7 Schichtbeleg
python -m rechner_pipeline.gates.verankerung_belegen --fall $F --repo-root . --generation klv/tg2015 \
    --formfunktion proportional_zur_basis --zeilen $T.zeilen.json --vorgeschichte baldrian_gevo_metadaten.csv \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag.json $LIEF
# 8-10 aktuarieller Test, 11-13 Gate-Vorlagen
for M in "A-M1 stichtag Stichtagstest" "A-M2 verlauf Verlaufstest" "A-M3 geschaeftsvorfaelle Geschaeftsvorfalltest"; do
  set -- $M
  python -m rechner_pipeline.gates.aktuartest_lauf --fall $F --abnahme $1 --generation klv/tg2015 \
      --erwartungswerte baldrian_erwartungswerte_$2.json --stichprobe baldrian_erwartungswerte_stichprobe.json \
      --bestand $B/bestand.parquet --zeilen $T.zeilen.json --vorgeschichte baldrian_gevo_metadaten.csv \
      --stoab-je-baustein --schicht $S --repo-root . $LIEF
  python -m rechner_pipeline.gates.aktuartest --fall $F --abnahme $1 --titel "$3 Baldrian KLV TG2015 Lauf 2"
done
# 14 Migrationssuite ueber zwei Stichtage
python -m rechner_pipeline.gates.migrationssuite_lauf --fall $F --generation klv/tg2015 \
    --abzug-1 baldrian_bestandsabzug_2026-01-01.csv --abzug-2 baldrian_bestandsabzug_2027-01-01.csv \
    --gevo-protokoll baldrian_gevo_protokoll_2026.csv --bestand $B/bestand.parquet \
    --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 --zeilen $T.zeilen.json --vorgeschichte baldrian_gevo_metadaten.csv \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag.json --stoab-je-baustein --dk-stichtag jahrestag \
    --schicht $S --repo-root . $LIEF
# 15 Fortschreibung: Eigenbestand plus Uebernahme in einem Lauf (Abschnitt 5)
python -m rechner_pipeline.bestand.cli_fortschreibung --config $CFG --bis 2027-01-01 --neuzugang-ab 2026-01-01 \
    --uebernahme $B --merkmale $B/merkmale.parquet --out-dir $N
# 16 Bestandsberichte: Quellsicht vor, gefuehrter Gesamtbestand nach
python -m rechner_pipeline.bestand.cli_report --portfolio $B/bestand.parquet --historie $B/historie.parquet \
    --ledger $B/ledger.parquet --merkmale $B/merkmale.parquet --config $CFG --bis 2026-01-01 \
    --titel "Bestandsbericht Baldrian KLV TG2015 VOR Migration (Quellsicht, uebernommener Bestand)" --out $R/bestandsbericht-vor.html
python -m rechner_pipeline.bestand.cli_report --portfolio $N/bestand_gesamt.parquet --historie $N/historie.parquet \
    --ledger $N/ledger.parquet --scheiben $N/scheiben.parquet --merkmale $B/merkmale.parquet --config $CFG \
    --bis 2027-01-01 --stichtag 2026-01-01 \
    --titel "Bestandsbericht Baldrian KLV TG2015 NACH Migration (gefuehrter Gesamtbestand)" --out $R/bestandsbericht-nach.html
# 17 Abnahmebericht (Vorlage fuer A-M4)
python -m rechner_pipeline.gates.abnahmebericht --fall $F --suite $R/migrationssuite.json \
    --titel "Migrationsabnahme Baldrian KLV TG2015 Lauf 2" --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 \
    --spec $T.spec.json --transformation-ergebnis $T.ergebnis.json \
    --bestandsbericht-vor $R/bestandsbericht-vor.html --bestandsbericht-nach $R/bestandsbericht-nach.html --repo-root .
# 18 die vier Zeichnungen, in dieser Reihenfolge (A-M4 verlangt A-M1 bis A-M3 und P-K1 desselben Stands)
for G in A-M1 A-M2 A-M3 A-M4; do
  python -m rechner_pipeline.gates.gate_entscheid --fall $F --gate $G --entscheid angenommen \
      --entscheider plv-aktuar --rolle mensch --begruendung "Wiederholung Lauf 2" \
      --zeichnungsordnung ../sicher/zeichnungsordnung.json --freigabe-schluessel ../sicher/plv-aktuar.key --repo-root .
done
```

Jedes Kommando muss mit Exit 0 enden; ein anderer Exit-Code nennt in
der Meldung, was fehlt. Exit 0 ist notwendig, nicht hinreichend:
`aktuartest_lauf` und `migrationssuite_lauf` sind Produzenten und enden
auch bei rotem Urteil mit 0 — die Zeile `Urteil: bestanden` bzw. `834
bestanden` lesen; die Gates dahinter (Schritte 11 bis 13 und 17) urteilen
mit dem Exit-Code. Die Gates schreiben nach
`abgeleitet/diagnostics/<gate>.gate.json`; Pruefungszahl und maximales
Residuum der Suite stehen in der JSON-Ausgabe von Schritt 17
(`summary.pruefungen`, `summary.max_residuum`).

Erwartete Begleitmeldungen, die zum Lauf gehoeren und die Kennzahlen
nicht aendern: in Schritt 4 der `HINWEIS`, dass 834 von 834 gelieferten
Geburtsdaten vom konstruierten abweichen (die Lieferung traegt echte
Geburtsdaten, der Kern rechnet mit dem Eintrittsalter); in den Schritten
7 bis 14 je vier bis fuenf `WARNUNG`-Zeilen `Anfangszustand nicht
ableitbar` fuer beitragsfrei gelieferte Vertraege ohne Ankerwert
(Policen 7000539, 7000586, 7000722, 7000754, 7000910).

## 8 Referenzwerte

| Schritt | Lauf 02.09.2026 | Wiederholung auf 4b1abf04 |
|---|---|---|
| P-K1 Golden Master | 616 Werte, 0 Abweichungen (4 Skalare, 51 Tabellenzeilen) | gleich |
| Uebernahme | 834 Vertraege, 160 Historienzeilen (beitragsfrei), 994 Ledgerzeilen, 1668 Merkmale | gleich; `bestand.parquet` `c31b5b71` byte-gleich |
| Schichtbeleg | 834/834 getragen, Residuensumme -0,14, max 0,02 | gleich |
| A-M1 Stichtagstest | 100/100, max. Residuum 0,022347698661178583 | gleich |
| A-M2 Verlaufstest | 100/100, max. Residuum 0,020593604938767385 | gleich |
| A-M3 Geschaeftsvorfalltest | 166/166, max. Residuum 0,010021519265137613 | gleich |
| Migrationssuite | 834/834, 2508 Pruefungen, max. Residuum 0,03151236512348987 | gleich |
| Fortschreibung | 3054 Basisvertraege (834 uebernommen), 39 Neuzugaenge, 9607 GeVos; Gesamtbestand 3093 | gleich |
| Abnahmebericht | `passed`, Gate-Version 1.10.0, keine Abnahmehindernisse | gleich; `migrationsabnahme.html` `e7fa67f0` byte-gleich |

Die Residuen sind bit-gleich, nicht nur gerundet gleich.

## 9 Bekannte Abweichungen zum Lauftag

* **Belege und Ledger** (`aktuartest*.json`, `migrationssuite.json`,
  `verankerung_schichten.json`, der P-K1-Beleg, alle `*.gate.json` und
  `*.historie.jsonl`) sind nicht byte-gleich. Fachlich sind sie es: Die
  einzigen Unterschiede sind `system.branch` (`fallbericht` am Lauftag,
  `HEAD` in einer Auscheckung), `system.dirty` (`ja` am Lauftag — im
  Arbeitsbaum lagen ungesicherte Dateien ausserhalb des Pakets —, `nein`
  in einer sauberen Auscheckung), Zeitstempel und Versuchszaehler. Die
  HTML-Vorlagen des aktuariellen Tests weichen in genau diesen zwei
  Tabellenzellen ab.
* **`bestand/ledger.parquet` und `generation-zellen.toml`** weichen vom
  Lauftag ab, weil das `bestand/` des Lauftags vor der
  A-Q1-Zinsentscheidung erzeugt wurde (13:10 Uhr; die Entscheidung fiel
  14:15 Uhr; die Spez wurde danach neu geschrieben). In der Wiederholung
  liest die Uebernahme die gezeichnete Spez: 160 PEX-Betraege anders,
  Summe 1.693.904,53 statt 1.716.338,01 EUR. Folgeabweichungen:
  `bestand-nach/ledger.parquet`, beide Bestandsberichte, die
  Eingangshashes von P-B1 und die davon abhaengigen Hashes im
  Abnahmebericht-Ledger. Zum Nachpruefen die Hashes des Lauftags gegen
  die der Wiederholung: `bestand/ledger.parquet` `9140be75` gegen
  `519ba44b`, `bestand/generation-zellen.toml` `6dc8f7d3` gegen
  `a7cc5978`, `bestand-nach/ledger.parquet` `c8814319` gegen `f3067896`,
  `berichte/bestandsbericht-vor.html` `6a8b136e` gegen `ed5c2a20`,
  `berichte/bestandsbericht-nach.html` `82d9d180` gegen `dc5007d5`. Der
  Lauf hat also seinen P-B1-Beleg auf einem
  Ledger mit 1,75 % gezeichnet, waehrend die gezeichnete Spez 1,25 %
  sagt — dieselbe Inkonsistenz wie in der Config (7.3), am 07.09.2026
  behoben.
* **`entscheide/`** enthaelt eigene Snapshots mit eigenem
  Fingerabdruck, nicht die des Laufs. Die Snapshots des Laufs sind
  HMAC-signiert und mit einem anderen Schluessel nicht nachpruefbar; das
  ist gewollt. `eingang.json` traegt eigene Registrierzeitpunkte.
* Der Lauf hatte eine `abgeleitet/bestand-vor/` und keinen
  `fuehrungsprobe`-Schritt; beides ist bei `4b1abf04` kein
  Pflichtbeleg. `--anfangszustand`, `--stoab-je-baustein` und
  `--formfunktion` in `bestand_uebernehmen` sowie `--config` in
  `verankerung_belegen` gibt es auf diesem Stand noch nicht; die
  Fortschreibung schreibt kein Laufmanifest.

## 10 Wiederholung auf einem juengeren Stand

Die Kennzahlen aus Abschnitt 8 sind auf `1dc736b` (Kern 3.5.0)
nachgemessen und gleich, bis auf die Gate-Versionen (A-M4 3.0.0 statt
1.10.0, P-K1 1.0.0 statt 0.2.0, P-B1 4.0.0 statt 2.0.0). Was sich
aendert:

* **Zeichnungsordnung nach Schema 2** (ADR-018, ab `1dc736b`): Rollen
  heissen `mensch/<funktion>` oder `agent/<name>` und tragen eine
  `schluesselklasse`; Schema 1 wird mit einer Meldung abgewiesen. Fuer
  eine natuerliche Person:

  ```
  {"schema_version": 2, "rollen": {"mensch/plv-aktuar": {"schluessel_sha256": "<FP>",
      "schluesselklasse": "mensch", "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4"]}}}
  ```

  `--rolle mensch/plv-aktuar` statt `--rolle mensch`. Eine Rolle der
  Klasse `simulation` braucht zusaetzlich `--mandat <datei>`; das ist
  der Weg der Vorfuehrung, nicht der eines Menschen.
* **Die Uebernahme materialisiert den Anfangszustand**:
  `bestand_uebernehmen` bekommt `--anfangszustand materialisieren
  --anker-erwartungswerte baldrian_erwartungswerte_stichtag.json
  --stoab-je-baustein` und die `LIEF`-Parameter; `bestand.parquet` ist
  dann ein anderer (`c51790ac`: Grundsumme plus 2307 Alt-Scheiben statt
  der gelieferten Summe), die Pruefstrecke rechnet identisch, weil sie
  den Anfangszustand aus der Vorgeschichte selbst herleitet.
  `verankerung_belegen` schreibt `schichten.parquet` in das
  Uebernahme-Verzeichnis; P-B1 bekommt `--scheiben --merkmale
  --schichten --verankerung` dazu. Ab `17091b39` verlangt A-M4 ein
  Laufmanifest, das `verankerung_belegen --config --stichtag` schreibt,
  und die Fuehrungsprobe (`gates.fuehrungsprobe`) ist Pflichtbeleg.
* **Massgeblich ist immer der Skill des ausgecheckten Stands.** Die
  Kommandofolge dieser Anleitung ist die von `4b1abf04`; `--help`
  jedes Kommandos nennt die Optionen seines Stands. Wer auf einem
  juengeren Stand faehrt, faehrt den Fall neu und zeichnet ihn neu — die
  Belege binden den Stand, und ein alter Snapshot gilt auf einem neuen
  Stand nicht.
