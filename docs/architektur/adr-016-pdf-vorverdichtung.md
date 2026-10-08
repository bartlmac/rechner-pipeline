# ADR-016: Vorverdichtung liest Text-PDF (pypdf); OCR bleibt draußen

**Status:** angenommen am 2026-09-01 (Maintainer). Anlass war der
Trockenlauf der zweiten Baldrian-Lieferung.

## Kontext

Die Meldungs-Vorverdichtung (`quellen.tarifplan_staging`) las bis heute
ausschließlich DOCX. Real liefern Quellsysteme aber überwiegend PDF —
teils mit Textlayer, teils als Scan. Die zweite Baldrian-Lieferung
enthält die Mitteilung 143 als PDF (Doku-Engine-Artefakt); der
maschinelle Trockenlauf vor dem Merge blieb an genau dieser Stelle
stehen. Ohne PDF-Weg ist Stufe 1 der Tarifhälfte für reale
Lieferungen nicht durchführbar.

## Entscheidung

1. `tarifplan_staging` bedient DOCX und PDF, nach Dateiendung
   unterschieden, mit identischer JSON-Ausgabestruktur (`--input`;
   `--docx` bleibt als Altname). Die Vorverdichtung bleibt der eine
   deterministische Weg zum LLM-Input (P10 unverändert).
2. PDF heißt Text-PDF: extrahiert wird der Textlayer, zeilenerhaltend
   (der Formelsatz alter Meldungen trägt Bedeutung im Zeilenlayout),
   je Absatz die Seite als Fundstelle. Ein PDF ohne Textlayer (Scan)
   ist ein harter Fehler mit benanntem Ausweg — OCR ist bewusst nicht
   Teil der Stufe: es ist nicht deterministisch genug für einen
   Vorverdichter und extern beschaffbar (Backlog, falls es je in die
   Pipeline soll).
3. Dependency: `pypdf==6.16.2` (exakt gepinnt). Reines Python,
   plattformneutral (Windows-Team) — dieselbe Linie wie
   openpyxl/oletools für Office-Formate. Ein stdlib-eigener
   PDF-Parser wäre ein fragiles Kunstwerk (Objektströme, Fonts,
   CMaps) und wurde verworfen; ein Systemwerkzeug (poppler/pdftotext)
   wäre ein Subprozess mit Plattformrisiko.
   Nachtrag 2026-10-03: angehoben auf `pypdf==6.19.0` (acht
   Sicherheitsmeldungen der Stufe hoch gegen 6.16.2, alle ab 6.19.0
   behoben). Gemessen vor dem Wechsel: Der Textlayer aller PDFs im
   Repository kommt byte-gleich heraus, 6.19.0 bringt keine weitere
   Abhängigkeit mit.
4. PDF kennt keine Absatzstile, Tabellen- und Formelstruktur:
   `tabellen` und `formeln` bleiben leer und der `hinweis` weist das
   aus — die Inhalte stehen als Text in den Absätzen. Die
   Fragment-Extraktion liest sie von dort; eine Strukturrekonstruktion
   aus Layoutkoordinaten ist bewusst nicht Teil dieser Stufe.

## Konsequenzen

- Lieferungen dürfen die Meldung als PDF enthalten; der Fall-Lauf 2
  (Mitteilung 143 als PDF) ist damit durchführbar.
- Scans blockieren hart statt leer durchzulaufen; der Fehlertext nennt
  die externe OCR/Textfassung als Ausweg.
- Erste neue Runtime-Dependency seit der Excel-Linie; sie ist auf die
  Quellen-Schicht beschränkt (kein Kern-Import).
