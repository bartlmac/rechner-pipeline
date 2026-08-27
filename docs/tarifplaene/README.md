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

Die PDFs sind Sekundärartefakte, gerendert über die gepinnte
Doku-Engine (`docs/engine/render.sh`, ohne Argument alle Tarifpläne;
die Grundsatzdokumentation rendert `docs/engine/render.sh
docs/mathematik/grundsatzdokumentation.md`); maßgeblich sind die
Markdown-Fassungen.
