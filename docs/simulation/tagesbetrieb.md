# Fachkonzept: Die PLV als laufendes Unternehmen — täglicher Bestandsbetrieb

**Status:** Konzept, beschlossen vom Maintainer am 2026-09-05; Umsetzung in
Blöcken (Abschnitt 9). **Ebene:** Vorzeige (das Bestandsführungssystem der
fiktiven Pfefferminzia Lebensversicherung, PLV) und Vorzeige-Werkzeuge
(Simulation, Laufzeitumgebung). Das KI-Tool selbst wird nicht verändert;
Abschnitt 8 skizziert nur, wie seine Laufzeitumgebung aussehen könnte.

## 1 Ziel

Bis heute ist der PLV-Bestand ein Lauf: Er wird bis zu einem Horizont
simuliert, geprüft, abgeschlossen und vorgeführt. Ein Versicherer lebt
aber. Er verkauft jeden Werktag Neugeschäft, bucht jeden Tag
Geschäftsvorfälle, schließt jeden Monat ab und weiß jederzeit, wie sein
Bestand gestern Abend aussah. Genau das soll die PLV künftig tun:

- Der Bestand steht jeden Morgen auf dem Stand von gestern. Ein
  nächtlicher Lauf um 23:00 Uhr simuliert den heutigen Tag, schreibt die
  Verträge mit heutigem Vertragstag fort und schließt am Kalendermonatsende
  den Monat ab.
- Neugeschäft läuft ununterbrochen bis heute, in Mengen, die das
  Unternehmen langsam schrumpfen lassen: kein Verkauf am Wochenende,
  etwas mehr am Montag, sonst gleichmäßig, mit geringeren Schwankungen
  als die übrigen Geschäftsvorfälle.
- Alle KLV-Generationen seit der ersten bis heute stehen in Tarifplan,
  Rechenkern und Simulation, mit allen Geschäftsvorfällen; die BU ebenso.
- Die Baldrian-Übernahme zum 01.01.2026 ist als abgeschlossene Migration
  Teil der laufenden Kennzahlen: Der übernommene Bestand wird seit dem
  Stichtag im selben Strom fortgeschrieben wie das eigene Geschäft.
- Das Ganze läuft nicht auf einem Entwicklerrechner, sondern in einer
  Laufzeitumgebung unter `~/apps/plv` aus einem Container-Image, das aus
  diesem Repository gebaut wird. Die Vorzeigeseite liest aus dieser
  Umgebung.

Was sich dadurch zeigen lässt, ist mehr als ein Migrationsfall: ein
Bestandsführungssystem, dessen Zahlen jeden Tag nachrechenbar aus einem
deterministischen Modell und einem Rechenkern entstehen, und in das eine
Migration als datierter Zugang eintritt.

## 2 Leitgedanke: der Tag ist eine Sicht, kein zweites Modell

Die bestehende Ereignis-Engine (`bestand.ereignisse.fortschreiben`) ist
eine reine Funktion von Basisbestand, Config, Horizont und Seed: Sie
simuliert jeden Vertrag Vertragsjahr für Vertragsjahr und erzeugt einen
Strom datierter Geschäftsvorfälle. Wer sie mit Horizont "heute" aufruft,
erhält deterministisch denselben Verlauf wie gestern, um die Vorfälle des
heutigen Tages verlängert.

Deshalb baut der Tagesbetrieb **keine zweite, tagesgranulare Engine**.
Der Stand von heute ist die deterministische Fortschreibung bis heute;
das Tagesjournal ist die Differenz zweier Stände. Alles, was Beträge
bestimmt, bleibt beim Rechenkern und bei der bestehenden Engine — der
Tagesbetrieb entscheidet nur, **welche Buchungen an welchem Kalendertag
sichtbar werden** und **wie viel Neugeschäft ein Tag bringt**.

Das hält drei Invarianten des Systems unangetastet:

1. Determinismus: Gleicher Seed, gleiche Config, gleicher Kalendertag —
   gleicher Stand, byteidentisch (Laufmanifest).
2. Beträge aus dem Kern: Das Simulationswerkzeug rechnet nichts
   Aktuarielles selbst (docs/simulation/README.md).
3. Die Gate-Verträge bleiben: Der Ledger bleibt das Wirkungsjournal, das
   P-B1 prüft; der Tag kommt als eigene, zusätzliche Tabelle hinzu.

## 3 Zeitmodell: Wirkungstag und Buchungstag

Jeder Geschäftsvorfall hat zwei Daten.

| Datum | Bedeutung | Wo es heute steht |
|---|---|---|
| **Wirkungstag** | der Vertragstag, an dem der Vorfall aktuariell wirkt: Jahrestag (Storno, Beitragsfreistellung, Erhöhung, Ablauf), Monatserster (Versicherungsbeginn) | `ledger.status_date`, `historie.status_date` — Monatserster-Konvention |
| **Buchungstag** | der Kalendertag, an dem das Unternehmen den Vorfall in die Bücher nimmt | neu: `tagesjournal.buchungsdatum` |

Der Buchungstag wird deterministisch aus dem Wirkungstag abgeleitet:

- Storno, Beitragsfreistellung, dynamische Erhöhung, Ablauf: am
  Wirkungstag, fällt dieser auf ein Wochenende, am nächsten Werktag.
- Tod: Wirkungstag plus Meldeverzug (deterministisch gezogen aus einer
  Verteilung mit Median etwa zwei Wochen, Seed aus Police und Jahr), auf
  den nächsten Werktag gerundet. Die Leistung wirkt am Wirkungstag, das
  Unternehmen erfährt es später — so sieht der Bestand von gestern
  Verträge noch als aktiv, die es aktuariell nicht mehr sind. Das ist
  kein Fehler, das ist ein Versicherer.
- Neugeschäft: Antrags- und Policierungstag ist der Buchungstag (ein
  Werktag, Abschnitt 4); der Versicherungsbeginn ist der nächste
  Monatserste nach dem Buchungstag. Die Police steht ab Buchungstag im
  Bestand als "policiert, Beginn folgt", ab Beginn als beitragspflichtig.

Das Tagesjournal ist eine neue, nur-anfügbare Tabelle
`tagesjournal.parquet`: `buchungsdatum`, `police_id`, `ereignis`,
`status_date` (Wirkungstag), `betrag`, `betrag_art`, `herkunft`
(`fortschreibung`, `neugeschaeft` oder `uebernahme`) — je Zeile ein
Verweis auf genau eine Ledger-Zeile (Police, Ereignis, Wirkungstag,
Betragsart). Die Betragsart gehört in den Schlüssel, weil ein Vorfall mehr
als eine Größe bewegt: Ein Zugang bucht die Versicherungssumme **und** den
Bruttojahresbeitrag, eine Erhöhung die Erhöhungssumme und den Beitrag der
neuen Scheibe. So wird Neugeschäft gemessen, in Summe und in Beitrag. Der
Beitrag wird aus dem Kern derselben Police hergeleitet, nicht geliefert;
P-B1 rechnet ihn nach wie jeden anderen Betrag. Wer über einen Vorfall
summiert, nennt deshalb die Betragsart — die Bewegungsrechnung führt
Versicherungssummen, nicht Beiträge —, und wer Vorfälle zählt, zählt
Vorfälle und nicht Zeilen. Noch offen und bewusst nicht in diesem Schritt:
Die Abgänge (Storno, Tod, Ablauf) und die Beitragsfreistellung führen ihre
Beitragswirkung noch nicht. Der Ledger selbst ändert sein Schema nicht;
P-B1 prüft ihn wie bisher. Ein neuer
Validator prüft die Bijektion Tagesjournal zu Ledger für alle Buchungen
mit Buchungstag bis gestern (dieselbe Klasse wie die ERH-Scheiben-Bindung
und die Betragsidentität aus T18 und T20).

Feiertage werden bewusst nicht modelliert; Wochenende genügt für die
Vorzeige. Ein Feiertagskalender wäre eine Config-Erweiterung ohne
Änderung am Modell.

## 4 Neugeschäft: stetig, wochentagsabhängig, schrumpfend

Heute erzeugt der Generator je Generation und Kalenderjahr
`neuzugang_pro_jahr` Verträge mit Beginn auf Monatsersten. Neu:

**Jahresziel mit Trend.** Je Generation ein Jahresziel und ein
Jahresfaktor, zum Beispiel `neuzugang_pro_jahr = 120` und
`neuzugang_trend = -0.04`: Das Ziel des Jahres J ist
`neuzugang_pro_jahr * (1 + trend) ** (J - gueltig_von.year)`. Damit
schrumpft das Unternehmen sichtbar, ohne dass jemand jedes Jahr eine Zahl
pflegt. Die Werte gehören in die Config, nicht in den Code.

**Verteilung auf die Tage.** Jeder Kalendertag des Jahres bekommt ein
Gewicht: Samstag und Sonntag 0, Montag 1,3, Dienstag bis Freitag 1,0.
Der Erwartungswert eines Tages ist `Jahresziel * Gewicht(Tag) / Summe der
Gewichte des Jahres`. Die tatsächliche Zahl ist der ganzzahlige Anteil
plus ein Bernoulli-Zug auf den Rest, mit Seed aus (Config-Seed,
Generation, Kalendertag). Das ist deutlich stetiger als ein Poisson-Zug
und trifft das Jahresziel im Erwartungswert exakt; die Schwankung eines
Tages ist höchstens ein Vertrag.

**Vertragsmerkmale** kommen wie bisher aus den Verteilungen der Generation
(Alter, Laufzeit, Summe, Zahlweise), gezogen mit dem Tagesseed —
reproduzierbar je Tag, unabhängig von der Reihenfolge der Läufe.

**Generationenwechsel.** Ein Tag verkauft die Generation, deren
Gültigkeitsfenster ihn enthält. Fenster überlappen nicht; die Config
prüft das bereits.

## 5 Generationen bis heute

Die Config `configs/bestand_gesamt.toml` trägt bereits KLV-1994 bis
KLV-2022 (gültig bis 2035) und BU-2000, BU-2017. Für "bis heute" fehlt:

- Eine aktuelle KLV-Generation ab 2025 mit eigenen Rechnungsgrundlagen
  (Rechnungszins, Tafel, Kosten), damit der Generationenwechsel im
  laufenden Betrieb sichtbar ist; entsprechend eine BU-Generation ab 2025.
  Die Rechnungsgrundlagen legt das Aktuariat der Vorzeige fest, nicht der
  Entwickler; das Konzept nennt sie als offene Fachentscheidung.
- Der Tarifplan (`docs/tarifplaene/klv.md`, `bu.md`) beschreibt heute das
  Tarifwerk; er bekommt je Generation eine erzeugte Tabelle der
  Rechnungsgrundlagen aus der Config (P7: erzeugt, nicht abgetippt) und
  einen Abschnitt, was sich von Generation zu Generation ändert.
- Der Rechenkern braucht keine neue Formel: Generationen sind
  Parametrierungen (ADR-004). Je Generation kommt ein
  Charakterisierungsreferenzwert hinzu (Kern-Abnahmeprotokoll), damit
  eine Parametrierung nicht still driftet.

Die Übernahme-Generation der Baldrian (KLV TG2015, in Tarifzellen) bleibt
eine eigene Generation mit `sample_size = 0`: Sie wird nicht erzeugt,
sondern kam als Zugang.

## 6 Baldrian als Zugang zum 01.01.2026

Ein Zugang liegt in der **geführten Zeit**: zwischen dem ersten Tag, den
das Unternehmen führt, und heute. Er fällt nicht mit dem Betriebsbeginn
zusammen und muss es nicht — die PLV führt seit dem 1. Juli 1994, Baldrian
tritt am 1. Januar 2026 ein, also mitten im laufenden Betrieb. Die Engine
trägt das ohnehin: Sie simuliert einen übernommenen Vertrag erst ab seinem
Bestandszugang, weil alles davor beim abgebenden Unternehmen geschah. Vor
dem ersten geführten Tag gäbe es keine Bücher, in die ein Bestand
eintreten könnte; nach heute ist nichts geschehen, was zu buchen wäre.

Der zweite Baldrian-Lauf hat den übernommenen Bestand als
`abgeleitet/bestand-nach/` hinterlassen (Stamm, Historie, Ledger mit
ZUG-/PEX-Umbuchungen zum Stichtag, Merkmale). ADR-015 legt fest, dass ein
übernommener Bestand im SELBEN Strom fortgeschrieben wird wie das eigene
Geschäft (`cli_fortschreibung --uebernahme`).

Für den Tagesbetrieb heißt das: Die Laufzeitumgebung erhält den
übernommenen Bestand einmal als Eingang (`daten/uebernahme/baldrian/`,
mit Laufmanifest und Fall-Bezug: Fallname, Stichtag, Snapshot-Hash der
A-M4-Annahme). Jeder Tageslauf fährt eigenen und übernommenen Bestand
zusammen. In den Kennzahlen erscheint die Migration als das, was sie ist:
ein Zugang von 834 Verträgen zum 01.01.2026 mit Zugangssumme und
Migrationsresiduum, danach gewöhnliche Geschäftsvorfälle. Der
Monatsbericht weist den übernommenen Teilbestand getrennt aus, solange
das Aktuariat es will (Config-Schalter).

Ein weiterer Migrationsfall käme als weiterer Eingang hinzu; der
Tagesbetrieb kennt keine Sonderbehandlung je Fall.

**Was der Zugang trägt (seit der Freischaltung des übernommenen
Bestands, 2026-09-07).** Die Übernahme schreibt den Anfangszustand, den
die Abnahmen des Falls geprüft haben: die Grundsumme im Stamm, die
Alt-Erhöhungen als Bausteine (`scheiben.parquet`), die Ursprungssumme
beitragsfrei gelieferter Verträge, die Korrekturschicht
(`schichten.parquet`) mit ihrer Verankerung, und im Beleg
`uebernahme.json` die Tarifwerks-Schalter der Generation. Die
Bestand-Config der PLV führt dieselben Schalter je Generation
(`scheiben_mit_gamma1`, `stoab_je_baustein`, `red_verfahren`); die
Führung rechnet Storno je Baustein, Scheiben mit voller Beitragsformel
und den Rückkaufswert mit Schicht, so wie es das Bedingungswerk der
Quelle zusagt. Ein Zugang ohne diese Tabellen ist ein Bestand in der
falschen Welt; der Tageslauf muss Bausteine, Schicht und Verankerung
des Eingangs in seinen Stand durchreichen (offen, Schritt 9 des
Fachkonzepts `dev-docs/freischaltung-uebernommener-bestand.md`).

### 6.1 Betriebsfunde: Entwicklerweg oder Betriebsweg

Ein Befund im laufenden Betrieb, der den übernommenen Bestand betrifft,
hat zwei mögliche Wege. Das Kriterium ist eine Frage: **Falsifiziert der
Befund ein gezeichnetes Artefakt des Falls?**

- Wenn ja — etwa weil der Bestandsbericht nach der Migration, den A-M4
  gebunden hat, falsche Beträge trägt —, dann ist es der
  **Entwicklerweg**: Das System wird korrigiert, das Artefakt im Fall neu
  erzeugt, der Korrekturvermerk in das Korrektur-Protokoll des Falls
  geschrieben, und das Gate wird neu gezeichnet (mit Vermerk, welcher
  Befund die Neuzeichnung ausgelöst hat). Der Fall bleibt die Wahrheit
  über die Migration; ein Betrieb, der etwas anderes rechnet als der
  gezeichnete Fall, ist nicht "korrigiert", sondern abgekoppelt.
- Wenn nein — der Befund liegt im Betrieb selbst (Tageslauf, Ablage,
  Kennzahlen), das gezeichnete Artefakt bleibt richtig —, dann ist es der
  **Betriebsweg**: Das System wird korrigiert, und der Betrieb wird aus
  der Übernahme neu aufgesetzt: alte Ablage archivieren, Eingang erneut
  einspielen, Stand ab Betriebsbeginn neu fahren, Stands-Paket neu
  exportieren.

Beide Wege sind Routinen mit Beleg, keine Handarbeit: Der Entwicklerweg
läuft über die Kommandos des Migrationsfalls (Skill
`migrationsfall-durchfuehren`), der Betriebsweg über die Werkzeuge der
Laufzeitumgebung (Abschnitt 8.2; "Betrieb neu aufsetzen" ist als Routine
noch zu bauen). Was nie geht: den Betrieb still weiterfahren, während
der Fall etwas anderes bezeugt.

## 7 Der Tageslauf

Ein Kommando, `python -m rechner_pipeline.betrieb.tageslauf --stand
<daten> --heute <datum>`, idempotent und deterministisch. Ohne `--heute`
gilt der Kalendertag des Aufrufs; in Tests und beim Nachholen wird er
gesetzt.

1. **Nachholen.** Liegt der letzte geführte Tag vor gestern, wird jeder
   fehlende Kalendertag in Reihenfolge nachgeholt. Ein Ausfall des
   nächtlichen Laufs kostet nichts als Rechenzeit; der Stand ist danach
   derselbe, als hätte der Lauf jede Nacht stattgefunden (Determinismus).
2. **Neugeschäft des Tages** (Abschnitt 4) in den Basisbestand.
3. **Fortschreibung bis heute**: `fortschreiben(basis, config,
   bis=heute)`, eigenen und übernommenen Bestand zusammen. Ergebnis sind
   die sechs bekannten Ausgaben plus Laufmanifest.
4. **Tagesjournal**: Differenz zum gestrigen Stand, Buchungstage nach
   Abschnitt 3; anfügen, nie überschreiben.
5. **Wache**: Gate P-B1 mit Config, Manifest und jeder Nebentabelle, die
   der Stand trägt (Merkmale, Korrekturschicht, Verankerung — aus der
   Rollentabelle des Erzeugers, nicht abgetippt), auf dem neuen Stand.
   Rot heißt: Der Stand wird nicht übernommen, der gestrige bleibt
   der geführte, der Fehler steht im Tagesprotokoll. Ein Bestandsführungs-
   system, das einen roten Stand still übernimmt, wäre die schlechteste
   Variante.
6. **Monatsabschluss** im Lauf des Ersten des Folgemonats (der erste Lauf,
   der den Monatsersten führt, schreibt ihn; beim Nachholen jeder
   übersprungene Monatserste): `cli_abschluss --stichtag <Erster des
   Folgemonats>` (Bewertung zum Monatsersten, festgeschrieben, 0444, nie
   überschrieben) und der Bestandsbericht des Monats. (Der normative Text
   sagte „am letzten Kalendertag", Umsetzung und Begründung machten den
   Ersten — Nebenhinweis des Reviews T22; der Text folgt jetzt dem Code.)
7. **Tagesprotokoll**: eine JSON-Zeile je Lauf (Datum, Neugeschäft,
   Buchungen je Art, Bestandszahlen, P-B1-Urteil, Manifest-Hash,
   Kern-Version, Image-Digest). Das Protokoll ist der Nachweis, dass das
   Unternehmen jeden Tag geführt wurde.

Der Zeitpunkt 23:00 Uhr ist eine Betriebsentscheidung: spät genug, dass
der Tag vorbei ist, früh genug, dass der Stand vor Mitternacht steht.
Die Simulation kennt keine Uhrzeit, nur den Kalendertag.

**Ablage** unter `~/apps/plv/daten/`:

| Verzeichnis | Inhalt | Schutz |
|---|---|---|
| `stand` | Symlink auf den geführten Stand `stand-<kennung>/` (sechs Ausgaben, Manifest, Merkmale) | wechselt nur durch einen grünen Lauf, atomar per Symlink-Tausch; eine Prozess-Sperre (`lauf.lock`) verhindert zwei gleichzeitige Läufe |
| `journal/tagesjournal.parquet`, `journal/protokoll.jsonl` | nur-anfügbar | 0444 je Tagesabschnitt nicht praktikabel; Schutz über Prüfsumme im Protokoll |
| `abschluesse/` | Monatsabschlüsse | 0444, genau einmal (ADR-011) |
| `berichte/` | Tages- und Monatsberichte (HTML) | erzeugt, jederzeit neu renderbar |
| `uebernahme/<fall>/` | Eingang je Migration | unantastbar wie ein Fall-Eingang |
| `configs/` | die Config der PLV, versioniert im Repo, hier als Kopie mit Hash im Protokoll | |

## 8 Laufzeitumgebung und Deployment

### 8.1 Image

Ein Dockerfile im Repo (`deploy/plv/Dockerfile`): `python:3.11-slim`,
Installation exakt wie die CI (`requirements.txt`, dann `pip install -e .
--no-deps`), kein Entwicklungswerkzeug, keine Schlüssel, ein
unprivilegierter Benutzer. Ein GitHub-Workflow `plv-image.yml` baut bei
jedem Push auf `main` das Image `ghcr.io/<owner>/rechner-pipeline-plv`
mit zwei Tags: dem Commit-Kurzhash und `latest`. Das Muster existiert
bereits für die Doku-Engine (`docs-image.yml`). Der Image-Digest steht in
jedem Tagesprotokoll — der Stand ist damit auf den Code rückführbar, aus
dem er entstand (dieselbe Provenienzdisziplin wie die Gate-Ledger).

### 8.2 Laufzeitumgebung `~/apps/plv`

```
~/apps/plv/
  compose.yml          # Image, Volumes daten/ und configs/, kein Netz
  .env                 # IMAGE_TAG, ZEITZONE; keine Geheimnisse
  daten/               # Abschnitt 7
  tageslauf.timer      # systemd --user, OnCalendar=*-*-* 23:00, Persistent=true
  tageslauf.service    # docker compose run --rm tageslauf
```

`Persistent=true` sorgt dafür, dass ein verpasster Lauf beim nächsten
Start nachgeholt wird; das Nachholen selbst leistet der Tageslauf
(Abschnitt 7, Schritt 1). Der Container braucht kein Netz. Ein Update
ist ein neuer Image-Tag in `.env` und ein `docker compose pull`; der
erste Lauf mit neuem Image protokolliert den Digest-Wechsel. Wechselt
die Kern-Version, weisen Monatsabschluss-Kontrollen die Abweichungen aus,
wie ADR-011 es verlangt — der Tagesbetrieb schreibt nichts um.

Das Repository liefert unter `deploy/plv/` Compose-Datei, Timer, Service
und eine README mit dem Einrichtungsweg; die Laufzeitumgebung selbst ist
kein Repo-Inhalt. Erstbefüllung: Basisbestand aus der Config (einmalig bis
zum Betriebsbeginn) plus Übernahme-Eingänge plus der Tagesstrom seither.

**Nummernkreise sind Pflicht, sobald eine Config einen Tagesbetrieb
führt** (Entscheid des Maintainers, 2026-09-08). Ein Kreis reserviert
seiner Generation das Band ab `k * 10 Mio + 1`; weil `k` mindestens eins
ist, kann kein Erzeuger unter oder auf zehn Millionen vergeben. Genau
dieser Bereich steht übernommenen Beständen offen, ohne mit dem
Eigengeschäft zu kollidieren. Ohne Kreise fallen die Nummern auf die
Position der Generation zurück, und dann liegt kein Band fest — die
Zusicherung wäre eine Annahme. Der Tagesbetrieb ist der Ort, an dem
fremder Bestand als Zugang eintritt, also gilt die Pflicht dort. Eine
Config der Fall-Welt darf ohne Kreise bleiben: Ihre Bytes sind eine
hashgebundene P-B1-Eingangsrolle und hängen an gezeichneten Abnahmen; eine
Lesepflicht hätte bestehende Fälle unreproduzierbar gemacht.

Der `betriebsbeginn` der Config ist die **Erzeugungsgrenze**: Bis zu ihr
stellt der Batch-Erzeuger den Bestand, danach der Tagesstrom — ein
Erzeuger je Zeitfenster. Beide beschreiben dieselbe Generation: Das
Jahresziel (`neuzugang_pro_jahr`, konstant über das Verkaufsfenster) ist
die Dichte, die auch der Batch zieht (`sample_size` über die
Fensterjahre). Wo die Grenze liegt, ändert deshalb nicht die Größe des
Bestands, sondern nur, welcher Erzeuger ihn aufgebaut hat. Die PLV setzt
sie an den Anfang ihrer Geschichte (1994-07-01): Der Batch zieht nur die
Verträge des Grenztages selbst (fünf mit Beginn am 1. Juli 1994), jeder
weitere entsteht Werktag für Werktag, und kein Bericht kennt einen
Zeitraum "vor dem Betriebsbeginn". Eine vollständige Neugenerierung ist
damit ein Neuaufsetzen (Abschnitt 8.5) und ein Lauf: rund eine
Viertelstunde, davon der größte Teil die Monatsabschlüsse seit 1994.

### 8.2a Der Betriebsbericht kennt keine Prognose

Der Bestandsbericht des Monatsabschlusses endet am **Berichtsstichtag**:
Er zeigt die geführte Geschichte des Bestands bis dahin — Zugang, Bewegung
und Abgang, wie sie gebucht wurden — und nichts darüber hinaus. Das ist
keine weggelassene Prognose, sondern eine andere Aussage: Der Betrieb
kennt die Zukunft nicht, er entdeckt sie jeden Tag neu. Eine
Prognosekurve wäre hier eine Behauptung über Tage, die noch nicht
stattgefunden haben.

Der Fallbericht behält seine Projektion. Im Migrationsfall IST der
prognostizierte Verlauf der Gegenstand: Er zeigt, wie sich der
übernommene Bestand nach der Migration entwickelt. Beide Formen sind
derselbe Renderer mit zwei verschiedenen Fragen, und sie schließen
einander aus — `berichtsstichtag` für den Betrieb, `stichtag` plus `bis`
für den Fall.

### 8.3 Vorzeigeseite aus der Laufzeitumgebung

Die Vorzeigeseite ist heute ein erzeugter Jekyll-Baum (`werkzeuge/`),
den ein Mensch veröffentlicht. Für den lebenden Bestand gibt es zwei
Wege, die sich nicht ausschließen:

- **Interne Sicht, täglich.** Der Tageslauf rendert nach
  `daten/seite/` einen Abschnitt "Bestand heute" (Kennzahlen, Neugeschäft
  der Woche, letzte Buchungen, Monatsabschlüsse) mit den bestehenden
  Renderern. Ein Caddy auf dem Betriebsrechner liefert das Verzeichnis
  read-only aus; die Sichtung läuft dort, wo der Maintainer sie ohnehin
  macht.
- **Öffentliche Sicht, gestempelt.** Die GitHub-Pages-Seite bleibt eine
  vom Menschen veröffentlichte Momentaufnahme mit Datum und Manifest-Hash
  ("Stand 2026-09-30"). Der Auftritt (`werkzeuge/auftritt.py`) liest die
  Kennzahlen dann aus einem exportierten Stands-Paket der
  Laufzeitumgebung statt aus einem Fall — eine neue Quelle für
  `falldaten`, dieselbe Drift-Regel: erzeugt, nie abgetippt.

Die Veröffentlichung nach außen bleibt menschlich (werkzeuge/README.md);
die Regie-Sperre gilt unverändert. Automatisch veröffentlicht wird
nichts, was nicht durch P-B1 ging.

### 8.4 Laufzeitumgebung für das KI-Tool (Konzept, nicht Teil dieser Umsetzung)

Das KI-Tool (Ebene 2) läuft heute in Entwicklersitzungen. Eine eigene
Laufzeitumgebung würde denselben Mustern folgen: ein zweites Image
`rechner-pipeline-agent` mit Repository, Agenten-Werkzeug und
Skill-Katalog; je Migrationsfall ein Arbeitsbereich als Volume
(Eingang und Entscheide unantastbar, ADR-002); Schlüsselmaterial nie im
Image, sondern über Dateizeiger aus einer verwalteten Ablage; jede
Sitzung beginnt mit einem Mandat und endet mit einem Verlaufsprotokoll;
die Agentenrollen des Tools legen vor, gezeichnet wird mit menschlichem
Schlüssel (Ebenen-Modell). Der Deploymentprozess wäre derselbe wie 8.1:
Image je Commit, Digest im Protokoll. Offen und Teil des
Architektur-Strangs: welche Rollen als Agentendefinitionen im Repo
liegen, wie ein Mandat als Artefakt aussieht und wo die Modelle je Rolle
protokolliert werden.

### 8.5 Betrieb neu aufsetzen (Betriebsweg)

Findet sich nach der Abnahme, dass der Betrieb den übernommenen Bestand
in einer anderen Welt führt als die Abnahmen (Abschnitt 6.1, Betriebsfund
vom 2026-09-07), wird der Fall auf dem Entwicklerweg korrigiert und der
Betrieb aus der neuen Übernahme neu aufgesetzt. Dafür gibt es eine
Routine, die nichts löscht:

```
python -m rechner_pipeline.betrieb.neuaufsetzen --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 [--config configs/bestand_gesamt.toml]
```

Sie prüft, bevor sie etwas bewegt (keine Lauf-Sperre; die Tarifwerk-
Schalter der Config stimmen mit dem Übernahmebeleg des Falls überein),
baut die neue Ablage vollständig neben der alten auf (Config, Übernahme-
Eingang mit Stamm, Journal, Ledger, Merkmalen, Bausteinen, Korrektur-
schicht, Verankerung und Übernahmebeleg, dazu `neuaufsetzen.json` als
Provenienz), archiviert die alte Ablage durch eine Umbenennung
(`daten.archiv-<Zeit>`; Journal, Protokollkette, Abschlüsse und Berichte
bleiben vollständig erhalten) und setzt die neue an ihre Stelle. Den
Stand fährt sie nicht: Der nächste Tageslauf baut ihn vom Betriebsbeginn
bis heute in einem Lauf, danach wird das Stands-Paket neu exportiert
(Abschnitt 8.3). Die Protokollkette der neuen Ablage beginnt neu; die
Provenienzdatei nennt das Archiv.

Zwei Dinge sagt die Routine offen: Zwischen den zwei Umbenennungen gibt
es einen Moment ohne Ablage (die Wurzel ist ein echtes Verzeichnis, kein
Symlink wie `stand`), darum wird der Timer vorher angehalten; startet
doch ein Tageslauf in diesem Moment, schlägt die zweite Umbenennung fehl,
und die Meldung nennt den Ausweg (alte Ablage im Archiv, neue unter
`daten.neu-<Zeit>`, von Hand an ihre Stelle setzen). Und die
Host-Kommandos (`uebernahme`, `neuaufsetzen`, `seite`) laufen aus dem
Repository-Checkout, nicht aus dem Image; der Checkout gehört auf den
Commit des Image-Tags, sonst schreibt ein anderer Code-Stand den Eingang
als der, der ihn liest.

Der Übernahme-Eingang trägt seit dieser Routine auch die Bausteine
(`scheiben.parquet`), die Korrekturschicht (`schichten.parquet`) und den
Übernahmebeleg (`uebernahme.json`); der Tageslauf reicht sie in die
Fortschreibung, die damit nach dem Tarifwerk der Generation rechnet,
dieselbe Welt wie die Führungsprobe vor A-M4.

## 9 Umsetzung in Blöcken

Jeder Block ist ein Commit mit Tests und Mutationsprobe; die volle Suite
bleibt grün. Neuer Code liegt in einem neuen Paket
`rechner_pipeline.betrieb` (Tagesbetrieb der Vorzeige) und unter
`deploy/plv/`; Änderungen an bestehenden Modulen bleiben additiv
(Config-Felder, Generator-Erweiterung). Damit ist der Strang unabhängig
vom Architektur-Strang (Rollen, Gates, Skills, Schichtenkarte) und lässt
sich ohne Konflikte mergen.

| Block | Inhalt | Aufwand |
|---|---|---|
| B1 | Config: `neuzugang_trend`, Wochentagsgewichte, Meldeverzug; Validierung; aktuelle Generationen KLV/BU ab 2025 (Rechnungsgrundlagen als offene Fachentscheidung, vorläufige Werte markiert) | 0,5 Tag |
| B2 | Neugeschäft tagesgranular: Tagesziel, Bernoulli-Rest, Tagesseed, Beginn nächster Monatserster; Test: Jahressumme, Wochenende null, Montag höher, Determinismus je Tag | 1 Tag |
| B3 | Tagesjournal: Buchungstag-Ableitung, Tabelle, Bijektions-Validator zum Ledger; Test mit Mutationsprobe (Zeile entfernt, Datum verschoben) | 1 Tag |
| B4 | `betrieb.tageslauf`: Nachholen, Fortschreibung, Wache P-B1, Monatsabschluss, Protokoll; Test über mehrere Tage inkl. Monatswechsel und ausgefallener Nacht | 1,5 Tage |
| B5 | Übernahme-Eingang: Baldrian `bestand-nach` als `daten/uebernahme/`, Fall-Bezug im Protokoll, Teilbestand im Monatsbericht | 0,5 Tag |
| B6 | Tarifplan: erzeugte Generationentabellen aus der Config; Kern-Referenzwerte je Generation | 0,5 Tag |
| B7 | `deploy/plv/`: Dockerfile, Compose, Timer, README; Workflow `plv-image.yml`; Erstbefüllung dokumentiert | 0,5 Tag |
| B8 | Seite: Abschnitt "Bestand heute" aus dem Stand; Stands-Paket als Quelle für `falldaten` | 1 Tag |

Zusammen etwa sechs bis sieben Arbeitstage. Reihenfolge B1 bis B4 zuerst
(danach läuft die PLV täglich auf dem Entwicklerrechner), B7 als
nächstes (danach läuft sie unter `~/apps/plv`), B5, B6 und B8 danach.

**Merge-Weg.** Eigener Branch `plv-betrieb`, abgezweigt vom Stand von
PR #11 (730fcb0), ohne Umbasieren als Merge-Commit gegen `main` (PR #13,
gemergt 2026-09-06 als f066b55; Systemstände und Snapshots binden
Commit-Shas, deshalb kein Rebase). Vorher wurde er in den Seiten-Branch
gemergt, damit das Redesign der Vorzeigeseite das Stands-Paket und
„Bestand heute" nutzen konnte. Der Architektur-Strang lief parallel auf
seinem Branch; die einzige Berührung war die Einordnung des neuen Pakets
in die Ebenen der Schichtenkarte, und die blieb konfliktfrei.

## 10 Offene Fachentscheidungen

- Rechnungsgrundlagen der aktuellen Generationen KLV und BU ab 2025
  (Aktuariat der Vorzeige).
- Meldeverzug Tod: Verteilung und Median (Vorschlag: lognormal, Median 14
  Tage, 95 Prozent unter 60 Tagen).
- Bewertungsstichtag des Monatsabschlusses: Erster des Folgemonats
  (Konvention Monatserster) oder Monatsultimo als Datum der Datei; das
  Konzept nimmt den Ersten des Folgemonats.
- Getrennter Ausweis des übernommenen Teilbestands: dauerhaft oder bis
  zum ersten Jahresabschluss nach der Übernahme.
- Ob die öffentliche Seite Monatsstände oder auch Tagesstände zeigt.

## 11 Was dieses Konzept nicht ist

Keine Änderung an Bewertung, Rechenkern-Formeln oder Gate-Verträgen.
Keine Modellierung von Feiertagen, Stornierungen von Anträgen, Mahnwesen
oder Zahlungsverkehr. Kein Ersatz der Fall-Arbeitsbereiche: Eine
Migration bleibt ein Fall mit Gates und Zeichnungen; erst ihr Ergebnis
tritt als Zugang in den Tagesbetrieb ein.
