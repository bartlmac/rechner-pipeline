# Vorzeigeseite: statische Stellen und ihre Automatisierung

**Seit 2026-09-08 gilt das Seitenkonzept** (`vorzeige-seitenkonzept.md`):
Bereiche Risikomanagement und Finanzen entfallen, ihre Kennzahlen stehen
unter Geschaeftsentwicklung; neue Seite "Hinter den Kulissen" (ausserhalb
der Fiktion) traegt die Simulationsdokumente. Zeilen dieser Liste, die
diese Bereiche nennen, sind entsprechend zu lesen; die Automatisierung der
Verlinkung mit der Codebasis ist zurueckgestellt.

Quelle fuer Schritt 1 des frueheren Maintainer-Pruefplans (entfernt am
2026-10-04 mit den Arbeitsdokumenten abgeschlossener Runden). Erhoben beim
Inhalts-Nachzug Lauf 2 (2026-09-02). "Automatisiert" heisst: Der Wert
wird beim Bau aus dem falldaten-Modell des Falls GENERIERT
(`{{...}}`-Kennzahlen in den Quellseiten, aufgeloest von
werkzeuge/unternehmensseite.py; ein unaufloesbarer Platzhalter bricht
den Bau ab). Was Prosa bleibt, ist benannt und begruendet.

## Automatisiert (Wert kommt je Bau aus dem Modell)

| Stelle | Seite | Kennzahl-Quelle im Modell |
|---|---|---|
| Vertraege in Kraft, Stand, Buchungen, Neugeschaeft, aus Uebernahmen (Block Geschaeftsentwicklung) | index, geschaeftsentwicklung, finanzen | betrieb.* aus dem Stands-Paket (Pflicht; generierte SVGs buchungen_je_art, bestand_vergleich_tief; Tabellen buchungen_je_art, abschluesse, uebernahmen_im_stand). Seit 2026-09-19 traegt der Kennzahlkopf bestand_vergleich_tief die Bestandszahlen; die wiederholende Tabelle und das zweite Produktdiagramm sind von der Seite genommen (Erzeuger bestand_je_produkt bleibt im Modul) |
| Geschaeftsentwicklung: Neuzugang/Leistungen x drei Zeitraeume, Anzahl + Betrag | index, geschaeftsentwicklung | betrieb.geschaeftsentwicklung (Stands-Paket, aus dem Tagesjournal; html:geschaeftsentwicklung) |
| Fertiggestellte Migrationen: Block je Uebernahme (Name, Stichtag, Vertraege, Struktur, DK, Abnahme-KPIs, Verweise) | index, migrationen | fall.name + bestand.verteilungen (Name), abnahmen.controlling, bestand.*, abnahmen.aktuariell[*], parameter.diskrepanzen (html:migrationen_bloecke) |
| Migrierte Vertraege (Kennzahl Block Migration) | index | bestand.anzahl |
| Zusammensetzung des Zugangs (Grafik POL/PEX) | index | bestand.verteilungen.status_code (generierte SVG) |
| Geschaeftsvorfaelle im Migrationsjahr (Kennzahl) | index | bestand.vorfaelle_im_zeitraum.anzahl |
| Geschaeftsvorfaelle je Art (Grafik) | index | bestand.vorfaelle_im_zeitraum.je_art (generierte SVG) |
| Prueffluecken des Controllings | index | abnahmen.controlling.pruefluecken |
| Migrationsstichtag | index, migrationen | abnahmen.controlling.stichtag_1 |
| Vertraege in der Uebersichts-Tabelle | migrationen | bestand.anzahl |
| Uebernommenes Deckungskapital | migrationen, finanzen | bestand.abzuege.0.deckkap.summe |
| Laufender Jahresbeitrag | finanzen | bestand.abzuege.0.jbrutto.summe |
| Versicherungssumme der Lieferung | finanzen | bestand.abzuege.0.erlsumme.summe |
| Geschaeftsvorfall-Tabelle je Art | geschaeftsentwicklung | bestand.vorfaelle_im_zeitraum.je_art (generierte Tabelle) |
| Kennzahlenband (Umfang / Prueftiefe / Verbindlichkeit) | index, Fallbericht | bestand.anzahl, abzuege[0].deckkap.summe, vorgeschichte.anzahl; abnahmen.controlling.verteilung.anzahl_werte, aktuariell[*].verteilung.anzahl_werte, pruefluecken; kette.entscheide[in_finaler_kette], A-M4.artefakte_gebunden, gates[*].versuch |
| Toleranz-Leitgrafik (Schranke gegen groesste Abweichung) | index, Fallbericht | abnahmen.aktuariell[*].{verteilung,grundtoleranz}, controlling.verteilung |
| Der Fall in fuenf Stationen | index | lieferung.anzahl(+nachgereicht), transformation.anzahl_zielfelder, parameter.diskrepanzen (echte Feststellungen), controlling.verteilung.anzahl_werte, finale Zeichnungen |
| Widerspruch-Teaser | index | parameter.diskrepanzen (feld zins: Lesarten mit Quelle, gewaehlt, entscheider) |
| Abgrenzungsband | index, Fallbericht | abgrenzungen[], luecken[], umbau.befunde |
| Seite "Unsere Pruefgates" (Tabelle aller Gates) | it/pruefgates | `python -m rechner_pipeline.gates.register --format markdown` (Register als Code, Tests binden es an Module, GUELTIGE_GATES und fall.BELEGROLLEN); Backlog: dev-docs/vorzeige-backlog.md |
| Berichte als Kacheln | index, Fallbericht | abnahmen.aktuariell[*].bericht, bestandsberichte, Abschlussbericht, Uebersetzungsbericht, Landkarte |
| Korrekturschicht (Kernaussage) | Fallbericht | verankerung.{getragen,residuum_summe,residuum_max_abs} |
| Golden Master | Fallbericht | parameter.golden_master (P-K1-Ledger) |

## Bleibt Prosa (mit Begruendung)

| Stelle | Seite | Grund / Quelle |
|---|---|---|
| Stammdaten der Fiktion (Rechtsform, Sitz, Gruendung) | index | Fiktion, kein Artefakt |
| PLATZHALTER Bruttojahresbeitrag (Neuzugang) | index, geschaeftsentwicklung | das Bestandsmodell fuehrt keinen Beitrag; gebuchte Betraege (VS, Jahresrente) werden daneben gezeigt |
| PLATZHALTER letztes Jahr | index, geschaeftsentwicklung | Tagesbetrieb erst seit 2026-01-01 ("vor Betriebsbeginn"), loest sich 2027 von selbst |
| PLATZHALTER Dauer und Kosten je Migration | index, migrationen | keine Artefakt-Quelle (Sitzungsprotokoll, Token) — Backlog |
| PLATZHALTER "Aktuelle Migration: Baldrian Rentenversicherungen" | index, migrationen | Fall existiert noch nicht; Prosa-Kasten bis der Fall laeuft |
| Methodik-Bullets | index, migrationen | Prosa (Selbstverstaendnis), verlinkt auf generierte Pruefgates-Seite und Konzept |
| Bestandsstruktur nach Vorgeschichte (257/360/160/57) | migrationen | steht so nicht im Modell; uebernommen aus docs/faelle/baldrian-lauf2.md (versionierte VU-Quelle — aendert sich dort, faellt der Widerspruch im Review auf) |
| Erzaehlsaetze (Selbstverstaendnis, Banderole, Zaehlwerk-Hinweis) | alle | Prosa; das Zaehlwerk-Prinzip ist lauf-unabhaengig formuliert |
| Tarifgenerations-Nennung (KLV TG2015) | aktuariat | aus dem importierten Tarifplan ersichtlich; Nennung ist Text |
| Abschlussbericht des Falls | migrationen | wird als Fachdokument aus docs/faelle/baldrian-lauf2.md importiert (eine Quelle, eine Heimat) |

## Geschlossene Restluecke (2026-09-06)

Eigene PLV-Buchzahlen kommen seit B8 aus dem Stands-Paket des
Tagesbetriebs (Modellgruppe `betrieb`, `auftritt.py --stands-paket`):
Vertraege in Kraft je Produkt, davon aus Uebernahmen, Neugeschaeft,
Buchungen je Art, Monatsabschluesse, Zugaenge aus Uebernahmen. Die
Migration steht in den Buechern als datierter Zugang (Fachkonzept
Tagesbetrieb, Abschnitt 6) — "davon aus Uebernahmen" macht die Menge
kenntlich, damit niemand Bestand und Migrationszugang addiert. Der
Referenzlauf `abgeleitet/bestand-vor/` bleibt Fall-Artefakt (Kachel im
Fallbericht) und ist keine Quelle der Startseite mehr.
