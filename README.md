# Rechner-Pipeline — agentische Bestandsmigration Leben

> **Status:** öffentlicher Prototyp, lauffähig Ende-zu-Ende.
> Vorgängerprojekt: [portxlpy](https://github.com/bartlmac/portxlpy).
> Was der aktuelle Stand kann, was er bewusst noch nicht kann und was
> sich zuletzt geändert hat: [`CHANGELOG.md`](CHANGELOG.md).

## Was dieses Repository ist

Ein **agentisches System für die Bestandsmigration Leben und die
Entwicklung des zugehörigen Rechenkerns**. Es löst zwei eng verzahnte
Aufgaben:

1. **Migration:** fremde Tarifgenerationen samt Bestand aus heterogenen
   Lieferungen (Tarifrechner, Tarifmeldung, Bestandsabzüge) in ein
   Zielsystem übernehmen — nachvollziehbar, mit menschlichen
   Entscheidungen an genau den Stellen, an denen Quellen sich
   widersprechen oder das Zielsystem erweitert werden muss.
2. **Rechenkern-Entwicklung:** der Zielkern wird mit KI-Unterstützung
   weiterentwickelt — unter einer Architektur, die Korrektheit erzwingt
   statt erhofft.

Die Arbeitsteilung ist der Kern der Methodik:

- **Agenten schlagen vor** — als versionierte Rollen (Skills): Quellen
  extrahieren, Bestandsdaten-Mappings vorschlagen, Konflikte
  aufbereiten, Code unter den Architekturregeln entwickeln. Ein Agent
  einer späteren Stufe liest nie die Rohquelle einer früheren.
- **Deterministischer Code entscheidet** — Zusammenführung, Vergleich,
  Abdeckung, Transformation, Abnahmerechnung. In `src/` gibt es keine
  Modell-, Provider- oder Token-Fläche und keinen LLM-Pfad in einer
  Prüfung.
- **Menschen entscheiden fachlich** — Widersprüche zwischen Quellen
  werden Objekte mit beiden Lesarten, nie stille Annahmen; jede
  Abnahme ist ein menschliches Gate mit unveränderlichem Snapshot.

## Architektur

**Schichten** (Import-Regeln maschinell erzwungen,
`ontologie/code_karte`):

```
quellen  ->  ontologie  ->  spez  ->  kern  ->  bestand  ->  qa  ->  gates
             (T-Box/A-Box)          (Zielkern)  (GeVo-Strom)        (Abnahme)
```

- `quellen/`: deterministische Vorverdichter je Quelltyp (Excel-Mappen,
  DOCX-Meldungen, CSV-Bestandsabzüge) — Agenten lesen nie Rohdateien.
- `ontologie/`: die T-Box (was eine Tarifgeneration ausmacht) und je
  Fall eine A-Box, in der **jede Aussage Provenienz trägt** (Quelle,
  SHA-256, Fundstelle, Akteur). Widersprüche sind Diskrepanz-Objekte.
  Dazu die Datentransformation (Quell-Datenmodell -> Ziel-Ontologie:
  der Agent schlägt das Mapping vor, Code validiert und wendet an,
  Unklarheit blockiert bis zur menschlichen Entscheidung) und der
  **Code-Index**: Module und Tests deklarieren ihren Fachknoten
  (`Knoten: klv/tg2015`), daraus werden Impact, Schichtenprüfung und
  Landkarten-Sichten **berechnet** statt gepflegt — ausgelegt auf ein
  Zielbild von einer Million Codezeilen, in dem es kein Bild "der
  Codebasis" mehr gibt, nur begrenzte Ausschnitte
  (`docs/architektur/landkarte.md`).
- `spez/`: die abgenommene Lesart einer Generation als Parametrierung
  des Kerns — samt maschinell berechnetem Struktur-Urteil
  (Parametrierung vs. neues Produkt).
- `kern/`: der Zielrechenkern (unten).
- `bestand/`: der fortschreibbare Bestand auf dem Kern (unten).
- `qa/` und `gates/`: Abnahmerechnungen und blockierende Prüf-Gates.

**Ablauf eines Migrationsfalls** (Details:
`docs/architektur/migrations-pipeline-v01.md`): Fall-Arbeitsbereich
anlegen und Quellen registrieren (`eingang/` mit SHA-256-Register, nie
still überschrieben — hier beginnt die Provenienzkette) -> je Quelle
Vorverdichtung und Agenten-Extraktion -> deterministischer Merge zur
A-Box -> Diskrepanzen als Entscheidungs-Dossier an den Menschen
(Gate G-1) -> Spez -> parametrierter Kern -> Abnahme gegen die
Lieferung (Gate O3, Bestandsabzugs-Abgleich) -> Transformation und
Übernahme des Bestands -> **Migrationsabnahme über zwei Stichtage**:
Deckungskapital am Migrations- und am Folgestichtag plus die
Geschäftsvorfälle dazwischen, gegen die gelieferten Erwartungswerte
(`qa/migrationssuite`), zusammengefasst im HTML-Abnahmebericht
(`gates/abnahmebericht`) mit Bestandsberichten vor/nach — als Vorlage
für das menschliche Gate G-2.

Braucht die Migration eine **Code-Änderung** (Berechnungskatalog,
Bewertung, Produktdefinition), läuft sie als kleines, knotengebundenes
Inkrement auf dem einen Trunk — Landung nur mit grüner Gesamt-Suite
einschließlich der Anker aller anderen Fälle (ADR-007: parallele
Migrationen in einem Kern).

Die Agenten-Rollen samt Grenzen stehen im Katalog
`docs/architektur/skill-architektur.md`; Architektur-Entscheidungen als
ADRs unter `docs/architektur/`.

## Die Prüf-Gates

Jedes Gate schreibt ein JSON auf stdout und ein Ledger in den
Diagnostics-Ordner; ein Nicht-Null-Exit ist **blockierend** und wird
nie zur Warnung abgeschwächt.

| Gate | Kommando | Prüft |
|---|---|---|
| G0 | `gates.extract` | deterministische Vorverdichtung einer Quellmappe (Formeln, Werte, Namen, VBA) |
| O0 | `gates.abox_merge` | Zusammenführung der Extraktions-Fragmente zur A-Box |
| O1 | `gates.abox_validate` | A-Box gegen T-Box: Abdeckung, Wertebereiche, Formel-Rück-Check |
| O3 | `gates.generation_golden` | der parametrierte Kern gegen die Erwartungswerte der Lieferung |
| P9 | `gates.gate_entscheid` | unveränderliche Snapshots der menschlichen Gates (G-1, G-2, G-T) |
| B1 | `gates.bestand_validate` | Bestandsschema und Bewegungs-Identitäten je Jahr, Track und Maß |

Dazu prüfen Hypothesis-Tests die aktuariellen Identitäten des Kerns
(`tests/test_kern_algebraisch.py`: qx-Schranken, Barwert-Bilanz
`A + d·ä = 1`, Rekursionen, Äquivalenzprinzip) — unabhängig von jeder
Quell-Lieferung.

## Die Beispielartefakte: die PLV-Fiktion

Vorgeführt wird das System an der fiktiven **Pfefferminzia
Lebensversicherung (PLV)**: der Zielkern ist der PLV-Kern, der Bestand
der PLV-Bestand, und Migrationsfälle übernehmen fremde Bestände in die
PLV. Die Artefakte der Fiktion enthalten keine echten Vertrags-,
Kunden- oder Bestandsdaten; Struktur und Rechnungsgrundlagen sind aus
realen Vorlagen abgeleitet, Unternehmen und Bestände sind frei
erfunden:
`configs/` hält die Bestands-Konfigurationen der PLV
(TOML, von Suite und Berichten geladen), `tests/fixtures/` synthetische
Quellmappen für die Extraktions-Tests, und `lieferungen/` das Frachtgut
der Showcase-Migrationen — die Lieferung eines fiktiven abgebenden
Unternehmens, mit der jeder die Migration selbst durchführen kann
(`ONBOARDING.md`, Abschnitt 3). Einen impliziten Eingangskanal gibt es
nicht: In einen Fall gelangt eine Lieferung nur über die ausdrückliche
Registrierung.

**Der Rechenkern** (`rechner_pipeline.kern`): KLV und
Berufsunfähigkeit auf einem gemeinsamen (Semi-)Markov-Zustandsmodell
mit Thiele-Rückwärtsrekursion; Tafelwerk als reine qx-Vektoren mit
harten Erschöpfungsgrenzen; Monatsreserven für Bilanz-Stichtage
(unterjährige Interpolation) und vertragsweite Bewertung dynamischer
Erhöhungsscheiben. Eine Tarifgeneration, deren Leistungsmerkmale der
Kern bereits kennt, ist eine **Parametrierung** über den Modellpunkt —
kein neuer Kern-Code für die Generation selbst (der Normalfall einer
Migration ist das nicht, siehe oben und ADR-007):

```python
import dataclasses
from rechner_pipeline.kern import KLV_DEFAULT, berechne

ergebnis = berechne(KLV_DEFAULT)
mp = dataclasses.replace(KLV_DEFAULT, x=30, sex="F", zins=0.0225,
                         tafel="DAV2008_T")
ergebnis2 = berechne(mp)
```

Die klassische Kommutationsrechnung lebt als **separater Zweitkern**
(`rechner_pipeline.kommutationskern`) ausschließlich für den
Kreuz-Check (`qa/ueberleitung`) — sie ist kein Bestandteil des
Zielkerns.

**Die Tarifpläne** (`docs/tarifplaene/klv.md`, `bu.md`): die
Fachdokumente des Zielkerns in seiner eigenen Mathematik
(Zustandsmodell, GeVo-Katalog mit Betragsformeln, Stellschrauben,
Gültigkeitsgrenzen), gerendert über eine gepinnte Doku-Engine
(`docs/engine/`).

**Der Bestand** (`rechner_pipeline.bestand`): synthetische,
deterministisch reproduzierbare Bestände, deren Datenmodell 1:1 auf dem
Kern-Contract liegt. Die Entwicklung über die Zeit ist ein einziger
Strom datierter Geschäftsvorfälle (Neuzugang, Storno, Tod,
Beitragsfreistellung, dynamische Erhöhungen als eigene Scheiben,
Ablauf); jeder Betrag kommt aus dem Kern, die Eintrittsraten aus einer
eigenen Annahmenschicht (3. Ordnung), und das Bewegungskonto führt die
Identität Anfangsbestand + Zugang − Abgang = Endbestand exakt in der
Struktur der BaFin-Nachweisungen. Der Bestandsbericht rendert das als
selbst-enthaltene HTML-Seite:

```bash
python -m rechner_pipeline.bestand.cli_fortschreibung --config configs/bestand_gesamt.toml ...
python -m rechner_pipeline.bestand.cli_report --portfolio <parquet> --out bericht.html ...
```

**Die Migrationsfälle** (`faelle/`, lokale Arbeitsbereiche, nicht
eingecheckt): je Fall die registrierten Quellen, die A-Box mit
Provenienz, die menschlichen Entscheide (append-only) und alle
abgeleiteten Artefakte bis zum Abnahmebericht. Der erste durchgängige
Fall übernimmt den KLV-Bestand (Tarifgeneration TG2015) der fiktiven
**Baldrian Leben** in die PLV — inklusive der Datentransformation aus
einem fremden Datenmodell und der Zwei-Stichtags-Abnahme; die
Lieferung dazu liegt unter `lieferungen/baldrian/` zum
Selbst-Durchführen.

## Schnellstart

Voraussetzung: **Python 3.11 oder neuer**. Kein LLM-Key nötig — das
Paket ist SDK-frei; Agenten arbeiten über ihre CLIs (unten) auf dem
Repo.

```bash
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline

python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest                     # volle Suite
```

Dieser Weg pinnt die **direkten** Abhängigkeiten exakt und lässt pip
alles Transitive frei auflösen — bequem, aber nicht reproduzierbar. Wer
denselben Paketstand will, den die CI fährt, installiert über die
Pin-Dateien:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

Die Suite endet mit vier Skips (`... passed, 4 skipped`): vier
Regressionstests hängen an einem lokalen, nicht eingecheckten
Fall-Arbeitsbereich
(`faelle/archiv/baldrian-klv-tg2015`) und skippen überall dort, wo er
fehlt — im frischen Clone, in der CI und auf jedem Rechner ohne diesen
Fall. Darunter ist der einzige Ende-zu-Ende-Beleg für Gate O3. Details
in `ONBOARDING.md`, Abschnitt 5.

Einen Fall anlegen und die Pipeline fahren:

```bash
python -m rechner_pipeline.fall anlegen --fall faelle/mein-fall
python -m rechner_pipeline.fall registrieren --fall faelle/mein-fall --datei <quelle>
python -m rechner_pipeline.fall status --fall faelle/mein-fall

# Dazwischen liegen die Agenten-Stufen (Vorverdichtung, Extraktion je
# Quelle, Merge zur A-Box) — ohne sie enden O1 und O3 planmäßig mit
# Exit 2 und nennen die fehlende Datei. Siehe ONBOARDING.md, Abschnitt 3.
python -m rechner_pipeline.gates.abox_validate --fall faelle/mein-fall --repo-root .   # O1
python -m rechner_pipeline.quellen.tafel_import --fall faelle/mein-fall --generation klv/tgX
python -m rechner_pipeline.gates.generation_golden --fall faelle/mein-fall \
    --generation klv/tgX --repo-root .                                                 # O3

# menschliche Gates:
python -m rechner_pipeline.ontologie.entscheide --fall ... --diskrepanz ... \
    --wert ... --entscheider ... --begruendung ... --rolle mensch
python -m rechner_pipeline.gates.gate_entscheid --fall ... --gate G-1 \
    --entscheid angenommen --entscheider ... --begruendung ... --rolle mensch
```

`--rolle` ist bei beiden Kommandos Pflicht (ohne das Flag brechen sie
mit Exit-Code 2 ab) und trägt die Grenze zwischen Mensch und Agent:
`entscheide` nimmt ausschließlich `--rolle mensch` — endgültige
Diskrepanz-Auflösungen sind Menschen vorbehalten. Bei `gate_entscheid`
ist `--rolle agent` zulässig, ein Agent kann ein menschliches Gate damit
aber nur **ablehnen**, nie annehmen.

Die Code-Ontologie navigiert und begrenzt Änderungen:

```bash
python -m rechner_pipeline.ontologie.code_index --tests tests    # Knoten <-> Modul/Test, Drift
python -m rechner_pipeline.ontologie.code_karte                  # Import-Graph vs. Schichtenkarte
git diff --name-only | python -m rechner_pipeline.ontologie.impact
python -m rechner_pipeline.ontologie.landkarte --format mermaid --umfang knoten --out k.mmd
```

## Reproduzierbarkeit und Verlässlichkeit

- **Deterministisch:** gleiche Eingaben ergeben byte-identische
  Artefakte (Extrakte, Berichte, Parquet-Bestände, Landkarten); Seeds
  stehen in Configs, nie im Code.
- **SDK-frei:** keine Modell-Abhängigkeit im Paket; die Erwartungswerte
  jeder Abnahme stammen aus der Lieferung, nie vom Modell.
- **Fail fast:** fehlende Tafeln, verletzte Schichtregeln, Bausteine
  ohne Ontologie-Knoten und Register-Abweichungen im Fall-Eingang sind
  harte Fehler, keine Warnungen.
- **Gepinnte Abhängigkeiten:** die direkten exakt in `pyproject.toml`,
  ihre transitive Hülle in `requirements.txt` /
  `requirements-dev.txt` — das ist der Installationsweg für
  reproduzierbare Läufe (Schnellstart oben) und der, den die CI fährt.
  Der bequeme Weg `pip install -e ".[dev]"` löst das Transitive frei
  auf und ist damit tagesabhängig.

## Agenten-Anbindung

Claude-CLI wird über `.claude/skills/` unterstützt, Codex-CLI über
`AGENTS.md` plus gespiegelte Skills unter `.agents/skills/`; die
Spiegel-Parität ist test-erzwungen. Die portable Basis ist: lokale
Dateien plus einfache Python-Kommandos — kein MCP/RPC-Pfad.

## Mitwirken

Beiträge laufen über GitHub-Collaborators auf Vertrauensbasis; siehe
`CONTRIBUTING.md` und `AGENTS.md`. **Arbeitsweise am gemeinsamen
Branch:** klonen und lokal arbeiten, kein direkter Push in den
gemeinsamen Branch — Änderungen werden nach Absprache übernommen.

## Lizenz

MIT — siehe `LICENSE`.

Die Rechnungsgrundlagen (`src/rechner_pipeline/kern/tafeln.xml`) sind
veröffentlichte DAV-Tafeln bzw. synthetische Vektoren; die Herkunft
steht bei den meisten Vektoren in der Datei selbst (siehe
`CONTRIBUTING.md`).
