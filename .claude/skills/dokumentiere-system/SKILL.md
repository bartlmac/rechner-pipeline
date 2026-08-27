---
name: dokumentiere-system
description: >-
  Write and maintain this repository's documentation under its rules: generated beats
  handwritten (P7), each document type has ONE home (ADRs and architecture in
  docs/architektur, Tarifplaene in docs/tarifplaene, team agent instructions in
  AGENTS.md, private notes in docs-local), German plain text without emojis, ADR
  format for decisions. Trigger when documentation is to be created or updated:
  ADRs, architecture docs, README sections, Tarifplaene, docstrings, commit messages
  for doc changes. Skip for: generating the Fachspez of a migration case (that is a
  generator in spez/fachspez.py), code comments as part of implementation work.
---

# System dokumentieren

## Grundsatz: Generiert schlaegt handgeschrieben (P7)

Dokumente, die Daten wiedergeben (Berichte, Fachspezifikationen,
Coverage, Indizes), werden GENERIERT — Gliederung/Texte als Daten
getrennt vom Renderer (Muster: `bestand/berichtstexte.py`,
`spez/fachspez.py`). Handgeschrieben ist nur, was Urteil traegt:
Architektur-Begruendungen, ADRs, Tarifplan-Fachtexte. Wenn du dabei
bist, denselben Inhalt an zwei Orten zu pflegen: STOPP — eine Quelle
bestimmen, die andere generieren oder verweisen (Drift ist hier schon
zweimal teuer gewesen).

## Wo was lebt (genau EIN Zuhause je Dokumenttyp)

| Dokumenttyp | Ort | Regeln |
|---|---|---|
| Architektur-Entscheidungen | `docs/architektur/adr-NNN-*.md` | ADR-Format: Kontext, Entscheidung, Konsequenzen, verworfene Alternative(n); Status + Datum + Entscheider; Index in `docs/architektur/README.md` nachziehen |
| Architektur-Beschreibung | `docs/architektur/*.md` | beschreibt IST und Absicht; "bewusst nicht"-Abschnitte sind Pflicht (Grenzen benennen, nie beschoenigen) |
| Grundsatzmathematik (alle Produkte) | `docs/mathematik/grundsatzdokumentation.md` | normative Mathematik und Numerik ALLER Produkte, inkl. Migrationszugang und Korrekturschicht (Abschnitt 9) — was fuer mehr als ein Produkt gilt, gehoert dorthin, nicht in einen Tarifplan; substanzielle Aenderungen brauchen die Zustimmung des Aktuariats |
| Tarifplaene (Zielkern) | `docs/tarifplaene/*.md` | AUSGESTALTUNG je Produkt; das gemeinsame Rueckgrat steht einmal in `docs/mathematik/grundsatzdokumentation.md` und wird nie wiederholt (Waechter: tests/test_tarifplan_struktur.py); einheitliche Gliederung ueber alle Produkte, Rendering ueber die Doku-Engine |
| Agenten-Anweisungen (Team) | `AGENTS.md` + `.claude/skills/` (+ `.agents/`-Spiegel) | CLI-neutral; AGENTS.md-Aenderungen im Team abstimmen; Skill-Paritaet ist test-tragend |
| README | `README.md` | erzaehlt das System entlang der Architektur; Kommandobeispiele muessen LAUFEN (nachpruefen, nicht abschreiben) |
| Private Notizen, Bauplaene, Erklaerungen | `docs-local/` (gitignored) | nie Klarnamen/Kontaktdaten des Kreises ins oeffentliche Repo (DSGVO) |
| Fall-Dokumente | Fall-Arbeitsbereich | generiert (Fachspez, Coverage, Ledger), nie von Hand editiert |

## Stilregeln (nicht verhandelbar)

- Deutsch, Klartext, KEINE Emojis/Icons/Status-Symbole.
- Begruendung vor Behauptung: ein Satz WARUM schlaegt drei Saetze WAS.
- Zahlen mit Herkunft: keine Kennzahl ohne Quelle (Test, Gate, Messung).
- Ehrlichkeit: Grenzen, offene Punkte und bewusste Nicht-Umsetzungen
  stehen IM Dokument, nicht nur im Kopf des Autors. Ein "bewusst nicht
  in vX"-Abschnitt gehoert in jedes Architektur-Dokument.
- Docstrings begruenden fachlich (WARUM diese Regel/Grenze existiert,
  welcher Fehler ohne sie passiert) statt Code nachzuerzaehlen; das
  Repo nutzt Docstrings als Traeger von Abnahme-Protokollen und
  Knoten-Annotationen — diese Teile nie beilaeufig umformulieren.
- Aktualisierungs-Pflicht: wer Verhalten aendert, zieht betroffene
  Dokumente IM SELBEN Block nach (README-Kommandos, AGENTS-Eintraege,
  ADR-Konsequenzen, Grundsatzmathematik). Veraltete Doku ist ein Befund.

## Arbeitsweise

1. Dokumenttyp bestimmen -> Zuhause aus der Tabelle -> existiert schon
   eines? (Duplikat vermeiden, Index pruefen.)
2. Bei Entscheidungen: ADR VOR oder MIT der Umsetzung, nicht danach
   aus der Erinnerung.
3. Kommandobeispiele und Pfade gegen das Repo verifizieren.
4. Gegenlesen auf die Stilregeln; Suite laufen lassen, wenn Doku
   test-tragend ist (AGENTS.md, Skills, README-Strukturtests).
