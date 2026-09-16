# Tarifpläne

Fachdokumente des **Beispiel-Rechenkerns** (`rechner_pipeline.kern`) —
Teil des Illustrationsobjekts, der fiktiven Pfefferminzia LV, nicht der
System-Dokumentation (die liegt unter `docs/architektur/`).

Je Produkt ein Tarifplan mit der **Ausgestaltung**: Zustandsraum des
Tarifs, Leistungen, Beiträge, Reservebegriffe, GeVo-Katalog,
Stellschrauben, Gültigkeitsgrenzen, Bestandsgenerationen — und bei
migrierten Produkten die Parameter der Korrekturmathematik
(Grundsatzdokumentation Abschnitt 10 Nr. 9). Das **gemeinsame Rückgrat** aller Produkte
(Zustandsmodell, Thiele-Rekursion, Rechnungsgrundlagen-Schicht,
Numerik) steht einmal in der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md) und
wird hier nicht wiederholt; ein Wächter hält den Schnitt
(`tests/test_tarifplan_struktur.py`).

- [KLV — Kapitallebensversicherung](klv.md)
- [BU — Berufsunfähigkeit](bu.md)

Die Generationentabellen in Paragraf 13 sind **erzeugt, nicht
abgetippt** (P7): `python -m rechner_pipeline.bestand.tarifplan_tabellen
--config configs/bestand_gesamt.toml --produkt klv --einsetzen
docs/tarifplaene/klv.md` ersetzt den markierten Block aus der
Bestand-Config — Generationen mit Rechnungsgrundlagen und Vertrieb, die
Tarifzellen übernommener Generationen und was sich von Generation zu
Generation ändert. Ein Test hält den Block gegen den Generator; je
Generation hält der Kern einen Charakterisierungs-Referenzwert
(`tests/fixtures/kern_referenzwerte/referenz_plv_*.json`), damit eine
Parametrierung nicht still driftet.

Die PDFs sind Sekundärartefakte, gerendert über die gepinnte
Doku-Engine (`docs/engine/render.sh`, ohne Argument alle Tarifpläne;
die Grundsatzdokumentation rendert `docs/engine/render.sh
docs/mathematik/grundsatzdokumentation.md`); maßgeblich sind die
Markdown-Fassungen.
