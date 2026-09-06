# Bestands-Konfigurationen

Konfigurationen der Bestandserzeugung und -fortschreibung
(`rechner_pipeline.bestand`) für die fiktive Pfefferminzia LV — je
Datei ein Bestand: Tarifgenerationen mit Rechnungsgrundlagen und
Ontologie-Knoten, Erfahrungsannahmen (3. Ordnung), Seeds und Volumina.

- `bestand_klv.toml` — KLV-Bestand (neun Generationen; Lehrbeispiel)
- `bestand_bu.toml` — BU-Bestand (Lehrbeispiel)
- `bestand_gesamt.toml` — beide Versicherungsarten in einem Bestand:
  die operative Config der PLV mit den Generationen bis heute (KLV-2025,
  BU-2025 im Vertrieb) und dem Abschnitt `[tagesbetrieb]`

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

## `[tagesbetrieb]`: die PLV als laufendes Unternehmen

Fachkonzept `docs/simulation/tagesbetrieb.md`. Der Abschnitt trägt den
`betriebsbeginn` (ab diesem Tag verkauft der Tagesbetrieb Werktag für
Werktag; der Batch besiedelt die Verkaufsfenster nur bis dahin), die
`wochentagsgewichte` der Neugeschäftsverteilung (Wochenende 0, Montag
1,3, sonst 1,0) und den `meldeverzug_tod` (lognormal, Median und
95-Prozent-Quantil in Tagen). Je verkaufender Generation gibt
`neuzugang_trend` den Jahresfaktor des Ziels an:
`neuzugang_pro_jahr * (1 + neuzugang_trend)^(J - gueltig_von.year)`.
Verkaufsfenster verkaufender Generationen desselben Produkts dürfen
nicht überlappen — ein Tag verkauft je Produkt genau eine Generation;
die Config prüft das. Die Werte für 2025 sind **vorläufig** (offene
Fachentscheidungen des Konzepts, Abschnitt 10) und in der Config als
solche markiert.
