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
