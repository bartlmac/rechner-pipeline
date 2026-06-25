# CR-005 — Modellwahl und Eskalations-Strategie (Sonnet-Default, Opus-Eskalation)

- **Status:** Vorschlag (Entscheidung offen)
- **Datum:** 2026-05-29
- **Branch-Kontext:** `feat/anthropic-provider`
- **Betroffen:** `cli.py`, `orchestrate/runner.py` (PipelineOptions),
  `orchestrate/agentic.py` (Repair-Knoten)
- **Abgrenzung:** *nicht* die Provider-Erweiterung (OpenRouter/LM Studio, eigenes
  Issue) — hier geht es um die **Wahl des Claude-Modells und wann hochstufen**.

## 1. Problem

Die Korrektheit der LLM-Generierung schwankt deutlich von Lauf zu Lauf
(beobachtet bei identischem Prompt: 566/566, 616/617, dann 150 Abweichungen).
Ein stärkeres Modell (Opus 4.8) dürfte die Verlässlichkeit erhöhen — besonders
bei echten Rechenfehlern, weniger bei Flüchtigkeits-Auslassungen —, ist aber
spürbar teurer und langsamer als Sonnet 4.6. Fix „immer Opus" wäre teuer; fix
„immer Sonnet" lässt Verlässlichkeit liegen.

## 2. Vorschlag: kostenbewusste Eskalation

Sonnet 4.6 als **Default** (günstig). **Hochstufen auf Opus 4.8 nur dann**, wenn
der agentische Repair-Loop mit dem Default-Modell nicht innerhalb von `N`
Iterationen gegen das feste Golden-Master-Orakel konvergiert. Starkes Modell
also nur, wenn nötig.

Skizze:

- Neue Optionen: `--escalation-model claude-opus-4-8` (Default leer = keine
  Eskalation) und `--escalate-after N` (Anzahl erfolgloser Default-Repairs, ab
  der hochgestuft wird).
- Im agentischen Graph: erreicht `repair_main` die Schwelle `N`, wird für die
  nächste `main_llm`-Generierung das Eskalations-Modell verwendet (das aktuelle
  Modell wird im Agentic-State mitgeführt statt fix aus `options`).
- Klassischer (nicht-agentischer) Lauf bleibt single-shot mit `--model`.

## 3. Mess-Protokoll (Evidenz statt Bauchgefühl)

Vor einer Default-Empfehlung empirisch vergleichen — die objektive Metrik liefert
der feste Harness (Abweichungszahl):

- Je Modell (Sonnet 4.6, Opus 4.8) **M Läufe** (z. B. 5) der agentischen
  Pipeline (`--test-mode fixed`) gegen `examples/Tarifrechner_KLV.xlsm`.
- Pro Lauf erfassen: Abweichungen im ersten Wurf, Repair-Iterationen bis grün
  (oder „nicht konvergiert"), Anzahl LLM-Calls, grobe Kosten.
- Auswertung: Konvergenzrate, mittlere Iterationen, Kosten je „grünem" Lauf.
  Daraus Eskalations-Schwelle `N` und Default ableiten.

**Hinweis Kosten:** Die Messkampagne selbst kostet (Anthropic-API). Vorab ein
Budget/Obergrenze festlegen (z. B. „max. 2 × 5 Läufe").

## 4. Offene Fragen

1. Eskalieren nur die **Repair**-Generierung oder auch den Erstwurf bei
   „bekannt schweren" Excels?
2. Schwelle `N` (z. B. nach 1 erfolglosem Sonnet-Repair auf Opus)?
3. Interaktion mit `--max_retries_main` (Opus konvergiert evtl. in weniger
   Iterationen).
4. Übertragbarkeit auf OpenAI-Modelle (gpt-Tiers) bzw. später weitere Provider.
5. Soll die Eskalation pro Lauf protokolliert werden (Dossier), damit
   nachvollziehbar bleibt, welcher Schritt mit welchem Modell lief
   (Whitebox/Governance)?

## 5. Empfehlung

Erst das **Mess-Protokoll** (Abschnitt 3) fahren — kleine, budgetierte Kampagne —,
dann auf Basis der Zahlen über Default und Eskalations-Schwelle entscheiden und
die Eskalation (Abschnitt 2) implementieren. So bleibt die Modellwahl im Geist
des Golden-Master-Ansatzes datengetrieben.
