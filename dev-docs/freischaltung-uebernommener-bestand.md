# Freischaltung des uebernommenen Bestands: ein Rechenweg fuer Pruefstrecke und Fuehrung

**Stand:** Fachkonzept und Schrittliste, 2026-09-07 (dev-Session, nach
der fachlichen Klaerung mit dem Maintainer zu Review-Befund T22-11).
Abschnitt 6 fuehrt den Stand je Schritt und wird beim Umsetzen
fortgeschrieben.

**Anlass:** Der zweite Baldrian-Fall (`baldrian-klv-tg2015-lauf2`, A-M4
angenommen 2026-09-01) hat im Lauf drei Tarifwerks-Eigenschaften der
Quelle aufgedeckt und in die Pruefstrecke eingebaut: Erhoehungsscheiben
mit voller Beitragsformel (Korrektur 6, Kern 3.2.0), Stornoabzug je
Baustein (Korrektur 7, Kern 3.3.0), Teilkuendigung als
Herabsetzungsverfahren (Korrektur 16). Dazu die Korrekturschicht auf
dem Verankerungsresiduum. Alle drei Abnahmen und das Migrations-
controlling rechnen damit, 834 von 834 Vertraegen bestehen. Die
Bestandsfuehrung, die diese Vertraege seit dem 2026-01-01 fuehrt, rechnet
NICHTS davon. Sie kennt weder die Bausteine der Vertraege noch die
Schalter noch die Schicht. Was abgenommen wurde, ist nicht das, was
gefuehrt wird.

## 1 Kontext: zwei Rechenpfade

Das System hat fuer einen uebernommenen Vertrag heute zwei Wege, seine
Werte zu bilden.

**Die Pruefstrecke** (`gates.aktuartest_lauf`, `qa.aktuarieller_test`,
`gates.migrationssuite_lauf`, `qa.migrationssuite`,
`gates.verankerung_belegen`) baut je Vertrag aus den transformierten
Lieferzeilen und der registrierten Vorgeschichte einen
**Anfangszustand**: die Ursprungs- oder Grundsumme, die Alt-Erhoehungs-
scheiben aus dem belegten Dynamiksatz, das Jahr einer Beitragsfrei-
stellung, den Anteil einer Herabsetzung
(`migrationssuite_lauf.anfangszustaende_je_police`, Ableitungen in
`bestand.migrationszugang`). Auf diesem Zustand rechnet sie mit den
Lauf-Schaltern `--scheiben-mit-gamma1`, `--stoab-je-baustein`,
`--red-verfahren teilkuendigung` und dem Dynamiksatz, und sie legt die
Korrekturschicht aus dem Schichtbeleg darueber. Genau das haben A-M1
bis A-M4 abgenommen.

**Die Fuehrung** (`gates.bestand_uebernehmen`, `bestand.ereignisse`,
`bestand.kernlauf`, `bestand.auswertung`, `bestand.abschluss`,
`bestand.ledger_bindung`) nimmt die transformierte Zeile, wie sie ist:
Die gelieferte Summe wird die Versicherungssumme des Stamms, egal ob
sie eine Gesamtsumme aus sieben Bausteinen oder eine beitragsfreie
Summe ist. Die Uebernahme schreibt keine Scheiben (`GEVO_STATUS` laesst
ERH und RED bewusst aus, weil sie den Zustand nicht aendern), keine
Schichtparameter, und sie rechnet die beitragsfreie Summe eines
beitragsfrei gelieferten Vertrags aus der gelieferten Summe, die schon
die beitragsfreie ist. Die Ereignis-Engine bildet den Rueckkaufswert
vertragsweit (`kernlauf.vertrags_rkw`), legt neue Scheiben ohne gamma1
an (`erhoehungs_scheibe` mit Vorgabe) und kennt keine Schicht. Das ist
das Tarifwerk des eigenen Geschaefts der PLV (Tarifplan KLV, Abschnitte
6 und 7), angewandt auf einen Bestand, fuer den ein anderes
Bedingungswerk gilt.

Die beiden Pfade beruehren sich an keiner Stelle. Kein Gate vergleicht
das Ledger der Fuehrung mit den Werten der Pruefstrecke; A-M4 bindet
den Bestandsbericht nach der Migration nur ueber seinen Hash.

### 1.1 Zahlenwirkung im zweiten Baldrian-Fall

Gemessen am 2026-09-07 auf den Fall-Artefakten (Uebernahme
`abgeleitet/bestand`, Fortschreibung `abgeleitet/bestand-nach` bis
2027-01-01, Schichtbeleg `abgeleitet/schichten`), Pruefstrecken-Welt =
Anfangszustand wie in A-M4, Scheiben mit gamma1, Stornoabzug je
Baustein, Korrekturschicht. Ad-hoc-Messung der dev-Session, kein
Tooling; sie wird durch die Fuehrungsprobe (Schritt 6) ersetzt.

| Groesse | Fuehrung heute | Pruefstrecke (abgenommen) |
|---|---|---|
| Vertraege, deren Stammsumme nicht die Grund-/Ursprungssumme ist | 550 von 834 | (390 mit 2307 Alt-Scheiben, 160 beitragsfrei) |
| Umbuchung beitragsfrei bei der Uebernahme (160 Vertraege) | 1.716.338 EUR | 3.646.718 EUR (= gelieferte beitragsfreie Summen) |
| Zugangssumme der Uebernahme (834 Vertraege) | 55.135.289 EUR | 62.884.551 EUR (Gesamt-VS der Bausteine) |
| Buchungen nach dem Stichtag, abweichend | 14 von 42 (STO 10/20, PEX 3/8, TOD 1/7, ABL 0/7) | groesste Einzelabweichung 16.254 EUR (Todesfall eines beitragsfreien Vertrags: 20.902 statt 37.156 EUR) |
| Deckungskapital der 800 uebernommenen in-force am 2027-01-01 | 33.370.245 EUR | 33.960.716 EUR (beide auf der Config-Welt gerechnet, siehe Mechanismus 4) |
| Rueckkaufswerte derselben Vertraege | 31.322.652 EUR | 30.102.145 EUR |
| Anteil der Korrekturschicht an allen Abweichungen | | hoechstens 0,02 EUR je Vertrag (rho in der Groessenordnung 1e-7) |

Drei Mechanismen, nach Gewicht:

1. **Beitragsfrei gelieferte Vertraege werden doppelt umgewandelt.** Der
   Abzug fuehrt bei ihnen die beitragsfreie Summe; die Uebernahme nimmt
   sie als Versicherungssumme und rechnet daraus noch einmal eine
   beitragsfreie Summe (`_beitragsfreie_summe` auf der gelieferten
   Summe, obwohl der Docstring die Umkehrung beschreibt). Die
   Pruefstrecke invertiert (`leite_pex_ursprungssumme_ab`) und
   reproduziert die gelieferte Summe exakt. Folge: beitragsfreier
   Bestand um 2,0 Mio EUR zu klein, Todes- und Ablaufleistungen dieser
   160 Vertraege um den Umwandlungsfaktor zu niedrig.
2. **Alt-Erhoehungen sind keine Bausteine.** Ein Vertrag mit sieben
   Erhoehungen wird als EIN Vertrag mit der Gesamtsumme ab
   Versicherungsbeginn gefuehrt. Seine Reserve ist damit zu hoch (die
   jungen Bausteine haben weniger Reserve als ein alter), sein
   Rueckkaufswert bei Storno erst recht (dazu der vertragsweite statt
   bausteinweise Stornoabzug), seine beitragsfreie Summe bei einer
   spaeteren Freistellung ebenfalls. Zehn der zwanzig Stornobuchungen
   nach dem Stichtag weichen ab, bis 12.880 EUR je Vertrag.
3. **Die Korrekturschicht fehlt strukturell, nicht numerisch.** Im
   zweiten Fall sind die Residuen Rundungsrauschen (max. 0,02 EUR).
   Das ist ein Befund ueber diese Lieferung, nicht ueber die
   Architektur: Ein Bestand mit echten Residuen wuerde in der Fuehrung
   ohne Schicht andere Rueckkaufswerte zahlen als abgenommen.
4. **Die Config rechnete mit den Grundlagen von vor A-Q1** (gefunden
   bei der Neuerzeugung, Schritt 8): Der TG2015-Block der Bestand-Config
   des Falls und der PLV-Config trug den Rechnungszins 1,75 % des
   Tarifrechners statt der in A-Q1 entschiedenen 1,25 % der Mitteilung,
   und fuer die Haus-Zellen Inkassokosten 0 statt 0,01. Die Abnahmen
   rechneten mit der Spez (1,25 %), die Fuehrung mit der Config
   (1,75 %). Der Tarifplan KLV behauptete 1,75 %. P-B1 im Vollprofil
   und die Fuehrungsprobe (Grundlagen der Config gegen die Spez-Zelle)
   finden das jetzt; der Block wird aus dem Spez-Abschnitt der
   Uebernahme uebernommen, ein Test haelt ihn gegen die Spez-Fixture.

Vier Vertraege (7000539, 7000722, 7000754, 7000910) haben in der
Pruefstrecken-Ableitung keinen bestimmbaren Anfangszustand (Serie mit
offener Herabsetzung, kein Jahresbeitrag, kein Ankerwert). A-M4 hat
sie als Grundvertrag mit der Gesamtsumme geprueft und angenommen:
Nach dem Ende der Beitragszahlung ist die Summe der Bausteine
wertgleich mit einem Vertrag der Gesamtsumme, der Vergleich traegt.
Die Uebernahme fuehrt sie genauso und weist es aus (Schritt 3); die
Fuehrungsprobe (Schritt 6) sieht dieselbe Ableitung und meldet die
Vertraege als ausgewiesene Ausnahme, nicht als Befund.

### 1.2 Warum die Abnahmen das nicht sehen konnten

Die Abnahmen pruefen die Pruefstrecke gegen die Erwartungswerte der
Quelle. Das ist ihr Zweck, und den erfuellen sie. Sie sind die
Entwicklungsroutine fuer den Zielkern: Sie zeigen, dass das System die
Vertraege der Quelle richtig rechnen KANN. Ob der gefuehrte Bestand
diese Faehigkeit auch benutzt, prueft niemand. Die Fuehrung wurde in
beiden Baldrian-Faellen nur ueber P-B1 (Form, Invarianten,
Bewegungs-Identitaet, Kern-Herleitung jeder Buchung aus dem STAMM)
gebunden. P-B1 prueft, dass jede Buchung aus dem Stamm folgt; dass
der Stamm die falsche Welt ist, kann es nicht wissen.

Die Befunde 6 und 7 des Lauf-2-Korrekturprotokolls sind waehrend des
Falls entdeckt und im Kern als Opt-in-Parameter umgesetzt worden
(`erhoehungs_scheibe(gamma1_uebernehmen=...)`,
`vertrags_monatsreserve(stoab_je_baustein=...)`, Commits fc01663 und
2b35155, Fachbericht Systemaenderung 4 und
`docs/faelle/baldrian-lauf2-veraenderungen.md`). Der Kern kann beides;
gerufen wird es nur von der Pruefstrecke. Genau diese Luecke, "kann"
ohne "tut", ist das Thema.

## 2 Fachliche Festlegungen (Maintainer, 2026-09-07)

Diese Punkte sind entschieden und werden hier nicht neu verhandelt.

- **Der Rueckkaufswert darf sich durch die Migration nicht aendern.**
  Was die Quelle zugesagt hat, zahlt die PLV. Der Rueckkaufswert eines
  uebernommenen Vertrags ist Basiswert plus Korrekturschicht, mit
  Stornoabzug je Baustein und den Bausteinen, die der Vertrag bei der
  Quelle hatte. Das gilt im Betrieb, nicht nur im Test.
- **Der Abbau der Korrekturschicht ist grundsaetzlich definiert.**
  Grundsatzdokumentation 9.6 bis 9.13 und die Ausgestaltung des
  Tarifplans des Falls (`abgeleitet/tarifplan-ausgestaltung.md`:
  STO wertkontinuierlich, PEX absorbierend, ERH Klasse B mit eigenem
  Verankerungspunkt, Formfunktion proportional zur Basis, keine
  Floors, R_conv nicht aktiv) legen fest, wie die Schicht laeuft und
  wann sie erlischt. Nichts davon fehlt; es ist nur nicht in der
  Fuehrung gebaut.
- **Stornoabzug je Baustein: immer, fuer den uebernommenen Bestand.**
  Die Garantiewerte der Quelle beruhen darauf. Fuer das eigene
  Geschaeft der PLV bleibt der vertragsweite Abzug des Tarifplans KLV.
  Es ist eine Eigenschaft der Generation, keine des Laufs.
- **Die Abnahmetests sind die Entwicklungsroutine fuer den Zielkern.**
  Sie bleiben, wie sie sind, und ihr Explorationsweg (Schalter je
  Lauf, Kandidatenmengen, Plausibilitaets-Antraege) wird NICHT
  geschlossen. Das Migrationsteam muss weiter ausprobieren koennen.
- **Was die Tests 1 bis 3 bestanden hat, ist de facto freigegeben und
  MUSS fuer den uebernommenen Bestand freigeschaltet werden.** Die
  Freischaltung ist ein eigener, benannter Schritt vor A-M4. Was nicht
  freigeschaltet ist, wird nicht gefuehrt, und A-M4 zeichnet es nicht.
- **Zwei Wege fuer Betriebsfunde**, Kriterium: falsifiziert der Befund
  ein gezeichnetes Artefakt? Wenn ja, Entwicklerweg (Fall korrigieren,
  Artefakt neu erzeugen, Neuzeichnung mit Korrekturvermerk). Wenn nein,
  Betriebsweg (System korrigieren, Betrieb aus der Uebernahme neu
  aufsetzen). Beide Wege muessen als Routinen existieren (Ebene 4,
  ADR-017), nicht als Handarbeit.

## 3 Zielbild

Ein uebernommener Vertrag hat in der Fuehrung dieselbe Welt wie in der
Pruefstrecke: denselben Grund-Modellpunkt, dieselben Bausteine mit
derselben Rechnungsgrundlage, dieselbe Beitragsfreistellung, dieselbe
Schicht, dieselben Tarifwerks-Schalter. Es gibt EINEN Ort, an dem der
Anfangszustand entsteht (die Ableitungen in `bestand.migrationszugang`,
gerufen ueber `anfangszustaende_je_police`), und die Uebernahme
MATERIALISIERT ihn in den Tabellen des Bestands: Stamm mit
Grund-/Ursprungssumme, `scheiben.parquet` mit den Alt-Bausteinen,
`historie.parquet` mit der Beitragsfreistellung, `verankerung.parquet`
und `schichten.parquet` mit der Schicht. Die Tarifwerks-Schalter stehen
je Generation in der Bestand-Config, die Fuehrung liest sie dort, und
ein Produzent vor A-M4 (die Fuehrungsprobe) stellt Fuehrung und
Pruefstrecke gegeneinander. Die Schalter der Pruefstrecke bleiben
Lauf-Schalter (Exploration); die Freischaltung uebertraegt den
abgenommenen Stand in die Config und in die Uebernahme.

## 4 Vorgehen in Schritten

Jeder Schritt nennt, was er baut, warum in dieser Reihenfolge, und
woran man erkennt, dass er fertig ist. Die Reihenfolge ist so gewaehlt,
dass jeder Schritt fuer sich gruen committet werden kann.

### Schritt 1: Zahlenwirkung messen

Vor jeder Aenderung muss die Groesse des Problems belegt sein, sonst
streitet man ueber Architektur, wo es um Bilanzzahlen geht. Die Messung
aus Abschnitt 1.1 ist dieser Beleg: Sie stellt je Buchung der Fuehrung
nach dem Stichtag den Wert der Pruefstrecken-Welt daneben und
summiert Deckungskapital und Rueckkaufswert am Folgestichtag. Sie ist
ad hoc und wird nicht Tooling; ihr Nachfolger ist die Fuehrungsprobe
(Schritt 6), die dasselbe als Produzent mit Beleg tut.
Fertig, wenn: die Zahlen in Abschnitt 1.1 stehen. ERLEDIGT 2026-09-07.

### Schritt 2: Tarifwerks-Schalter als Eigenschaft der Generation

Die drei Eigenschaften (Scheiben mit gamma1, Stornoabzug je Baustein,
Herabsetzungsverfahren) sind heute Lauf-Schalter der Pruefstrecke. Im
Betrieb gibt es keinen Lauf, der sie setzen koennte; sie muessen dort
stehen, wo die Fuehrung ihre Rechnungsgrundlagen holt: in der
`[[generation]]` der Bestand-Config, neben Zins und Tafel. Fuer
TG2015 stehen sie auf `scheiben_mit_gamma1 = true`,
`stoab_je_baustein = true`, `red_verfahren = "teilkuendigung"`; fuer
das eigene Geschaeft bleiben die Vorgaben (false, false, prospektiv),
die dem Tarifplan KLV entsprechen. Damit ist die Ausgestaltung des
Tarifplans (Grundsatzdokumentation 10 Nr. 9) erstmals maschinenlesbar
und nicht nur Prosa im Fall.
Fertig, wenn: `TarifGeneration` die drei Felder traegt und validiert,
`configs/bestand_gesamt.toml` sie fuer TG2015 setzt, der Tarifplan KLV
(Abschnitte 6, 7, 13) sagt, dass uebernommene Generationen hier
abweichen duerfen, und ein Test die Vorgabewerte pinnt.

### Schritt 3: Die Uebernahme materialisiert den Anfangszustand

`gates.bestand_uebernehmen` bekommt dieselben Eingaben wie die
Pruefstrecke (Dynamiksatz, Herabsetzungsverfahren, nachgelieferte
Anteile, Kandidatenmenge, Ankerwerte) und ruft dieselbe Ableitung
(`anfangszustaende_je_police`). Aus dem Ergebnis schreibt sie den
Bestand so, wie die Pruefstrecke ihn rechnet: die Stammsumme ist die
Grund- beziehungsweise Ursprungssumme; die Alt-Erhoehungen werden
`scheiben.parquet` (jede mit dem gamma1, das der Schalter der
Generation vorgibt, ueber `erhoehungs_scheibe`); die Umbuchung eines
beitragsfrei gelieferten Vertrags ist die beitragsfreie Summe des
Kerns auf der Ursprungssumme, und die muss die gelieferte Summe auf
den Cent reproduzieren (sonst harter Halt); der Zugang bucht die
Gesamt-Versicherungssumme ueber alle Bausteine. Ein Vertrag ohne
ableitbaren Anfangszustand wird wie in der Pruefstrecke als
Grundvertrag gefuehrt und im Uebernahmebeleg namentlich ausgewiesen;
still ist daran nichts, und die Fuehrungsprobe traegt dieselbe Liste.
Ein Herabsetzungs-
Zustand, den die Fuehrung nicht tragen kann (jedes Verfahren ausser
Teilkuendigung, die zustandslos weiterfuehrt), haelt ebenfalls an:
"nicht freigeschaltet" ist ein benannter Zustand, keine Naeherung.
Die Schalter, mit denen uebernommen wurde, schreibt die Uebernahme in
den Config-Abschnitt `generation-zellen.toml`, damit die Config, die
daraus entsteht, dieselben Werte traegt.
Fertig, wenn: das E2E des zweiten Laufs die Uebernahme mit den
Lauf-2-Schaltern faehrt, `scheiben.parquet` entsteht, die
PEX-Umbuchungen die gelieferten Summen sind, und ein Test die
Doppel-Umwandlung als Regression festhaelt.

### Schritt 4: Die Fuehrung liest den Anfangszustand

Die Ereignis-Engine nimmt mitgebrachte Scheiben entgegen
(`fortschreiben(..., scheiben=...)`, `cli_fortschreibung --uebernahme`
liest sie aus dem Uebernahme-Verzeichnis) und rechnet je Generation
nach ihren Schaltern: Rueckkaufswert ueber den Kern
(`vertrags_monatsreserve(..., stoab_je_baustein=...)`) statt ueber
die vertragsweite Formel in `kernlauf`, neue Scheiben mit
`gamma1_uebernehmen` nach Schalter. Auswertung, Abschluss und
Ledger-Herleitung (`ledger_bindung`) gehen denselben Weg, sonst
faende P-B1 die Buchungen der Engine nicht mehr aus dem Kern. Die
gamma1-Regel in `validate_scheiben` ("immer 0") wird zur
Config-Regel: 0 fuer Generationen ohne Schalter, das gamma1 der
Zelle mit Schalter. Fuer das eigene Geschaeft aendert sich kein
Betrag; das ist die Ratsche, die ein Test haelt.
Fertig, wenn: die Fortschreibung des Lauf-2-Bestands die Werte der
Pruefstrecken-Welt bucht (Messung aus Schritt 1 auf null), P-B1 im
Vollprofil gruen bleibt, und die Buchungen des eigenen Geschaefts
bit-identisch zum Stand davor sind. Der Tagesbetrieb
(`betrieb.tageslauf`, Branch `betrieb-haertung`) baut seinen Stand
taeglich aus der Basis neu und muss die mitgebrachten Scheiben dabei
durchreichen — das gehoert zu Schritt 9, nicht hierher.

### Schritt 5: Die Korrekturschicht in der Fuehrung

Der Schichtbeleg (`gates.verankerung_belegen`) wird als Nebentabelle
`schichten.parquet` in das Uebernahme-Verzeichnis geschrieben, mit
denselben Feldern wie `Schichtparameter.als_beleg()`
(Grundsatzdokumentation 9.11: Parameter, keine Zwischenwerte). Die
Fuehrung liest sie mit `verankerung.parquet` zusammen und wendet den
Katalog der Ausgestaltung an: Storno zahlt Basiswert plus Schichtwert
(`schichtwert_bei`, dieselbe Funktion wie in beiden Vergleichs-
Engines), Beitragsfreistellung absorbiert (rho danach null), Tod und
Ablauf sind unberuehrt (feste Summe beziehungsweise Terminalbedingung),
eine Erhoehung laesst die Schicht stehen. Der Abschluss weist die
Schicht je Vertrag als eigene Position aus, nie unsichtbar im
Deckungskapital. Fuer den zweiten Fall ist die Wirkung null; die
Struktur ist die Zusage aus Abschnitt 2.
Fertig, wenn: ein Vertrag mit konstruiertem Residuum in der Fuehrung
dieselben Storno- und Bewertungswerte liefert wie die Engine des
aktuariellen Tests, und der Abschluss die Schicht ausweist.

### Schritt 6: Die Fuehrungsprobe als Wache vor A-M4

Ein Produzent `gates.fuehrungsprobe` stellt den gefuehrten Bestand
gegen die Pruefstrecke: je uebernommenem Vertrag Grundsumme,
Bausteine, Freistellungsjahr, Schicht und Schalter gegen den
Anfangszustand der Pruefstrecke; je Buchung der Fortschreibung nach
dem Stichtag (Storno, Umbuchung, Tod, Ablauf) den Betrag gegen den
Wert der Pruefstrecken-Engine am gebuchten Vertragsmonat; dazu die
Schalter der Config gegen die Schalter, mit denen Schichtbeleg und
Migrationscontrolling gerechnet haben. Ergebnis ist ein JSON-Beleg mit
Befunden je Vertrag und `bestanden`. A-M4 verlangt ihn im
Bestands-Scope als Pflichtbelegrolle (`fall.BELEGROLLEN`,
`gate_entscheid`, `abnahmebericht`; Versionssprung nach der
Versionierungsregel, weil sich die Akzeptanzmenge aendert). Damit ist
die Frage "prueft die Abnahme eine Fiktion?" nicht mehr eine des
Vertrauens, sondern eines Belegs.
Fertig, wenn: das Lauf-2-E2E die Probe faehrt und besteht, ein
manipulierter Stornobetrag im Ledger sie rot macht, und A-M4 ohne den
Beleg im Bestands-Scope ablehnt.

### Schritt 7: Freischaltung als benannter Schritt im Migrationsfall

Der Skill `migrationsfall-durchfuehren` bekommt zwischen den Abnahmen
A-M1 bis A-M3 und dem Migrationscontrolling einen Abschnitt
"Freischaltung": die Schalter, mit denen die Abnahmen bestanden haben,
in die Config der Generation uebertragen; Uebernahme mit denselben
Eingaben fahren; Schichtbeleg in den Bestand schreiben; Fortschreibung;
Fuehrungsprobe. README und ONBOARDING nennen den Produzenten. Der
Explorationsweg bleibt: Die Abnahmen nehmen ihre Schalter weiter vom
Lauf; die Freischaltung ist der Moment, in dem ein Stand zur
Eigenschaft des Bestands wird.
Fertig, wenn: Skill (beide Spiegel), README, ONBOARDING und die
Befundliste den Schritt fuehren.

### Schritt 8: Den zweiten Baldrian-Fall korrigieren (Entwicklerweg)

Der Befund falsifiziert ein gezeichnetes Artefakt: Der Bestandsbericht
nach der Migration ist Pflichtartefakt von A-M4 und traegt falsche
Betraege. Also Entwicklerweg: Korrekturvermerk im Korrektur-Protokoll
des Falls (Nr. 24, Gebiet Kern/Gates, mit den Zahlen aus 1.1),
Uebernahme neu mit den Lauf-2-Schaltern, Schichtbeleg neu (seine
Provenienz bindet den Bestand), Bestand vor/nach neu, Fuehrungsprobe,
Abnahmebericht neu, A-M4 neu zeichnen. Die Neuzeichnung ist eine
Handlung der Rollen des Falls (Regie), nicht der dev-Session.
`docs/faelle/baldrian-lauf2.md` bekommt einen Nachtrag.
Fertig, wenn: der Fall einen neuen A-M4-Snapshot mit Korrekturvermerk
traegt und die Fuehrungsprobe im Fall gruen ist.
STAND 2026-09-07: Produzenten und Pruef-Gates auf Systemstand 9573bfc neu
gefahren (Korrektur-Protokoll Nr. 24), Fuehrungsprobe 834 Vertraege, 42
Buchungen, 0 Befunde, Abnahmebericht gruen. Die fuenf Zeichnungen (A-Q1,
A-M1, A-M2, A-M3, A-M4) stehen bei der Regie aus.

### Schritt 9: Den Betrieb aus der Uebernahme neu aufsetzen (Betriebsweg)

Die Laufzeitumgebung der PLV fuehrt seit dem 2026-01-01 den falschen
Bestand. Der Betriebsweg: die alte Ablage archivieren, die neue
Uebernahme als Eingang einspielen, den Stand ab Betriebsbeginn neu
fahren, Stands-Paket neu exportieren. Das braucht die Uebernahme des
Tagesbetriebs (`betrieb.uebernahme`, Branch `betrieb-haertung`), die
Scheiben und Schichten als Nebentabellen durchreicht, und eine
Routine "Betrieb neu aufsetzen" (Ebene 4), die heute nicht existiert.
Die Config der Laufzeit bekommt die Schalter aus Schritt 2.
Fertig, wenn: die Laufzeit mit einem Stand laeuft, dessen Uebernahme
die Fuehrungsprobe bestanden hat, und die Routine dokumentiert ist.

### Schritt 10: Die Prozessregel fuer Betriebsfunde festschreiben

Das Kriterium aus Abschnitt 2 und die beiden Wege gehoeren in das
Fachkonzept des Tagesbetriebs (`docs/simulation/tagesbetrieb.md`) und
in ONBOARDING, damit der naechste Befund nicht wieder eine
Grundsatzdiskussion ist. Dazu die Regel, dass ein Befund, der ein
gezeichnetes Artefakt trifft, im Korrektur-Protokoll des Falls
landet und eine Neuzeichnung ausloest, und dass "Betrieb neu
aufsetzen" eine Routine mit Beleg ist.
Fertig, wenn: beide Texte den Abschnitt tragen.

### Schritt 11: Kommunikation

Die Antwort an den Reviewer zu T22-11 nennt den Befund vollstaendig
(nicht nur Stufe 1), mit den Zahlen aus 1.1 und dem Vorgehen. Das Team
erfaehrt, dass der Bestand der PLV neu aufgesetzt wird und warum.
Fertig, wenn: die run-Session die Antwort mit dem Go des Maintainers
abgesetzt hat.

## 5 Einordnung

**Aufwand:** Schritte 2 bis 4 und 6 sind der Kern, zusammen etwa drei
bis vier Tage; Schritt 5 ein bis zwei Tage; 7 und 10 ein halber Tag;
8 und 9 haengen an Regie und Laufzeit.

**Branch und PR-Reihenfolge:** Die Umsetzung liegt auf einem eigenen
Branch `freischaltung` ueber `ebenen`, weil die A-M4-Bindung der
Fuehrungsprobe die Belegrollen-Aenderungen aus Review T22 (Vollprofil
von P-B1, T-Box-Beleg) fortsetzt. Reihenfolge der PRs:
`betrieb-haertung` (Tagesbetrieb, von main), `ebenen` (PR #14), dann
`freischaltung`. Schritt 9 lebt auf `betrieb-haertung` oder danach.

**Was die Loesung NICHT leistet:** Sie schliesst den Explorationsweg
nicht und ersetzt die Abnahmen nicht. Sie baut keine Fuehrung fuer
Herabsetzungs-Zustaende nach den PLV-Verfahren (prospektiv, mit
Abzug); die bleiben "nicht freigeschaltet" und halten die Uebernahme
an, bis ein Fall sie verlangt. Sie loest nicht die Frage, ob eine
uebernommene Generation irgendwann auf das Zusagewerk der PLV
uebergeht; das waere ein eigener Tarifplan-Entscheid.

**Wer entscheidet:** Der Maintainer hat die fachlichen Festlegungen
getroffen (Abschnitt 2). Die Neuzeichnung von A-M4 (Schritt 8) trifft
die Rolle des Falls. Der Zeitpunkt des Betriebsneuaufbaus (Schritt 9)
liegt beim Maintainer.

## 6 Stand je Schritt

| Schritt | Stand |
|---|---|
| 1 Zahlenwirkung messen | ERLEDIGT 2026-09-07 (Abschnitt 1.1) |
| 2 Schalter je Generation | ERLEDIGT 2026-09-07 (ff18e03) |
| 3 Uebernahme materialisiert Anfangszustand | ERLEDIGT 2026-09-07 (4a59730); Pruefstrecke nimmt ohne Zustand die gelieferte Summe |
| 4 Fuehrung liest Anfangszustand | ERLEDIGT 2026-09-07 (Engine, Bewertung, Ledger-Herleitung, Fortschreibungs-Kommando); Tagesbetrieb folgt in Schritt 9 |
| 5 Korrekturschicht in der Fuehrung | ERLEDIGT 2026-09-07 (schichten.parquet aus dem Schichtbeleg, Storno und Abschluss mit Schicht, P-B1 4.0.0) |
| 6 Fuehrungsprobe vor A-M4 | ERLEDIGT 2026-09-07 (gates.fuehrungsprobe; Pflichtbelegrolle im Bestands-Scope, Abnahmebericht 3.0.0, P9 2.0.0) |
| 7 Freischaltung im Skill | ERLEDIGT 2026-09-07 (Skill migrationsfall-durchfuehren, Stufe 1b und 3b; Befundliste, Backlog) |
| 8 Fall Lauf 2 korrigieren | Produzenten neu (2026-09-07, Systemstand 9573bfc, Korrektur 24); Zeichnungen bei der Regie offen |
| 9 Betrieb neu aufsetzen | offen (betrieb-haertung, Laufzeit) |
| 10 Prozessregel Betriebsfunde | ERLEDIGT 2026-09-07 (docs/simulation/tagesbetrieb.md, Abschnitt 6.1) |
| 11 Kommunikation | offen (run-Session, Go des Maintainers) |
