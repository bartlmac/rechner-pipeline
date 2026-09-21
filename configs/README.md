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

## Der Bestand entsteht aus dem Zugangsstrom — es gibt keinen gezogenen Anfangsbestand

Jeder Vertrag der PLV kommt als Zugang ins Journal (Ereignis `ZUG`),
mit `neuzugang_pro_jahr` je Kalenderjahr und Generation als Dichte. Zwei
Erzeuger teilen sich dieselbe Attributziehung: der Tagesbetrieb
(`betrieb.tageslauf`, Werktag für Werktag ab `betriebsbeginn`) und der
jährliche Strom der Prüfstrecke (`cli_fortschreibung --neuzugang-ab`).
Ein Lauf ohne `--portfolio`, ohne `--uebernahme` und ohne
`--neuzugang-ab` hat nichts, was er führen könnte, und sagt das.

Bis zum 2026-09-21 gab es daneben `sample_size`: einen auf einmal
gezogenen Bestand ohne eine einzige Buchung. Er war nirgends mehr als
Kulisse — gemessen: die Vorzeige holte daraus fünf Verträge, die
Prüfstrecke des Migrationsfalls 2220, und alle Gates blieben ohne sie
grün (ADR-020). Eine Config, die den Schlüssel noch trägt, wird
abgewiesen, nicht still anders gelesen.

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

`nummernkreis = k` legt den Nummernkreis einer Generation fest: Police-Nummern
`k * 10 Mio + 1 ..`, mit festen Abschnitten fuer Batch, Jahresneuzugang und
Tagesneugeschaeft; auch die Seeds der Erzeuger haengen daran. Er ist eine
Eigenschaft der Generation, nicht ihrer Position in der Datei (Review T22-09:
vorher aenderte eine umsortierte Liste die Identitaet jeder Police und damit
jede Ereignishistorie). Entweder alle Generationen tragen ihn oder keine; ohne
ihn gilt die Position wie in der Erstfassung. `bestand_gesamt.toml` traegt ihn
explizit in der bisherigen Reihenfolge, die bestehenden Bestaende sind damit
bitidentisch.
