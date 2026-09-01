# Regie (Stub — Konzept benannt, Dokumentation ausstehend)

**Status:** Platzhalter, angelegt 2026-08-31 auf Barteks Wunsch: "ein
Zeichen setzen, dass wir das haben und dokumentieren brauchen."

## Was die Regie ist

Neben System und Simulations-Tooling gibt es eine dritte Sorte Arbeit:
die **Spielleitung der Vorfuehrung**. Sie legt fest, WAS vorgefuehrt
wird und unter welchen Bedingungen — sie ist Teil des Gesamtbilds, aber
wie die Simulation NICHT Teil des Systems. Heute gehoeren dazu:

* **Spielleiter-Bereiche** `docs-local/`, `simulation/` und `regie/`
  (alle gitignored): die Aufloesungen der Showcase-Faelle und die
  Spielleitung der Laeufe. `simulation/` erzeugt die Artefakte der
  Quelle (samt Manipulations-Doku), `regie/` traegt die
  LAUF-Spielleitung — Drehbuecher und die Auftraege der
  Operator-Sessions (uebergeben wird nur ihr INHALT als Start-Prompt;
  die Sessions lesen den Bereich nie). Operative Migrations-Sessions
  lesen keinen der drei Bereiche; die Vorzeigeseite bricht ab, wenn
  etwas davon in die Veroeffentlichung geriete.
* **Rollenbesetzung je Fall** (Modell Lauf 2, 2026-09-01):
  `programmleiter` (Orchestrator der PLV, fuehrt den Fall E2E; in
  Personalunion PLV-IT mit eigenem Schluessel fuer A-K1 und die
  Katalog-Erweiterungen), `plv-aktuar` (unabhaengige zeichnende
  Fachinstanz: A-Q1, A-M1..M4, eigener Schluessel — wer den Prozess
  faehrt, nimmt ihn nicht selbst fachlich ab), `quelle-experte`
  (Baldrian-Aktuar: Lieferungen und Auskuenfte, bewusst knapp
  gehalten, kein Schluessel), `mensch` (Eskalation nach
  Abbruchkriterien). Technisch getragen von der Zeichnungsordnung
  (`gate_entscheid --zeichnungsordnung`).
* **Abbruchkriterien**, nach denen der Mensch einsteigt: klarer
  Systemfehler (durch Agenten/Operatoren nicht heilbar),
  Zirkelreferenz, drei fruchtlose Q&A-Schleifen zum selben Thema,
  Budget ueberschritten.
* **Laufdrehbuecher**: welcher Fall wann gefahren wird, welche
  Rueckfragen die Quellseite beantwortet, was auf die Vorzeigeseite
  kommt.

Die Regie betrifft nicht nur die Migration: Auch die geplante taegliche
Fortschreibung des Bestands braucht eine Spielleitung (welche Vorfaelle
ein Tag bringt, welche Stoerungen inszeniert werden).

## Was zu dokumentieren bleibt

1. ~~README-Diagramm erweitern~~ — geschehen 2026-08-31: Komponente
   (7) "Regie — WIP" im Komponentenbild, gestrichelt wie das geplante
   Tooling, mit Verweis hierher.
2. Ein eigenes Kapitel (dieses Dokument ausbauen): Abgrenzung
   System / Simulation / Regie, die Bereiche, die Rollen, die
   Abbruchkriterien, der Umgang mit Aufloesungen.
3. Verweise aus AGENTS.md/ONBOARDING dorthin, sobald das Kapitel steht.

Siehe `dev-docs/offene-punkte.md` (Eintrag "Regie dokumentieren").
