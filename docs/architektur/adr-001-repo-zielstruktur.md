# ADR-001: Repo-Zielstruktur entlang der Migrations-Pipeline

Status: akzeptiert (Maintainer, 2026-08-14). Umgesetzt in zwei Commits
(src-Schnitt, runs/-Konsolidierung) vor dem Push des Branches
`feat/bestandsdaten-modul`.

> **Teilweise abgeloest durch [ADR-006](adr-006-portierung-ausser-betrieb.md)**
> (2026-08-17): `gates/orchestrate/`, `models/kern_output.py` und die
> `assurance`-Kette gibt es nicht mehr. Der Schichtenschnitt selbst gilt
> unveraendert; verbindlich ist heute `SCHICHT_ERLAUBT` in
> `ontologie/code_karte.py` (ADR-005).

## Kontext

Das Repo wird zur Plattform fuer KI-gestuetzte Bestandsmigrationen
ausgebaut (drei Stufen: Quellen-Analyse, Rechenkern-Implementierung,
Test/Abnahme; eine Ontologie als einziges Interface zwischen den
Stufen — Entwurf folgt in diesem Verzeichnis). Die gewachsene Struktur
passte nicht dazu: vier gitignorierte Laufverzeichnisse auf Top-Level
plus ein teilgetracktes output/, und ein src-Schnitt entlang der
Historie (extract/, adapters/, orchestrate/, toolbox/ mit 15 flachen
CLIs) statt entlang der Aufgabe. Vor dem Push lernt das Team die
Struktur genau einmal — deshalb jetzt.

## Entscheidung

Der src-Schnitt folgt den Pipeline-Stufen; Laufartefakte liegen in
EINEM Verzeichnis.

| Neu | Inhalt | Vorher |
|---|---|---|
| `quellen/` | Vorverarbeitungsschicht (Stufe 1): ein deterministischer, LLM-freier Vorverdichter je Quelltyp. `quellen/extract` + `quellen/adapters` (Excel), `quellen/tarifplan_staging` (DOCX); Bestands-Profiling folgt | `extract/`, `adapters/`, `toolbox/tarifplan_staging` |
| `gates/` | alle Pruef-CLIs und die Abnahme-Kette (Stufe 3): P-Q1–G8, `bestand_validate` (P-B1), `orchestrate/` (Ketten-Runner, Dossier), `_common` (Ledger/Exit-Contract) | `toolbox/`, `orchestrate/` |
| `bestand/` | unveraendert, plus eigene Producer-CLIs `cli_report`, `cli_fortschreibung` | `toolbox/bestand_*` |
| `kern/`, `qa/` | unveraendert (stabiler Rechenkern; deterministische Pruef-Logik) | — |
| `models/` | geteilte, paketuebergreifende Datenvertraege (Bundle, Manifest, Gate-Schemata, Bestand-Schema, `kern_output` = Sechs-Datei-Contract) | `models/`, `generate/output.py` |
| `ontologie/` | T-Box/A-Box der Migrations-Pipeline (Platzhalter, Entwurf folgt) | — |
| `spez/` | Tarif-Spezifikationen: typisierte Parametrierung des Zustandsmodell-Rueckgrats (Platzhalter, Entwurf folgt) | — |
| `runs/` | EIN gitignoriertes Laufverzeichnis: `runs/info_from_excel`, `runs/generated`, `runs/diagnostics`, `runs/migrationsstaging`, `runs/berichte` | `info_from_excel/`, `generated/`, `diagnostics/`, `migrationsstaging/`, `output/` |
| `docs/architektur/` | Architektur-Dokumente und ADRs (team-sichtbar) | verstreut/privat |

Kommando-Aufrufe aendern sich entsprechend:
`python -m rechner_pipeline.gates.<gate>`,
`python -m rechner_pipeline.quellen.tarifplan_staging`,
`python -m rechner_pipeline.bestand.cli_report`. Der Einstieg
`rechner-pipeline assurance` bleibt unveraendert.

## Konsequenzen

- Einmalige Einarbeitung: der Push traegt die Zielstruktur; niemand
  lernt eine Struktur, die zwei Tage spaeter faellt.
- Alle Referenzen (src, tests, README, AGENTS.md, Skills) sind
  nachgezogen; die Skill-Namen bleiben unveraendert (Working
  Agreement: `.claude/skills/` wird nicht umbenannt). Suite: 557
  Tests unveraendert gruen.
- Explizite `--*-dir`-Argumente verhalten sich unveraendert; nur die
  Fallback-Defaults zeigen auf `runs/`.
- `ontologie/` und `spez/` sind bewusst leere, dokumentierte
  Platzhalter — Inhalt kommt mit dem Architektur-Entwurf, nicht auf
  Vorrat.
- Die weitere Struktur unterhalb von `runs/` (lauffallweise
  Unterverzeichnisse, Schutz echter Laeufe vor Aufraeum-Aktionen)
  wird im Pipeline-Entwurf festgelegt.

## Verworfene Alternative

Anbau eines weiteren Pakets (`migration/`) neben die bestehende
Struktur: haette den Wildwuchs um einen sechsten Laufordner und ein
Parallel-Universum vergroessert, und das Team haette sich nach dem
Entwurf ein zweites Mal einarbeiten muessen.
