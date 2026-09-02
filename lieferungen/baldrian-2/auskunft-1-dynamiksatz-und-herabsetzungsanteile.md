# Auskunftsschreiben Nr. 1 — Dynamiksatz und Herabsetzungsanteile Vorgeschichte

Baldrian Lebensversicherung a. G., Bestandsuebertragung KLV TG2015 an
die Pfefferminzia Lebensversicherung — Lauf 2

## Frage der PLV

1. Welchen Prozentsatz je Erhoehungstermin hat Baldrian fuer die
   planmaessige Dynamik (S' = e * S^ges) tatsaechlich angewendet —
   einheitlich oder gestaffelt 2016-2025?
2. Anteil f, um den die Versicherungssumme bei jeder der 70
   Vorgeschichts-Herabsetzungen (GEVO=RED) in
   baldrian_gevo_metadaten.csv herabgesetzt wurde, je Police
   (POLNR;DATUM).

## Antwort

**Zu 1. (Dynamiksatz):** Der Satz betrug einheitlich **5 %** der
Gesamtversicherungssumme je Erhoehungstermin, ueber den gesamten
Beobachtungszeitraum 2016-2025 unveraendert. Grundlage: Rechenwerk der
Bestandsfuehrung (Parameter der Vorfallannahmen der Fuehrung; kein
Zahlwert in den AVB, siehe dort Ziffer 3, oder im Tarifplan — die
Dynamikhoehe ist Fuehrungspraxis, keine Tarifgroesse).

**Zu 2. (Herabsetzungsanteile der Vorgeschichte):** Diese Auskunft
koennen wir in der angefragten Form NICHT liefern. Unser
Vorgeschichte-Export (baldrian_gevo_metadaten.csv) fuehrt fuer
Ereignisse vor dem Migrationsjahr grundsaetzlich nur Police, Art und
Datum — ohne Betraege oder Parameter (etabliertes Lieferformat, siehe
auch LIEFERSCHEIN). Nur im GeVo-Protokoll des Migrationsjahres selbst
traegt das PARAM-Feld bei RED den fortgefuehrten Anteil (Auskunft der
Bestandsfuehrung, bereits mitgeteilt). Fuer die 70 Herabsetzungen der
Jahre 2016-2025 ist dieser Wert daher nicht Teil der Migrationslieferung;
eine Einzelfallrecherche je Police in der Kernverwaltung ist bei
laufendem Tagesgeschaeft und der Zusatzbelastung durch die
Uebertragung nicht kurzfristig fuer alle 70 Faelle leistbar.

Als allgemeine, aus dem Rechenwerk der Fuehrung ableitbare Auskunft:
die Herabsetzungspraxis der Quelle kennt drei moegliche fortgefuehrte
Anteile — f = 0,50, 0,60 oder 0,75 — je nach Kundenwunsch bei
Antragstellung der Teilkuendigung. Welcher der drei Werte im
Einzelfall je Police galt, laesst sich aus der gelieferten
Vorgeschichte nicht ableiten.

Sollte der aktuarielle Test auf die exakten Einzelwerte zwingend
angewiesen sein: Wir bitten um eine gebuendelte, auf das
Erforderliche eingegrenzte Anfrage (z. B. eine kleinere Stichprobe
statt aller 70 Faelle), zu der wir eine manuelle Pruefung in der
Kernverwaltung einplanen koennen.

## Grundlagen

- Dynamiksatz: Rechenwerk der Bestandsfuehrung (Vorfallannahmen der
  Fuehrung); AVB Ziffer 3 (Dynamik-Schranke, kein Zahlwert).
- Herabsetzungsanteile: Lieferformat der Vorgeschichte
  (baldrian_gevo_metadaten.csv, Kopfzeile POLNR;GEVO;DATUM); Auskunft
  der Bestandsfuehrung zum PARAM-Feld des GeVo-Protokolls; Rechenwerk
  der Fuehrung (moegliche Anteile der Herabsetzungspraxis).

Datum: 2026-09-01

Baldrian Lebensversicherung a. G., Bestandsfuehrung
