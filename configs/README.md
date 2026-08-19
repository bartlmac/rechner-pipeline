# Bestands-Konfigurationen

Konfigurationen der Bestandserzeugung und -fortschreibung
(`rechner_pipeline.bestand`) für die fiktive Pfefferminzia LV — je
Datei ein Bestand: Tarifgenerationen mit Rechnungsgrundlagen und
Ontologie-Knoten, Erfahrungsannahmen (3. Ordnung), Seeds und Volumina.

- `bestand_klv.toml` — KLV-Bestand (neun Generationen)
- `bestand_bu.toml` — BU-Bestand
- `bestand_gesamt.toml` — beide Versicherungsarten in einem Bestand

Diese Dateien sind prozess- und test-getragen: die Test-Suite lädt sie
direkt, `impact` führt sie als Daten-Bindung, und der Bestandsbericht
läuft auf ihnen (siehe `ONBOARDING.md`, Abschnitt 3). Format:
`src/rechner_pipeline/bestand/config.py`.

## `neuzugang_pro_jahr` wirkt nur mit `--neuzugang-ab`

Ein Erzeuger je Zeitfenster: Ohne `--neuzugang-ab` besiedelt der
Batch-Erzeuger das volle Verkaufsfenster jeder Generation
(`sample_size`), und `neuzugang_pro_jahr` bleibt ohne Wirkung — der Lauf
meldet dann `0 Neuzugaenge`. Das ist **kein** Run-off: Die Zugänge nach
dem Referenzstichtag stecken im Basisbestand statt im GeVo-Strom.

Mit `--neuzugang-ab <Datum>` stoppt der Batch an diesem Stichtag, und
ab da erzeugt der GeVo-Strom Neuzugang mit `neuzugang_pro_jahr` je
Kalenderjahr und Generation (Ereignis `ZUG`). Beide Modi sind
deterministisch; sie ergeben unterschiedliche Bestände, also nie beide
im selben Vergleich mischen. Zahlenbeispiel und Kommandos:
`ONBOARDING.md`, Abschnitt 3.
