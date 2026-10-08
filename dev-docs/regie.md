# Regie (Stub — Konzept benannt, Dokumentation ausstehend)

**Status:** Platzhalter, angelegt 2026-08-31 auf Wunsch des Maintainers: „ein
Zeichen setzen, dass wir das haben und dokumentieren brauchen.“

## Was die Regie ist

Neben System und Simulations-Tooling gibt es eine dritte Sorte Arbeit:
die **Spielleitung der Vorführung**. Sie legt fest, WAS vorgeführt
wird und unter welchen Bedingungen — sie ist Teil des Gesamtbilds, aber
wie die Simulation NICHT Teil des Systems. Heute gehören dazu:

* **Spielleiter-Bereiche** `docs-local/`, `simulation/` und `regie/`
  (alle gitignored): die Auflösungen der Showcase-Fälle und die
  Spielleitung der Läufe. `simulation/` erzeugt die Artefakte der
  Quelle (samt Manipulations-Doku), `regie/` trägt die
  LAUF-Spielleitung — Drehbücher und die Aufträge der
  Operator-Sessions (übergeben wird nur ihr INHALT als Start-Prompt;
  die Sessions lesen den Bereich nie; der Betriebsleitfaden des
  Spielleiters — Aufsetzen, Benennen, Modelle, Disziplin während des
  Laufs, Nacharbeit — liegt als README im Bereich selbst). Operative
  Migrations-Sessions lesen keinen der drei Bereiche; die Vorzeigeseite bricht ab, wenn
  etwas davon in die Veröffentlichung geriete.
* **Rollenbesetzung je Fall:** seit ADR-018 die Rollen der
  Zeichnungsordnung (`mensch/vorstand`, `mensch/aktuariat`,
  `mensch/architektur`, `mensch/rechenkern`, `mensch/betrieb`; in der
  Vorführung simuliert und unter Mandat) und die fünf Agentenrollen unter
  `.claude/agents/`. Die Besetzung von Lauf 2 (2026-09-01: Programmleiter,
  PLV-Aktuar, Quellexperte, Mensch) ist damit abgelöst.
* **Abbruchkriterien**, nach denen der Mensch einsteigt: klarer
  Systemfehler (durch Agenten/Operatoren nicht heilbar),
  Zirkelreferenz, drei fruchtlose Q&A-Schleifen zum selben Thema,
  Budget überschritten.
* **Laufdrehbücher**: welcher Fall wann gefahren wird, welche
  Rückfragen die Quellseite beantwortet, was auf die Vorzeigeseite
  kommt.

Die Regie betrifft nicht nur die Migration: Auch die geplante tägliche
Fortschreibung des Bestands braucht eine Spielleitung (welche Vorfälle
ein Tag bringt, welche Störungen inszeniert werden).

## Was zu dokumentieren bleibt

1. Ein eigenes Kapitel (dieses Dokument ausbauen): Abgrenzung
   System / Simulation / Regie, die Bereiche, die Rollen, die
   Abbruchkriterien, der Umgang mit Auflösungen. Das frühere
   Komponentenbild des README mit der Regie als Komponente 7 ist mit
   ADR-027 entfallen.
2. Verweise aus AGENTS.md/ONBOARDING dorthin, sobald das Kapitel steht.

Siehe `dev-docs/offene-punkte.md` (Eintrag „Regie dokumentieren“).

**Abgrenzung zur Dokumentation (2026-09-08):** `docs/simulation/` ist keine
Regie, sondern das versionierte Fachkonzept (Tagesbetrieb, Erfahrungsannahmen,
Entstehung der Bestände). Die Veröffentlichungssperre der Vorzeigeseite
(`werkzeuge/vorzeigeseite._pruefe_regie`) nimmt genau diesen Elternteil `docs/`
aus — nur das Paar `docs/simulation`; jedes andere `simulation/`, `docs-local/` oder `regie/` im Pfad sperrt.
