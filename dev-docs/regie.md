# Regie (Stub — Konzept benannt, Dokumentation ausstehend)

**Status:** Platzhalter, angelegt 2026-08-31 auf Barteks Wunsch: "ein
Zeichen setzen, dass wir das haben und dokumentieren brauchen."

## Was die Regie ist

Neben System und Simulations-Tooling gibt es eine dritte Sorte Arbeit:
die **Spielleitung der Vorfuehrung**. Sie legt fest, WAS vorgefuehrt
wird und unter welchen Bedingungen — sie ist Teil des Gesamtbilds, aber
wie die Simulation NICHT Teil des Systems. Heute gehoeren dazu:

* **Spielleiter-Bereiche** `docs-local/` und `simulation/` (gitignored):
  die Aufloesungen der Showcase-Faelle — welche Defekte eine Lieferung
  absichtlich traegt, wie die Beispieldaten entstehen. Operative
  Migrations-Sessions lesen sie nicht; die Vorzeigeseite bricht ab,
  wenn etwas davon in die Veroeffentlichung geriete.
* **Rollenbesetzung je Fall**: `quelle-experte` (bedient die
  Lieferungen, zeichnet keine Gates), `plv-va` (zeichnet A-Q1 und
  A-M1..M4, eigener menschlicher Schluessel), `mensch` (Eskalation).
  Technisch getragen von der Zeichnungsordnung
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

1. **README-Diagramm erweitern**: Das Komponentenbild (Objekte/System
   links, Simulations-Tooling rechts: (4) Bestands-Simulation,
   (5) Quellbestand-Simulation, (6) Taegliche Fortschreibung) bekommt
   eine vierte Komponente oder einen Balken UNTER dem Tooling:
   **Regie** — sie bespielt Migration UND Fortschreibung.
2. Ein eigenes Kapitel (dieses Dokument ausbauen): Abgrenzung
   System / Simulation / Regie, die Bereiche, die Rollen, die
   Abbruchkriterien, der Umgang mit Aufloesungen.
3. Verweise aus AGENTS.md/ONBOARDING dorthin, sobald das Kapitel steht.

Siehe `dev-docs/offene-punkte.md` (Eintrag "Regie dokumentieren").
