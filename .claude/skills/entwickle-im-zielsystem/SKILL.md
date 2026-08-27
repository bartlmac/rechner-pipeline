---
name: entwickle-im-zielsystem
description: >-
  Develop code in this repository under its non-negotiable architecture: layer map
  (quellen/ontologie/spez/gates/kern/bestand), Knoten annotation, determinism and
  SDK-freedom, fail-fast idioms, test-before-commit, kernel acceptance protocol.
  Trigger for ANY implementation work in src/ or tests/ — new features, fixes,
  refactorings, extensions — whether asked directly or as part of a larger task.
  Skip for: running migration cases (migrationsfall-durchfuehren), generating the
  six-file comparison kernel (build-vergleichsrechenkern), authoring gates
  (author-rechner-toolbox-gate), pure reading/analysis.
---

# Entwickeln im Zielsystem

## Rolle

Du bist Entwickler in einer Codebasis, die auf ~1 Mio. LOC waechst und
aufsichtsnah abgenommen wird. Die Architektur ist NICHT verhandelbar:
was ihr widerspricht, wird nicht "pragmatisch" eingebaut, sondern als
Architekturfrage gestoppt und vorgelegt.

## Schichtenkarte — wo Code hingehoert (ADR-001, ADR-005)

Verbindlich ist die nachrechenbare Fassung: `SCHICHT_ERLAUBT` in
`ontologie/code_karte.py`, geprueft durch
`python -m rechner_pipeline.ontologie.code_karte`. Diese Tabelle
ist ihre Lesefassung und muss mit ihr uebereinstimmen.

| Schicht | Traegt | Tabu |
|---|---|---|
| `kern/` | stabiler Rechenkern: Zustandsmodell-Rueckgrat + Produkte als Parametrierung | Formelaenderungen ohne Abnahme-Protokoll; Produktlogik ausserhalb `produkte/` |
| `ontologie/` | T-Box/A-Box, Aussagen/Provenienz/Diskrepanz, Merge, Coverage, Code-Index | Fachformeln; Quellformat-Wissen |
| `spez/` | Tarif-Spez (Parametrierung des Rueckgrats), Validierung, Generatoren | freie DSL-Erweiterungen; Kern-Imports ausser lesender Introspektion |
| `quellen/` | deterministische Vorverdichter + Import-Werkzeuge je Quelltyp | LLM-Aufrufe; Interpretation (die gehoert in Skills) |
| `gates/` | Pruef-CLIs mit Ledger-Contract (ein JSON auf stdout, Exit-Codes, `.gate.json`) | Fachlogik, die nicht pruefend ist; Prosa statt Befund |
| `bestand/` | synthetische Bestaende, Fortschreibung, Bericht | Kern-Umgehungen (Betraege kommen aus dem Kern) |
| `models/` | paketuebergreifende Datenvertraege | Verhaltenslogik |
| `qa/` | deterministische Vergleichs-Engines (Golden Master, Ueberleitung, Diff) | LLM-Pfade |
| `kommutationskern/` | separater Zweitkern (Kommutation, klassische Barwerte) NUR fuer den Kreuz-Check | jeder Konsument ausser `qa/` — der Zielkern rechnet ohne Kommutation (ADR-004) |
| `fall.py` | Fall-Arbeitsbereich (Eingang unantastbar, ADR-002) | Aufraeumlogik fuer `eingang/` oder `entscheide/` |
| `cli.py` | Kommandozeilen-Einstieg (assurance-Kette, Fall-Flags) | Fach- oder Pruflogik |

Neuer Code, der in keine Schicht passt, ist ein Architekturbefund —
STOPP, Vorschlag formulieren, Mensch entscheidet.

## Nicht verhandelbare Regeln

1. **Deterministisch und SDK-frei:** kein OpenAI/Anthropic/LangGraph,
   kein Netz, kein Subprozess (ausser bestehender Muster), keine
   dynamische Ausfuehrung in `src/`. Gleiche Eingaben => gleiche
   Ausgaben; Serialisierung sortiert; `Date.now`-artige Abhaengigkeiten
   werden injiziert, nie im Kernpfad gezogen.
2. **Fail-fast statt stiller Zustaende:** kein stiller Overwrite, kein
   stilles Verwerfen, kein "Default, wenn unklar". Unklarheit ist ein
   benannter Zustand (nicht_belegt/mehrdeutig/widerspruechlich) oder
   ein harter Fehler mit sprechender Meldung, die den Ausweg nennt.
3. **Constraints als Code:** Validierung im Idiom
   `validate(...) -> List[str]` (leer = ok) bzw. Pydantic-Validatoren
   in der Ontologie-/Spez-Schicht (ADR-003 zieht die Grenze). Prosa
   validiert nichts.
4. **Knoten-Annotation (D4, ADR-005):** fachtragende Module UND
   Testmodule deklarieren `Knoten: <id>` im Modul-Docstring
   (hierarchisch: `familie[/generation]`; Code bindet an die groebste
   Ebene, die er fachlich traegt, Tests so fein wie ihr Gegenstand);
   `python -m rechner_pipeline.ontologie.code_index --tests tests`
   muss drift-frei bleiben, `python -m
   rechner_pipeline.ontologie.code_karte` befundfrei (Schicht-
   Allowlist — eine neue Kante zwischen Schichten ist eine
   Architektur-Entscheidung). Impact einer Aenderung: `git diff
   --name-only | python -m rechner_pipeline.ontologie.impact`
   (informativ; committet wird nach VOLLER Suite). Fundstellen sind
   ableitbar, nicht suchbar: erst Index, dann exakte Symbolsuche,
   Volltext ist Fallback.
5. **Kern-Abnahme-Protokoll** (kern/__init__): die
   Charakterisierungs-Referenzwerte sind unantastbar; ihre Aenderung nur mit fachlicher
   Begruendung im selben Commit; `__version__` bei fachlicher Aenderung
   anheben; tafeln.xml nur ueber den Import-Weg mit Provenienz.
6. **Don't ship without tests:** vor JEDEM Commit volle Suite
   (`.venv/bin/python -m pytest`), neue Logik mit Tests, die die
   naheliegende Mutation fangen (siehe Skill `teste-adversarial`).
   Kontrollrechnungen gegen einen unabhaengigen Pfad schlagen
   Selbstbestaetigung (f(x)==f(x) ist kein Test).
7. **Dependencies:** exakt gepinnt, Aufnahme nur per ADR; `.venv`-pip
   ja, System-pip nein.
8. **Konventionen:** deutsche Domaenensprache im Migrations-/
   Bestandscode, Provenienz-Namen des Quellsystems bleiben erhalten
   (Bxt, kVx_MRV); keine Emojis/Icons; Commits deutsch, begruendend
   (WARUM vor WAS), Schluss "Generated with Claude Code"; Push macht
   der Mensch.
9. **AGENTS.md und `.claude/skills/`-Namen** sind team-geteilte
   Vertraege (Team): Inhalte nachziehen ja, umbenennen/schwaechen
   nein; `.claude`/`.agents`-Paritaet ist test-tragend.

## Arbeitsweise

1. Einordnen: welche Schicht, welcher Knoten, welche bestehenden Muster
   (Nachbarmodule LESEN, bevor du schreibst — Signaturen/Kontrakte
   zuerst, Quelltext nur bei Bedarf).
2. Klein schneiden: ein Block = eine fachliche Aussage = ein Commit.
   Kein unaufgeforderter Refactor ausserhalb des Scopes; drei aehnliche
   Zeilen schlagen eine verfruehte Abstraktion.
3. Bauen mit Tests, Suite gruen, committen.
4. Groessere Bloecke vor dem Abschluss adversarial reviewen lassen
   (Skill `teste-adversarial`); bestaetigte Findings fixen und als
   Regressionstests festschreiben.
5. Doku-Pflichten pruefen (Skill `dokumentiere-system`): ADR bei
   Architektur-Entscheidungen, README/AGENTS bei neuen Kommandos,
   Docstrings als Fachbegruendung (WARUM, nicht Nacherzaehlung).

## STOPP-Kriterien (Mensch fragen)

- Eine Regel oben muesste gebrochen werden, um die Aufgabe zu erfuellen.
- Ein bestehender Referenzwert (Charakterisierungstest, Gate P-K1 eines Falls) wird rot und die
  Ursache ist nicht ein offensichtlicher eigener Fehler.
- Ein Schichten-/Zustaendigkeitsschnitt muesste sich aendern.
- Eine neue Dependency, ein neues Top-Level-Verzeichnis, eine Aenderung
  an geteilten Vertraegen (AGENTS.md, Gate-Contracts, T-Box).
