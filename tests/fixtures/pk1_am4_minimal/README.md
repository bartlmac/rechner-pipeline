# Anonymisiertes P-K1-/A-M4-Pflicht-Fixture

`fixture.json` beschreibt den kleinsten fachlichen Fall, der den echten
Extraktions-, P-Q3-, P-K1- und A-M4-Pfad traegt. Die Quelle ist das synthetische,
eingecheckte Workbook `pk1_am4_anonymisiert.xlsm` im selben Verzeichnis; sein
voller SHA-256 ist Bestandteil des Fixtures. Die Kopie enthaelt weder
`cp:lastModifiedBy` noch `x15ac:absPath` oder externe Office-Relationships,
damit keine Personen-/Kontokennung und kein Herkunftspfad mitversioniert wird.

Die Tests materialisieren daraus jeweils einen frischen Fall unter `tmp_path`.
Damit bleiben Fall-Arbeitsbereiche unter `faelle/` weiterhin gitignoriert,
waehrend ein fehlendes oder veraendertes Pflicht-Fixture als Testfehler statt
als Skip sichtbar wird. Akteur und Fallbezeichnung sind reine Rollen- bzw.
Testnamen und enthalten keine Personen- oder Kundendaten.
