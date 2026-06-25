# dev/ — interne Entwicklungs-Dokumentation

Arbeitsraum für **Change Requests (CR)**, Design-Notizen und Entscheidungs-
vorlagen. **Kein** Teil der Laufzeit-/Pipeline-Logik — reine Doku.

## Konventionen

- Change Requests: `CR-<NNN>-<kurz-slug>.md` (fortlaufend nummeriert).
- Jeder CR hat oben einen Status: `Vorschlag` → `In Abstimmung` → `Angenommen` /
  `Abgelehnt` / `Zurückgestellt`.
- Entscheidungen, die geteilte Settings/Module berühren (z. B. `pyproject.toml`,
  `qa/security.py`), werden mit dem Kreis (insb. Alexander) abgestimmt, bevor
  sie `Angenommen` werden.

## Sessions

- [SESSION-2026-05-29](SESSION-2026-05-29.md) — Multiplattform (Excel-frei),
  Anthropic-Provider, festes Golden-Master-Orakel, agentische Konvergenz.

## Index

- [CR-001](CR-001-llm-provider-subscription-auth.md) — LLM-Calls über
  Claude-Subscription-Auth (Agent SDK) statt gemeterter API zur Kostensenkung.
- [CR-002](CR-002-fixed-golden-master-harness.md) — fester, reviewter
  Golden-Master-Harness statt LLM-generiertem Test (löst Security-Idiom-Varianz,
  Orakel-Unabhängigkeit und halbiert die Kosten pro Lauf). **Umgesetzt.**
- [CR-003](CR-003-ci-matrix.md) — GitHub-Actions-Matrix (Linux/macOS/Windows ×
  Python 3.11–3.13): Tests + Excel-freier Export-Smoke, macht „cross-platform"
  automatisch verifizierbar.
- [CR-004](CR-004-containerized-run.md) — containerisierter Run (kanonische
  Linux-Laufzeit) für den Excel-freien Pfad; Sicherheits-Synergie
  (Compare-Stufe `--network none`). COM bleibt nativer Windows-Pfad.
- [CR-005](CR-005-model-escalation.md) — Modellwahl + Eskalations-Strategie
  (Sonnet-Default, Opus-Eskalation bei Nicht-Konvergenz) mit Mess-Protokoll.
