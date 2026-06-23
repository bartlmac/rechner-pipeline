# Rechenkernentwicklung mit KI – Methodik, Leitplanken und Proof of Concept

> **Status:** öffentlicher Proof of Concept. Begleitender Arbeitsraum eines DAV-Projekts unter der AG Bestandsmigration. Vorgängerprojekt: [portxlpy](https://github.com/bartlmac/portxlpy) (handwerklicher und industrieller Workflow nebeneinander).

## Schnellstart

Voraussetzungen für einen vollständigen Demo-Lauf: **Python 3.11 oder neuer**
und ein gültiger LLM-API-Key (`OPENAI_API_KEY` **oder** `ANTHROPIC_API_KEY`).
Optional kann statt eines Cloud-Providers ein lokal laufendes Ollama-Modell
über die OpenAI-kompatible API genutzt werden.
Die Excel-Extraktion läuft standardmäßig **plattformneutral ohne Microsoft
Excel** (openpyxl + oletools) und damit auf Windows, macOS und Linux. Das
Legacy-Backend über Excel-COM (`--export-backend com`) bleibt für Windows
verfügbar.

```bash
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline

python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # API-Key bzw. *_FILE-Pointer eintragen (s. u.)

python pipeline.py                          # OpenAI-kompatibler Provider (Default)
python pipeline.py --provider anthropic     # Anthropic (Claude)
python agentic_pipeline.py                  # LangGraph-Variante mit Quality-Gates
```

`requirements.txt` ist bewusst nur ein dünner Verweis auf
`pyproject.toml`: Es installiert das Paket editable mit allen
Laufzeit-Extras (`llm`, `export`, `agentic`). Die Paket- und
Versionsstrategie wird dadurch an einer Stelle gepflegt.

Die Pipeline lädt beim ersten LLM-Schritt automatisch die Datei `.env` aus dem
Repository-Root. Bereits gesetzte echte Umgebungsvariablen haben Vorrang vor
Werten aus `.env`.

Ohne weitere Angabe nutzt die Pipeline die Demo-Arbeitsmappe
`examples/Tarifrechner_KLV.xlsm`. Eine andere Excel-Quelldatei kann mit
`--excel` angegeben werden:

```powershell
python pipeline.py --excel examples/Tarifrechner_KLV.xlsm
python agentic_pipeline.py --excel examples/Tarifrechner_KLV.xlsm
```

Relative `--excel`-Pfade werden gegen das Repository-Root aufgelöst. Absolute
Pfade sind ebenfalls möglich.

Das Exportmanifest `info_from_excel/export_manifest.json` enthält neben den
Exportpfaden auch strukturierte Warnungen, Prompt-Metadaten mit SHA-256-Hashes
und Output-Hashes. Mit `--strict_manifest_warnings` werden Warnungen als Fehler
behandelt, die Kontext verlieren oder Reproduzierbarkeit beeinträchtigen:
fehlender VBA-Zugriff, fehlgeschlagene VBA-Modul-Lesung, fehlgeschlagene
CSV-Kompression, fehlende Wertquellen oder fehlgeschlagene
Scalar/Table-Extraktion sowie Prompt-Trunkierung durch Datei- oder
Gesamtlimits.

Vor der Ausführung generierter Tests führt die Pipeline zusätzlich eine
statische Sicherheitsprüfung für generierten Python-Code aus. Sie blockiert
gefährliche Imports, Dateisystem- und Netzwerkzugriffe, Subprocess-Aufrufe
sowie `eval`/`exec`; das Ergebnis steht in
`generated/static_security_report.json`.

Nach jedem klassischen Lauf und nach jedem agentischen Abschluss schreibt die
Pipeline ein Review-/Run-Dossier nach `generated/run_dossier.json`. Es bündelt
Manifest-Zusammenfassung, Prompt- und Output-Hashes, erzeugte Dateien,
Testsummary, Manifest-Warnungen und abgeleitete offene Annahmen für die
menschliche Kontrolle.

> **Hinweis zur Plattform:** Die Extraktion läuft standardmäßig
> plattformneutral ohne Microsoft Excel (Backend `openpyxl`: Zellformeln +
> gecachte Werte und Defined Names via openpyxl, VBA-Quellcode via
> `oletools.olevba`). Damit ist die Pipeline auf Windows, macOS und Linux
> lauffähig. Das frühere COM-Backend bleibt als `--export-backend com`
> erhalten (nur Windows + installiertes Excel; einmalige Einstellung dort:
> **Datei → Optionen → Trust Center → Makroeinstellungen → „Zugriff auf das
> VBA-Projektobjektmodell vertrauen"**).
>
> Der Excel-freie Pfad liest die von Excel zuletzt **gespeicherten** (gecachten)
> Zellwerte statt live neu zu rechnen — für statische, berechnet gespeicherte
> Arbeitsmappen äquivalent und reproduzierbarer.

> **Hinweis zu den Beispieldaten:** Demo-Artefakte liegen unter `examples/`. `Tarifrechner_KLV.xlsm` und `Tarifrechner_Pipeline.pptx` sind synthetische Lehrbeispiele ohne realen Kundenbezug.

## Vision

Dieses Repository ist ein technischer und methodischer Arbeitsraum für die Frage, wie **KI und perspektivisch Agentensysteme die Rechenkernentwicklung sinnvoll unterstützen können**.

Im Zentrum steht nicht die Entwicklung eines unmittelbar einsetzbaren Standardtools, sondern der Aufbau eines **nachvollziehbaren, aktuarisch geführten Vorgehensmodells**. Wir wollen verstehen, wie sich fachliche Anforderungen, technische Umsetzung, Qualitätssicherung und menschliche Kontrolle in einem KI-gestützten Entwicklungsprozess sinnvoll zusammendenken lassen.

Dabei leiten uns insbesondere folgende Grundideen:

- **Methodik vor Produkt**: Ziel ist ein belastbares Vorgehen mit klaren Leitplanken, nicht ein universelles Toolversprechen.
- **End-to-End statt Einzelautomation**: Der Mehrwert entsteht im Zusammenspiel von Analyse, Kontextaufbereitung, Generierung, Review, Test, Dokumentation und Iteration.
- **Aktuarinnen und Aktuare in zentraler Rolle**: Fachliche Steuerung, Bewertung und Freigabe bleiben menschliche Kernaufgaben.
- **Whitebox-Prinzip**: Nachvollziehbarkeit, Prüfbarkeit, Reproduzierbarkeit und kontrollierte Verbesserung sind für diesen Kontext essenziell.
- **Pragmatischer Proof of Concept**: Wir wollen konkret zeigen, was heute bereits belastbar funktioniert, wo Grenzen liegen und welche Leitplanken notwendig sind.

Die langfristige Perspektive ist ein **methodischer Referenzrahmen für KI-gestützte Rechenkernentwicklung**: ein Ansatz, der technische Experimente, fachliche Verantwortung und Governance zusammenführt und damit Orientierung für weitere Anwendungen geben kann.

## Was ist unser MVP?

Unser aktuelles **Minimum Viable Product (MVP)** ist ein **End-to-End-funktionierender Proof of Concept**, mit dem sich ein KI-gestützter Entwicklungsablauf für Rechenlogik praktisch erproben und bewerten lässt.

Das MVP umfasst insbesondere:

- eine **durchgängige Pipeline** zur strukturierten Extraktion relevanter Artefakte,
- die **gezielte Aufbereitung von Kontext** für LLM-basierte Verarbeitung,
- die **Generierung von Code und Tests** in kontrollierten Schritten,
- einfache **Qualitäts- und Vergleichsmechanismen** zur Validierung der Ergebnisse,
- einen ersten **agentischen Orchestrierungsansatz** für wiederholbare Abläufe,
- sowie ein technisches Gerüst, an dem Fragen zu Rollen, Prüfpunkten, Fehlerschleifen und Governance konkret untersucht werden können.

Der Zweck des MVP ist damit:

1. die **Machbarkeit** eines durchgängigen KI-gestützten Ablaufs zu zeigen,
2. **Stärken und Grenzen** heutiger Modelle sichtbar zu machen,
3. Anforderungen an **Leitplanken, Qualitätssicherung und Human Oversight** herauszuarbeiten,
4. und eine belastbare Grundlage für die weitere methodische Arbeit zu schaffen.

## Weitere Entwicklungssprünge

Mögliche Entwicklungssprünge über das heutige MVP hinaus sind:

### 1. Robustere End-to-End-Pipeline
- bessere Zerlegung komplexer fachlicher Logik in verarbeitbare Arbeitspakete,
- stabilere Wiederholbarkeit der Ergebnisse,
- systematischeres Retry-, Debug- und Review-Verhalten.

### 2. Ausbau der Qualitätssicherung
- stärkere Testabdeckung,
- strukturierte Golden-Master-Vergleiche,
- automatische Konsistenzprüfungen zwischen Artefakten, generiertem Code und Testergebnissen.

### 3. Explainability und Governance
- sauberer Artefaktbezug,
- bessere Dokumentation der Herleitung,
- klar definierte menschliche Freigabepunkte,
- nachvollziehbare Protokollierung von Entscheidungen und Iterationen.

### 4. Agentische Zusammenarbeit spezialisierter Komponenten
- Trennung von Rollen wie Extraktion, Analyse, Code-Generierung, Test-Generierung, Review und Fehlerdiagnostik,
- explizite Orchestrierung dieser Rollen in einer kontrollierten Pipeline.

### 5. Erweiterung des Anwendungsbereichs
- Übertragbarkeit auf weitere fachliche Kontexte,
- perspektivisch Verknüpfung mit angrenzenden Fragestellungen wie ETL, Mapping, Verifikation und Dokumentation,
- Nutzung als methodischer Referenzrahmen für weitere KI-Use-Cases im Aktuariat.

---

# TarifRechner Pipeline

Dieses Projekt orchestriert eine zweistufige Pipeline:

1. Excel-Artefakte deterministisch exportieren und aufbereiten.
2. LLM-basierte Code- und Testgenerierung aus diesen Artefakten.

Die generierten Ordner `generated/` und `info_from_excel/` sind Laufzeit-Outputs und werden nicht manuell gepflegt.

## Projektstruktur

```
src/rechner_pipeline/
├── extract/        # Phase 1: deterministische Excel-Extraktion
│   ├── excel.py            (Sheets, VBA, Name Manager, Formel-Kompression)
│   └── scalar_table.py     (*_scalar.json und *_table_values.csv)
├── context/        # Phase 2: Prompt-Aufbereitung
│   └── prompt_builder.py   (Stuffing, Truncation, Placeholder)
├── generate/       # Phase 3: LLM-Aufruf + Output-Extraktion
│   ├── client.py           (OpenAI-Client, OPENAI_API_KEY-Validierung)
│   └── output.py           (===FILE_START===…===FILE_END===-Blöcke)
├── qa/             # Phase 4: Qualitätssicherung und Security-Gates
│   └── security.py         (statische Prüfung generierter Python-Dateien)
├── orchestrate/    # Phase 5: Orchestrierung
│   ├── dossier.py          (Review-/Run-Dossier für Human Control)
│   ├── runner.py           (PipelineRunner mit öffentlicher Stage-API)
│   └── agentic.py          (LangGraph-Wrapper, Quality-Gates, Human-Review)
├── models/
│   └── manifest.py         (ExportManifest)
└── cli.py                  (main(), agentic_main())
```

Top-Level liegen weiterhin (rückwärtskompatibel):

- `pipeline.py` — Wrapper, ruft `rechner_pipeline.cli.main` auf.
- `agentic_pipeline.py` — Wrapper, ruft `rechner_pipeline.cli.agentic_main` auf.
- `matrix_extractor.py` — deprecated; lädt Re-Exports lazy aus den kanonischen
  Modulen. Der Import der Fassade bleibt plattformneutral; der tatsächliche
  Excel-Export über `export_excel_infos` benötigt weiterhin die
  Exportabhängigkeiten (`pandas`, Windows + `pywin32` + Excel).

Über `pip install -e .` werden zusätzlich die Console-Scripts `rechner-pipeline` und `rechner-pipeline-agentic` registriert.

## Installation und Abhängigkeiten

Die zentrale Abhängigkeitsdefinition liegt in `pyproject.toml`.
Die Extras verwenden sinnvolle Mindestversionen und grenzen ungetestete
Major-Upgrades aus. Die Basisinstallation bleibt absichtlich schlank:

```powershell
pip install -e .
```

Damit sind Paketimporte, CLI-Hilfe und reine Hilfsfunktionen ohne OpenAI,
Pandas, pywin32 oder LangGraph nutzbar. Für ausführbare Pipeline-Läufe werden
Extras kombiniert:

```powershell
pip install -e ".[llm]"                    # OpenAI Responses API
pip install -e ".[anthropic]"              # Anthropic Messages API (Claude)
pip install -e ".[export]"                 # Excel-frei: openpyxl + oletools + pandas (pywin32 nur auf Windows)
pip install -e ".[llm,export]"             # klassische Pipeline
pip install -e ".[llm,export,agentic]"     # klassische und agentische Pipeline
pip install -e ".[all]"                    # alle Laufzeit-Extras
pip install -e ".[all,dev]"                # Laufzeit plus Tests
```

### LLM-Provider wählen (OpenAI, Ollama oder Anthropic)

Standardprovider ist OpenAI-kompatibel und nutzt standardmäßig
das Modell `gpt-5.2`. Über `--provider anthropic` läuft die
LLM-Generierung stattdessen gegen die Anthropic-Messages-API (Claude). Der
Modellname wird je Provider sinnvoll vorbelegt (`openai` → `gpt-5.2`,
`anthropic` → `claude-sonnet-4-6`) und ist über `--model` überschreibbar.
`--reasoning_effort` steuert bei Anthropic das Extended-Thinking-Budget
(`low` = aus, `medium`/`high` = wachsendes Budget).

Für lokale Ollama-Läufe kann `.env.example` nach `.env` kopiert und der
kommentierte Ollama-Block aktiviert werden. `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`
routet den OpenAI-Provider auf die lokale Ollama-API; `OLLAMA_NUM_CTX=65536`
setzt den nativen Ollama-Kontext auf 65K Tokens. Ohne explizites
`OPENAI_BASE_URL` wird keine lokale Ollama-Route gesetzt.

Lokaler Testlauf mit einem installierten Ollama-Modell:

```bash
OLLAMA_MODEL="dein-lokales-modell"  # Beispiel: batiai/qwen3.6-27b:q4
ollama pull "$OLLAMA_MODEL"
ollama serve
```

In einem zweiten Terminal im Repository:

```bash
. .venv/bin/activate
cp .env.example .env
# In .env den Ollama-Block aktivieren.
OLLAMA_MODEL="dein-lokales-modell"
python agentic_pipeline.py --provider openai --model "$OLLAMA_MODEL" --test-mode fixed --max_retries_main 2 --reasoning_effort low
```

Der Lauf nutzt dann das explizit angegebene Ollama-Modell und den in `.env`
gesetzten 65K-Kontext. Ein vollständiger agentischer Lauf mit lokalem Modell
kann je nach Hardware, Modell und Retry-Anzahl deutlich länger als eine Stunde
dauern.

Beispiel für den lokalen Qwen-Lauf, der in dieser Arbeitsumgebung verwendet
wurde:

```bash
ollama pull batiai/qwen3.6-27b:q4
ollama serve
```

In `.env`:

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_NUM_CTX=65536
```

Start im Repository:

```bash
. .venv/bin/activate
python agentic_pipeline.py \
  --provider openai \
  --model batiai/qwen3.6-27b:q4 \
  --test-mode fixed \
  --max_retries_main 2 \
  --reasoning_effort low
```

Falls das Modell lokal unter einem anderen Ollama-Tag installiert ist, muss nur
der Wert hinter `--model` angepasst werden; die Pipeline selbst bleibt
provider- und modellagnostisch.

```bash
pip install -e ".[anthropic]"
# ANTHROPIC_API_KEY als echte Umgebungsvariable oder in .env (Repo-Root) setzen
python pipeline.py --provider anthropic
python pipeline.py --provider anthropic --model claude-opus-4-8 --reasoning_effort high
```

Der `.env`-Loader behandelt `ANTHROPIC_API_KEY` genauso wie `OPENAI_API_KEY`:
echte Umgebungsvariablen haben Vorrang vor `.env`-Werten.

### Secrets über Pointer-Datei (empfohlen)

Damit der API-Key nicht in `.env` oder einer persistenten Host-Variable
liegt, unterstützt der Loader die `*_FILE`-Konvention: Der Key wird in eine
restriktiv berechtigte Datei außerhalb des Repos gelegt, und `.env` enthält
nur den **Pointer** darauf. Der Key wird zur Laufzeit direkt an den
SDK-Konstruktor übergeben und landet nicht in `os.environ`.

```bash
# Secret-Datei mit eingeschränktem Zugriff anlegen
install -m 600 /dev/null ~/.secrets/anthropic_api_key
printf '%s' 'sk-ant-...' > ~/.secrets/anthropic_api_key

# .env enthält nur den Pointer, kein Geheimnis:
#   ANTHROPIC_API_KEY_FILE=/home/<user>/.secrets/anthropic_api_key
```

Auflösungsreihenfolge je Key: (1) echte Umgebungsvariable `<KEY>`,
(2) `<KEY>_FILE` → Inhalt der Pointer-Datei. Gilt für `OPENAI_API_KEY` und
`ANTHROPIC_API_KEY` gleichermaßen.

`pywin32` ist mit einem Windows-Plattformmarker versehen. Auf anderen
Plattformen lassen sich Basisinstallation, CLI-Hilfe und Tests für reine
Hilfsfunktionen ausführen; der tatsächliche Excel-COM-Export benötigt weiterhin
Windows, Microsoft Excel und das Extra `export`.

## Lauf (Beispiel)

```powershell
python pipeline.py --help
python pipeline.py
python pipeline.py --excel examples/Tarifrechner_KLV.xlsm
python agentic_pipeline.py --help
python agentic_pipeline.py --max_retries_main 1 --max_retries_test 1
```

## Agentic Orchestrierung (LangGraph)

- `agentic_pipeline.py`
  - Graph-basierte Orchestrierung fuer denselben Kernablauf (`prepare -> main_llm -> test_llm -> compare`).
  - Enthaelt Quality-Gates mit begrenzten Repair-Schritten, strukturierten Diagnoseartefakten und Human-Review-Handoff.
  - Schreibt agentische Fehlerdiagnosen nach `generated/agentic_diagnostics.json` und Repair-Kontexte nach `generated/agentic_repair_context_*.json`.
  - Schreibt wie der klassische Lauf ein Review-/Run-Dossier nach `generated/run_dossier.json`.
  - Verwendet weiterhin die bestehende Business-Logik aus `PipelineRunner`.

Hinweis:
- Fuer den agentischen Einstieg wird das Extra `agentic` benoetigt.

## Workflow-Log (`RP_WFLOG`)

Standardmaessig laeuft die Pipeline technisch/still. Mit der Umgebungsvariable
`RP_WFLOG=1` schaltet man einen **menschen-lesbaren Workflow-Log** ein, der den
tatsaechlichen Verlauf je agentischer Iteration zeigt — ausschliesslich aus den
echten Lauf-Artefakten, nichts ist fest verdrahtet:

- **Auslesen:** ausgelesene Tabellenblaetter und VBA-Module.
- **Erzeugen:** Groesse des an das Modell gesendeten Prompts (und ob er einen
  Korrektur-Kontext enthaelt), die erzeugten Dateien mit Zeilenzahl, sowie in
  der ersten Iteration ein echter Code-Auszug der Rechenlogik aus
  `actuarial.py` (inkl. der vom Modell dokumentierten Excel-Korrespondenz, z. B.
  `Excel K5 / VBA-Name B_xt`).
- **Validieren:** die tatsaechlichen Abweichungen gegen den Golden-Master und —
  bei bestandenem Lauf — die skalaren Excel-Sollwerte aus `*_scalar.json`.

```bash
RP_WFLOG=1 python agentic_pipeline.py --provider anthropic --test-mode fixed --max_retries_main 2
```

Damit das Repo-Root sauber bleibt, schreibt jeder Lauf alle Artefakte in ein
eigenes, mit **Zeitstempel** versehenes Verzeichnis `runs/<zeitstempel>/`
(gitignored) — aufeinanderfolgende Laeufe (z. B. echt vs. Replay) ueberschreiben
sich also nicht. Der Log wird dort **mitgeschrieben**, sodass sich ein Lauf ohne
erneuten (kostenpflichtigen) API-Aufruf wieder ansehen laesst:

```bash
ls runs/
cat runs/<zeitstempel>/workflow_log.txt
```

Im Lauf-Verzeichnis liegen daneben die vollstaendigen Prompts jeder Iteration
(`prompt_iteration_<n>.txt`, erster Prompt vs. Korrektur-Prompt) sowie — bei
echten Laeufen — das automatisch wegsicherte Replay-Set unter `fixtures/`
(siehe „Eigene Replay-Sets" in `demo_fixtures/README.md`). Mit `RP_WFLOG_FILE`
laesst sich ein fester Pfad fuer die Mitschrift erzwingen, mit `RP_RUN_DIR` die
Basis der Lauf-Verzeichnisse. Der Umfang aufgelisteter Namen ist ueber
`RP_WFLOG_MAX_ITEMS` begrenzbar (Default 12; ueberzaehlige als `(+N)`).

## Kostenfreie Vorfuehrung (`--provider replay`)

Mit dem Replay-Provider laesst sich der **echte** Pipeline-Workflow inkl.
agentischer Korrekturschleife **kostenfrei und wiederholbar** vorfuehren — ohne
API-Aufruf. Statt das Modell zu rufen, gibt der Provider vorbereitete
Modell-Ausgaben aus einem Verzeichnis (`RP_REPLAY_DIR`) in Reihenfolge zurueck.
Die mitgelieferten Fixtures unter `demo_fixtures/` lassen gezielt Skalare im
Vertrag weg, sodass echte Abweichungen entstehen, die die Schleife real
korrigiert (2 -> 1 -> 0):

```bash
RP_WFLOG=1 RP_REPLAY_DIR=demo_fixtures \
  python agentic_pipeline.py --provider replay --test-mode fixed --max_retries_main 2
```

Details zu den Fixtures: `demo_fixtures/README.md`.

## Wichtige Hinweise

- Voraussetzungen für den Export:
  - **Default (`openpyxl`):** plattformneutral, kein Excel — nur die Pakete
    aus dem `export`-Extra (`openpyxl`, `oletools`, `pandas`).
  - **Legacy (`--export-backend com`):** Windows + installiertes Microsoft
    Excel; einmalige Excel-Einstellung: Datei -> Optionen -> Trust Center ->
    Makroeinstellungen -> „Zugriff auf das VBA-Projektobjektmodell vertrauen“.
  - Python-Pakete laut `pyproject.toml`, für den Schnellstart installiert über `pip install -r requirements.txt`
- Für LLM-Schritte muss je nach Provider `OPENAI_API_KEY` bzw.
  `ANTHROPIC_API_KEY` gesetzt sein — als echte Umgebungsvariable, in der
  automatisch geladenen Datei `.env` im Repo-Root, oder via `*_FILE`-Pointer
  auf eine Secret-Datei (siehe „Secrets über Pointer-Datei").
- Die generierten Verzeichnisse `generated/` und `info_from_excel/` werden bei jedem Lauf neu erzeugt und sind nicht zu pflegen.

## Strukturelles Refactor (parallel)

In einem separaten Branch (`refactor/structure`) wird ein strukturelles Refactor des Repositories vorbereitet (Paketierung, Modulgrenzen entlang der Pipeline-Phasen, Trennung öffentlicher und interner API). Der Stand auf `main` ist bewusst der **lauffähige Demonstrator**. Hinweise zum Refactor-Branch sind willkommen — gerne als Issue oder Kommentar.

## Vorschlag für das Vorgehen

Für die weitere Arbeit an diesem Repository bietet sich ein bewusst zweigleisiges Vorgehen an:

### 1. Technische Weiterentwicklung des Proof of Concept
Das bestehende Repository wird schrittweise so weiterentwickelt, dass der End-to-End-Ablauf robuster, besser testbar und methodisch aussagekräftiger wird. Ziel ist ein sauberer Demonstrator mit klaren Prüfpunkten und reproduzierbaren Ergebnissen.

### 2. Methodische Verdichtung der Erkenntnisse
Parallel zur technischen Arbeit werden die gewonnenen Erfahrungen systematisch verdichtet:
- Welche Aufgaben eignen sich heute bereits gut für KI-Unterstützung?
- Wo liegen die Grenzen aktueller Modelle?
- Welche Rollen übernehmen Aktuarinnen und Aktuare sinnvoll in einem KI-gestützten Entwicklungsprozess?
- Welche Governance-, Freigabe- und Dokumentationsanforderungen sind notwendig?

### 3. Iterative Validierung an konkreten Teilproblemen
Anstatt früh einen universellen Zielzustand anzunehmen, sollten einzelne Arbeitsschritte gezielt verbessert und immer wieder an konkreten fachlichen Fällen überprüft werden. So entsteht ein belastbares methodisches Bild aus realen Iterationen.

### 4. Enge Verzahnung von Technik und Fachlichkeit
Die technische Entwicklung sollte laufend mit fachlicher Bewertung gekoppelt bleiben. Relevante Kriterien sind dabei insbesondere:
- fachliche Korrektheit,
- Reproduzierbarkeit,
- Nachvollziehbarkeit,
- Testbarkeit,
- Wartbarkeit,
- und die klare Verteilung von Verantwortung zwischen Mensch und KI.

## Nächste Schritte

### Kurzfristig
- Vision und Zielbild im Team abstimmen.
- Scope des MVP explizit festhalten.
- Qualitätskriterien für „funktioniert“ vs. „fachlich belastbar“ definieren.
- Bestehende Pipeline an den wichtigsten Schwachstellen stabilisieren.
- Rollenbild für Human-in-the-Loop, Review und Freigabe konkretisieren.

### Mittelfristig
- Agentische Zerlegung einzelner Arbeitsschritte weiter ausarbeiten.
- Test- und Vergleichslogik ausbauen.
- Explainability-Elemente und Artefaktbezug verbessern.
- Übertragbarkeit auf weitere fachliche Beispiele prüfen.
- Schnittstellen zu angrenzenden Themen wie ETL und Verifikation konkretisieren.

### Perspektivisch
- Methodik und Leitplanken dokumentieren.
- Ergebnisse in der Fachcommunity diskutieren.
- Prüfen, welche Bausteine sich später standardisieren oder offen bereitstellen lassen.

## Roadmap für die nächsten 24 Monate

### Phase 1: Konsolidierung des Proof of Concept (0–6 Monate)
- gemeinsames Zielbild schärfen,
- MVP klar abgrenzen,
- Repository bereinigen und stabilisieren,
- wichtigste End-to-End-Strecke reproduzierbar machen,
- erste methodische Lessons Learned dokumentieren.

### Phase 2: Ausbau von QS, Rollen und Orchestrierung (6–12 Monate)
- Test-Gates und Vergleichsmechanismen ausbauen,
- explizite Review- und Freigabeschritte definieren,
- agentische Rollenbilder konkretisieren,
- Fehler- und Eskalationslogik verbessern,
- erste belastbare Aussagen zu Grenzen und Erfolgsfaktoren formulieren.

### Phase 3: Übertragbarkeit und methodische Verdichtung (12–18 Monate)
- weitere fachliche Beispiele heranziehen,
- Übertragbarkeit auf andere Kontexte prüfen,
- Brücke zu angrenzenden Use Cases wie ETL-Verifikation schlagen,
- methodische Leitplanken konsolidieren,
- Governance- und Explainability-Aspekte systematisieren.

### Phase 4: Konsolidiertes Rahmenwerk und Ausblick (18–24 Monate)
- einen konsistenten methodischen Rahmen für KI-gestützte Rechenkernentwicklung formulieren,
- Bausteine für Dokumentation, Review und QS standardisieren,
- offene Punkte für weitergehende Forschung oder Tooling identifizieren,
- bewerten, welche Teile künftig in Richtung wiederverwendbarer Referenzbausteine weiterentwickelt werden können.

## Einordnung der Roadmap

Die Roadmap ist bewusst **methodisch** und nicht als klassischer Produktentwicklungsplan formuliert. Sie soll helfen,
- technische Experimente zu fokussieren,
- Ergebnisse fachlich einzuordnen,
- und aus einem funktionierenden Proof of Concept schrittweise ein belastbares Vorgehensmodell zu entwickeln.

Eine spätere Produktisierung einzelner Bausteine ist denkbar, steht derzeit aber nicht im Mittelpunkt. Vorrang hat die Entwicklung eines klaren methodischen Rahmens, der technische Machbarkeit, fachliche Verantwortung und kontrollierten KI-Einsatz zusammenführt.

## Mitwirken

Issues, Diskussionsanstöße und Pull Requests sind willkommen. Details siehe [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).
