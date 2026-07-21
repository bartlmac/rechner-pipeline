# Rechenkernentwicklung mit KI – Methodik, Leitplanken und Proof of Concept

> **Status:** öffentlicher Proof of Concept. Begleitender Arbeitsraum eines
> DAV-Projekts unter der AG Bestandsmigration. Vorgängerprojekt:
> [portxlpy](https://github.com/bartlmac/portxlpy).

Dieses Repository migriert einen Excel/VBA-Tarifrechner **1:1 in einen reinen
Python-Rechenkern** (sechs Dateien) und weist die funktionale Äquivalenz gegen
ein unabhängiges Golden-Master-Orakel nach. Ein **Coding-Agent** (Codex- oder
Claude-CLI) schreibt und repariert den Rechenkern; dieses Paket ist die
**deterministische, SDK-freie Abnahme-Schicht**: es extrahiert die Eingaben,
fährt eine Kette von Prüf-Gates und erzeugt ein nachvollziehbares Abnahme-Dossier.

## Vision

Dieses Repository ist ein technischer und methodischer Arbeitsraum für die Frage,
wie **KI und Agentensysteme die Rechenkernentwicklung sinnvoll unterstützen
können**. Im Zentrum steht nicht ein fertiges Standardtool, sondern ein
**nachvollziehbares, aktuarisch geführtes Vorgehensmodell** — wie fachliche
Anforderungen, technische Umsetzung, Qualitätssicherung und menschliche Kontrolle
in einem KI-gestützten Entwicklungsprozess zusammenwirken.

Leitideen:

- **Methodik vor Produkt** — ein belastbares Vorgehen mit klaren Leitplanken,
  kein universelles Toolversprechen.
- **End-to-End statt Einzelautomation** — Wert entsteht im Zusammenspiel von
  Analyse, Kontextaufbereitung, Generierung, Review, Test, Dokumentation und
  Iteration.
- **Aktuarinnen und Aktuare in zentraler Rolle** — fachliche Steuerung, Bewertung
  und Freigabe bleiben menschliche Kernaufgaben.
- **Whitebox-Prinzip** — Nachvollziehbarkeit, Prüfbarkeit, Reproduzierbarkeit und
  kontrollierte Verbesserung sind essenziell.

Die langfristige Perspektive ist ein **methodischer Referenzrahmen für
KI-gestützte Rechenkernentwicklung**, der technische Experimente, fachliche
Verantwortung und Governance zusammenführt.

## Ansatz: Agent generiert, deterministische Schicht nimmt ab

Die Verantwortung ist klar getrennt:

- **Generierung und Selbstkorrektur** besitzt ein externer Coding-Agent (Codex-
  oder Claude-CLI) über die Skill `build-vergleichsrechenkern`. Der Agent schreibt
  den Rechenkern und repariert ihn anhand der Gate-Rückmeldungen, bis er besteht.
- **Abnahme** besitzt dieses Paket — rein deterministisch. Es gibt **keine**
  Modell-, Provider-, Token- oder Reasoning-Fläche und keinen LLM-Pfad in der
  Abnahme. Die Prüfung ist damit unabhängig von der (probabilistischen)
  Generierung und selbst nachvollziehbar.

Diese Trennung ist bewusst: das probabilistische Schreiben und das deterministische
Prüfen sind zwei verschiedene Dinge, und nur die Prüfung entscheidet über die
Annahme.

## Die Gate-Kette (`assurance`)

Der Befehl `assurance` fährt die deterministische Prüf-Kette **in Reihenfolge**
über einen bereits generierten Rechenkern und endet mit einem `dossier`-Verdikt.
Er enthält selbst keine Gate-Logik, sondern ruft die einzelnen Toolbox-Gates auf
und aggregiert deren Ergebnisse:

```
extract → validate → security → conventions → golden_master → algebraic → roundtrip → dossier
```

- **extract** — deterministische Extraktion der Excel-Artefakte (Zellformeln +
  gecachte Werte + Defined Names via openpyxl, VBA via `oletools.olevba`) sowie
  der Skalar-/Tabellen-Erwartungswerte.
- **validate** — der Sechs-Datei-Contract des Rechenkerns.
- **security** — statische Prüfung des generierten Codes (blockt Netz, Subprozess,
  dynamische Ausführung, schreibende/gefährliche Aufrufe).
- **conventions** — Architektur-/Namenskonventionen des Kerns.
- **golden_master** — Vergleich der berechneten Werte gegen die aus dem Excel
  extrahierten Erwartungswerte (unabhängiges Orakel).
- **algebraic** — property-based Prüfung aktuarieller Identitäten gegen einen
  deklarativen `qa_contract.json` (Sterblichkeits-, Kommutations- und
  Barwert-Identitäten); geprüft mit Hypothesis. Übersprungen ohne `--qa-contract`.
- **roundtrip** — Roundtrip-/Konsistenzprüfungen.
- **dossier** — aggregiert die Gate-Ergebnisse zum Abnahme-Verdikt.

Jedes Gate schreibt sein Ergebnis als einzelnes JSON auf stdout und eine
`<command>.gate.json`-Ledger-Datei in den gemeinsamen `--diagnostics-dir`.
`extract` und `validate` sind Voraussetzungen; schlägt eine fehl, werden die
QA-Gates übersprungen, `dossier` läuft aber weiter und protokolliert ein ehrliches
blockiertes Verdikt. `security`..`roundtrip` laufen **continue-on-fail**, damit
ein Lauf das vollständige Bild liefert. Ein Nicht-Null-Exit ist **blockierend**
und wird nie zu einer Warnung abgeschwächt.

## Schnellstart

Voraussetzung: **Python 3.11 oder neuer**. Kein LLM-Key nötig — die Abnahme ist
SDK-frei.

```bash
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline

python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Voller Abnahme-Lauf über einen bereits generierten Rechenkern:

```bash
rechner-pipeline assurance --repo-root . --input examples/Tarifrechner_KLV.xlsm \
    --generated-dir <gen> --info-dir <info> --diagnostics-dir <diag> \
    [--qa-contract qa_contract.json] [--adapter auto|excel] \
    [--export-backend openpyxl|com] [--strict-manifest-warnings]
```

Quell-neutrale Optionen: `--input <pfad>` (Excel heute, Adapter-Naht für weitere
Quellen; `--excel` bleibt als kompatibler Alias). `--adapter auto|excel`.
`--export-backend openpyxl|com` — `openpyxl` ist der plattformneutrale Default
(Windows/macOS/Linux, ohne Microsoft Excel); `com` benötigt Windows + Excel.
`--strict-manifest-warnings` behandelt `strict_error`-Manifest-Warnungen als
blockierend.

Jedes Gate ist auch einzeln lauffähig:

```bash
python -m rechner_pipeline.toolbox.<command> [flags]
```

## Sicherheit und Reproduzierbarkeit

- **Statisches Gate** (`security`) prüft den generierten Code vor jeder
  Ausführung.
- **Laufzeit-Confinement** (`qa/fs_confine.py`): der Golden-Master-/Roundtrip-Lauf
  führt den generierten Code in einem Subprozess aus, in dem Schreiben, Lesen
  außerhalb des Repos, Netz (`socket`), Subprozesse (`subprocess`, `os.system`)
  und schreibende `os`-Primitive hart abgewiesen werden.
- **Unabhängiges Orakel**: die Erwartungswerte stammen deterministisch aus dem
  Excel, nicht vom Modell; der Vergleichs-Harness ist reviewter Code.
- **Gepinnte Abhängigkeiten** (openpyxl/oletools/pandas, exakt) für
  reproduzierbare Läufe.

## Agenten-Anbindung

Claude-CLI wird über `.claude/skills/` unterstützt, Codex-CLI über die
`AGENTS.md` im Repo-Root plus gespiegelte Skills unter `.agents/skills/`. Die
Codex-Kopien werden auf Parität mit den Claude-Skill-Bodies getestet, damit ein
Workflow nicht still vom anderen abweicht. Die portable Basis ist: lokale Dateien
plus einfache Python-Kommandos — kein MCP/RPC-Pfad.

## Beispieldaten

Demo-Artefakte liegen unter `examples/` (`Tarifrechner_KLV.xlsm`,
`Tarifrechner_FLV_v1.xlsm` u. a.). Es sind **synthetische Lehrbeispiele** ohne
realen Kundenbezug.

## Mitwirken

Beiträge laufen über GitHub-Collaborators auf Vertrauensbasis; siehe
`CONTRIBUTING.md` und `AGENTS.md`. **Arbeitsweise am gemeinsamen Branch:** klonen
und lokal arbeiten, **kein direkter Push** in den gemeinsamen Branch — Änderungen
werden nach Absprache übernommen.

## Lizenz

MIT — siehe `LICENSE`.
