# ADR-016: Vorverdichtung liest Text-PDF (pypdf); OCR bleibt draussen

Status: angenommen (Maintainer, 2026-09-01). Kontext: Trockenlauf der
zweiten Baldrian-Lieferung.

## Kontext

Die Meldungs-Vorverdichtung (`quellen.tarifplan_staging`) las bis heute
ausschliesslich DOCX. Real liefern Quellsysteme aber ueberwiegend PDF —
teils mit Textlayer, teils als Scan. Die zweite Baldrian-Lieferung
enthaelt die Mitteilung 143 als PDF (Doku-Engine-Artefakt); der
maschinelle Trockenlauf vor dem Merge blieb an genau dieser Stelle
stehen. Ohne PDF-Weg ist Stufe 1 der Tarifhaelfte fuer reale
Lieferungen nicht durchfuehrbar.

## Entscheidung

1. `tarifplan_staging` bedient DOCX und PDF, nach Dateiendung
   unterschieden, mit identischer JSON-Ausgabestruktur (`--input`;
   `--docx` bleibt als Altname). Die Vorverdichtung bleibt der eine
   deterministische Weg zum LLM-Input (P10 unveraendert).
2. PDF heisst TEXT-PDF: extrahiert wird der Textlayer, zeilenerhaltend
   (der Formelsatz alter Meldungen traegt Bedeutung im Zeilenlayout),
   je Absatz die Seite als Fundstelle. Ein PDF ohne Textlayer (Scan)
   ist ein harter Fehler mit benanntem Ausweg — OCR ist bewusst NICHT
   Teil der Stufe: es ist nicht deterministisch genug fuer einen
   Vorverdichter und extern beschaffbar (Backlog, falls es je in die
   Pipeline soll).
3. Dependency: `pypdf==6.16.2` (exakt gepinnt). Reines Python,
   plattformneutral (Windows-Team) — dieselbe Linie wie
   openpyxl/oletools fuer Office-Formate. Ein stdlib-eigener
   PDF-Parser waere ein fragiles Kunstwerk (Objektstroeme, Fonts,
   CMaps) und wurde verworfen; ein Systemwerkzeug (poppler/pdftotext)
   waere ein Subprozess mit Plattformrisiko.
4. PDF kennt keine Absatzstile, Tabellen- und Formelstruktur:
   `tabellen` und `formeln` bleiben leer und der `hinweis` weist das
   aus — die Inhalte stehen als Text in den Absaetzen. Die
   Fragment-Extraktion liest sie von dort; eine Strukturrekonstruktion
   aus Layoutkoordinaten ist bewusst nicht Teil dieser Stufe.

## Konsequenzen

- Lieferungen duerfen die Meldung als PDF enthalten; der Fall-Lauf 2
  (Mitteilung 143 als PDF) ist damit durchfuehrbar.
- Scans blockieren hart statt leer durchzulaufen; der Fehlertext nennt
  die externe OCR/Textfassung als Ausweg.
- Erste neue Runtime-Dependency seit der Excel-Linie; sie ist auf die
  Quellen-Schicht beschraenkt (kein Kern-Import).
