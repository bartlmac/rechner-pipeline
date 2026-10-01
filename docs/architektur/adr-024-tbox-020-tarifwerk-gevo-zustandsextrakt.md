# ADR-024: T-Box 0.2.0 — Tarifwerk, Geschaeftsvorfaelle, Zustandsextrakt

**Status:** angenommen 2026-10-01. Vorgeschlagen und als Entwurf gebaut vom
Architektur-Agenten (`agent/architektur`) unter dem Entwicklungsauftrag des
Maintainers vom selben Tag; der Maintainer hat Vorschlag und Diffs als
Architekt durchgesehen und die Umsetzung freigegeben. Die ZEICHNUNG steht
noch aus und ist ein Artefakt des Falls: `A-O1.tbox-aenderung` mit
Aenderungsbeleg und Stellungnahme des Aktuariats zeichnet `mensch/architektur`
im ersten Migrationsfall, der auf diesem Stand rechnet (ADR-018, Nachtrag
2026-10-01: Weg (a)); spaetere Faelle verweisen darauf (Weg (b)). Bis dahin
nimmt A-M4 keinen Fall auf T-Box 0.2.0 an.

## Kontext

Die T-Box stand seit ihrer Einfuehrung auf `0.1.0`; die Versionslinie hatte
ein Element, der Uebergangsmechanismus (Vorgaenger-Pruefung in der Linie,
Beleg `abgeleitet/tbox/aenderung.json`, A-O1) war gebaut, aber nie gelaufen.
In derselben Zeit haben Kern und Bestandsfuehrung aufgebaut, was ein
uebernommener KLV-Bestand braucht: das Tarifwerk je Generation
(Erhoehungsscheiben mit $\gamma_1$, Stornoabzug je Baustein, Verfahren der
Herabsetzung), elf Geschaeftsvorfaelle mit Betragsarten, die Teilkuendigung
als eigenen Vorgang (ADR-023), Verankerung, Erhoehungsscheiben und
Herabsetzungen als Zustandsextrakt (Grundsatzdokumentation 9.12, 9.14), die
BU als zweite Produktfamilie. Die T-Box kannte davon nichts. Das Tarifwerk
einer uebernommenen Generation erreichte die Pruefstrecke als Schalter am
Aufruf (`--red-verfahren`, `--stoab-je-baustein`, `--scheiben-mit-gamma1`),
ohne Provenienz; die Zielfelder eines Bestandsabzugs standen als Konstante
in `ontologie.transformation`, ausserhalb der T-Box und ausserhalb ihrer
Version.

## Entscheid (vorgeschlagen)

1. **Version 0.2.0**, an die Linie angehaengt: `TBOX_VERSIONEN =
   ("0.1.0", "0.2.0")`. Der Uebergang ist rein additiv.
2. **Tarifwerk und Quellverfahren** sind generationsweite, belegte Aussagen
   der A-Box (`Tarifgeneration.tarifwerk`, `.quellverfahren`), mit
   Wertebereich, Merge, Diskrepanz am Knoten `<generation>/<block>`,
   Kettenpruefung, Coverage, Spez-Projektion und P-K1 in beiden Richtungen.
   Namen wie in der Bestand-Config. In 0.2.0 ausgewiesen, nicht blockierend.
3. **Katalog-Vokabular** (Geschaeftsvorfaelle, Vertragsstatus,
   Vertragsfelder einer Lieferung, rechnende Vorgaenge der Vorgeschichte,
   Zustandsextrakt, Formfunktionen, Produktfamilien mit Zustaenden und
   Rechnungsgrundlagen) steht in der T-Box als Spiegel der Konstanten des
   Codes; ein Test haelt jede Spiegelung mit `==`. Die T-Box importiert
   diese Konstanten nicht.
4. **Die BU ist Vokabular, nicht instanziierbar** (`ABOX_FAMILIEN =
   ("klv",)`).
5. **Abdruck des Vokabulars** (`vokabular_sha256`), je Version im Test
   festgehalten: eine Aenderung am Vokabular ohne Versionssprung ist rot.
6. **Hebung bestehender A-Boxen** ueber eine deklarierte Regel je Schritt
   der Linie (`ontologie.abox.HEBUNGEN`): 0.1.0 -> 0.2.0 aendert nur die
   Version, Entscheidungen (aufgeloeste Diskrepanzen) wandern unveraendert
   mit.

## Verworfene Alternativen

* **Import statt Spiegel** (die T-Box liest `EREIGNIS_VALUES` usw. aus
  `models`): Das Vokabular wanderte still mit dem Code, ohne Versionssprung
  und ohne A-O1 — genau die Nominalitaet, die Review T22-02 beseitigt hat.
* **BU als instanziierbare Familie:** Die T-Box versprache eine A-Box, die
  weder Extraktion noch Spez noch P-K1 verarbeiten koennen.
* **BU gar nicht:** Der Katalog der Geschaeftsvorfaelle liesse sich nicht
  gegen das Bewegungskonto halten (`INV`, `REA`, BU-Betragsarten).
* **Tarifwerk sofort Pflicht:** Jeder Tarif-Fall ohne Bedingungswerk als
  Quelle waere in P-Q3 rot; die Pflicht gehoert an den Fall-Scope
  `bestand` und an die Gates, die heute die Schalter lesen (naechste Stufe).
* **Quellverfahren im Tarifwerk:** Beide tragen `red_verfahren`, meinen aber
  Verschiedenes (Lesart der Lieferung gegen kuenftige Fuehrung).
* **Altform lesbar** (P-Q3 akzeptiert jede Version der Linie): machte den
  Versionsvergleich wieder nominal.

## Folgen

* Jede bestehende A-Box ist unter 0.2.0 fremd (P-Q3, P-K1). Laufende Faelle
  heben ihre A-Box (Entscheidungen bleiben) oder mergen neu; danach
  Neuzeichnung der Pruef-Gates auf dem neuen Stand. Abgeschlossene Faelle
  bleiben auf ihrem Stand.
* `A-O1` braucht einen Fall: Der erste Fall auf dem neuen Stand zeichnet den
  Uebergang 0.1.0 -> 0.2.0; das Artefakt des Belegs kann dieses ADR sein.
* Der Fachspez-Generator traegt Abschnitt 12 (Tarifwerk und Verfahren der
  Quelle); Version 0.2.0.
* Das Extraktionsschema (`QuellFragment`) hat die Felder `tarifwerk` und
  `quellverfahren`; `nicht_belegt` nennt Blockmerkmale qualifiziert
  (`tarifwerk.red_verfahren`).

## Nachtrag 2026-10-01: vor der ersten Zeichnung ergaenzt

Am selben Tag haben die Entscheide zur Folge von Vorgaengen (ADR-023,
Nachtrag 2026-10-01) das Tarifwerk um ein Merkmal erweitert. Weil noch kein
Fall auf 0.2.0 gezeichnet hat (A-O1 steht aus, siehe Status), ist 0.2.0
**vor seiner ersten Zeichnung ergaenzt** worden, ohne neue Version; der
Abdruck des Vokabulars ist fuer 0.2.0 neu gesetzt
(`tests/test_tbox_erweiterung_020.py`). Ergaenzt:

* Tarifwerk-Merkmal `tku_umfang` mit dem Wertebereich `TKU_UMFAENGE` =
  (`alle_bausteine`, `grundversicherung`) — welche Bausteine eine
  Teilkuendigung kuerzt (Tarifplan KLV 7.2, Entscheid B1); Spiegel von
  `kern.vorgangsfolge.TKU_UMFAENGE` und der Schluessel von
  `bestand.config.TarifGeneration.tarifwerk()`.
* Vorgabe des eigenen Geschaefts: `tku_umfang = alle_bausteine`.
* Lesart des Quellverfahrens (Beschreibung, nicht Vokabular): ab der
  Migration gilt das Vokabular des Zielsystems (Grundsatzdokumentation
  7.1); `teilkuendigung` heisst "der Tarif kennt keine Beitragsherabsetzung",
  eine gelieferte Absetzung danach und nach einer Beitragsfreistellung war
  eine Teilkuendigung (A2, Annahme B5).

Befuellung, Spez-Projektion, Coverage und Fachspezifikation (Abschnitt 12)
lesen die Merkmale aus `GENERATIONS_BLOECKE` und tragen das neue Merkmal
ohne eigene Aenderung. Wer auf dem Entwurfsabdruck gezeichnet haette, muesste
neu zeichnen — es hat niemand.

## Nachtrag 2026-10-01 (zweiter): die naechste Stufe ist gebaut — die Kommandos lesen die Spez

**Entscheid des Maintainers** zum Vorschlag "Die Tarifregeln eines
uebernommenen Tarifs muessen bei einer Bestandsmigration in der A-Box
stehen, belegt aus dem Bedingungswerk; die fuenf Kommandos lesen sie von
dort statt aus Schaltern": angenommen, mit dem Zusatz, auch die uebrigen
Regeln nachzuziehen ("kein Schalter von Hand, sondern Tabelle"); vor dem
Merge.

**Invariante.** Die Regeln eines Tarifs stehen EINMAL, belegt (A-Box ->
Spez), und jedes Kommando der Bestandsstrecke rechnet mit genau dieser
Fassung. Kein Kommando rechnet mit einer Vorgabe, die niemand belegt hat.

**Gebaut.**

1. *Pflicht im Scope bestand.* `tbox.BESTAND_PFLICHT` (das ganze Tarifwerk;
   im Quellverfahren `red_verfahren`, `dk_stichtag`, `formfunktion`) und
   `tbox.BESTAND_ERHOBEN` (`erhoehungssatz`: belegt oder ausdruecklich
   `nicht_belegt`); das Fenster folgt der Formfunktion. EINE Regel,
   `tbox.tarifregeln_luecken`, fuer P-Q3 und die Kommandos. P-Q3 (2.0.0)
   verweigert im Scope `bestand` mit Code `tarifregeln` und Ausweg; die
   Coverage weist das Urteil je Generation aus (`tarifregeln_bestand`),
   unabhaengig vom Scope.
2. *Die Grenze.* Im Scope `tarif` bleibt der Block ausgewiesen, nicht
   blockierend: Ein Tariffall fuehrt keinen Bestand, keine seiner
   Rechnungen liest die Bloecke, und eine Tarifmeldung ohne Bedingungswerk
   waere sonst rot, ohne dass etwas falsch gerechnet wuerde. Die Pflicht
   gehoert dorthin, wo die Regel rechnet.
3. *Quellverfahren erweitert* (vor der ersten Zeichnung von 0.2.0, ohne
   neue Version; Abdruck neu gesetzt): `erhoehungssatz` (Zahl, 0 < e < 1),
   `dk_stichtag` (`kalendertag`, `jahrestag`), `formfunktion`
   (`tbox.FORMFUNKTIONEN`), `fenster` (ganze Zahl >= 1). Zahlbereiche als
   `tbox.Zahlbereich`, typstreng wie die Aufzaehlungen.
4. *Eine Tuer.* `spez.tarifregeln.tarifregeln_der_spez` liefert die Regeln
   aus der ueber den einen Lader gelesenen Spez oder verweigert
   (`TarifregelnFehler`, mit Ausweg). Uebernahme, Verankerung,
   aktuarieller Test, Migrationscontrolling und Fuehrungsprobe beziehen
   sie dort; `--generation-spez` ist an der Uebernahme Pflicht.
5. *Die Schalter entfallen.* `--red-verfahren`, `--stoab-je-baustein`,
   `--scheiben-mit-gamma1`, `--tku-umfang`, `--erhoehungssatz`,
   `--dk-stichtag`, `--formfunktion`, `--fenster` werden an allen fuenf
   Kommandos sprechend verweigert (Exit 2, mit dem Abschnitt der Spez).
   Entschieden gegen den nackten argparse-Fehler: Die Schalter stehen in
   Laufnotizen, Skills und Aufrufen frueherer Belege; wer einen davon
   tippt, erfaehrt, wo die Regel jetzt steht und wie man sie aendert.
6. *Abgegrenzt.* Tarifwerk = Regel des Tarifs (Fuehrung). Quellverfahren =
   Eigenschaft der Quelle bzw. der Migration (Lesart der Lieferung,
   Dynamiksatz, Stichtag des gelieferten Deckungskapitals, Ausgestaltung der
   Korrekturschicht nach Grundsatzdokumentation 10 Nr. 9). Arbeitsannahme
   des Laufs und deshalb Schalter: `--red-anteil-kandidat`. Registrierte
   Eingaben bleiben Schalter mit Dateinamen (`--red-anteile-datei`,
   `--anker-erwartungswerte`, `--plausibilitaet-*`).
7. *Gefunden beim Bau.* Der Umfang der Teilkuendigung erreichte die
   Pruefauftraege von aktuariellem Test und Migrationscontrolling nie
   (`--tku-umfang` wirkte nur auf den Anfangszustand); jetzt geht er in
   jeden Auftrag. Der Fuehrungswert der Suite rechnet mit dem Tarifwerk
   der Config; das Migrationscontrolling verweigert eine Config, deren
   Tarifwerk nicht das der Spez ist (`bestand.migrationszugang.fuehrungswerte`).
8. *Belege.* Uebernahmebeleg, Schichtbeleg, aktuarieller Test, Suite und
   Fuehrungsprobe nennen die Regeln, mit denen sie gerechnet haben
   (`tarifregeln` bzw. `tarifwerk`/`quellverfahren`). Die Fuehrungsprobe
   traegt Fassung 5 (Aufruf ohne Tarifschalter); A-M4 (`gates.abnahmebericht`
   9.0.0) nimmt Fassung 4 nicht mehr an.

**Verworfene Alternativen.**

* *Schalter als Uebersteuerung* (Spez als Vorgabe, Schalter gewinnt): Ein
  Schalter, der die belegte Regel ueberstimmen kann, ist wieder Zweitwissen
  — dieselbe Tatsache an zwei Orten, und der Aufruf haette das letzte Wort
  ueber einen Beleg.
* *Vorgabe "PLV-Regel, wenn nichts belegt ist"*: der stille Default, genau
  der Fund des zweiten Laufs, in dem die Regel des uebernommenen Tarifs
  erst in A-M3 auffiel.
* *Formfunktion und Fenster in einem eigenen Block `migration`*: semantisch
  sauberer (sie sind keine Eigenschaft der Quelle), kostet aber ein
  weiteres Feld in vier Modellen (A-Box, Fragment, Spez, Befuellung) fuer
  zwei Merkmale, die wie das Verfahren der Quelle je Generation einmal
  entschieden werden. Naheliegende Einordnung gebaut (Quellverfahren); der
  eigene Block bleibt die Alternative, wenn die Ausgestaltung der
  Korrekturschicht mehr Merkmale bekommt (Floors, Ankerliste).
* *`--red-anteil-kandidat` in die Spez*: Die Kandidatenmenge ist eine
  Arbeitsannahme des Laufs, wo der exakte Anteil bei der Quelle nicht
  feststellbar ist, keine Regel des Tarifs. Waere sie eine (die zulaessigen
  Herabsetzungsstufen des Tarifs), gehoerte sie als Merkmal ins Tarifwerk.

**Fixtures.** Die eingefrorenen Spez der Baldrian-Laeufe haben keine A-Box;
ihre Regeln kommen ueber `spez.validierung.ergaenze_tarifregeln` aus dem
Dokument der Feststellung (`tests/fixtures/<lauf>/tarifregeln.json`, je
Merkmal mit Fundstelle) — der Test haelt die Bytes gegen den Weg
Hebung + Ergaenzung. Die P-K1-/A-M4-Fixture liefert die Regeln im Scope
`bestand` ueber ihren Produzenten (`tests/e2e_fixture.py`).

## Nachtrag 2026-10-01 (dritter): eine Version, ein Vokabular — Entwurf und Vertrag

**Anlass.** Der Abdruck des Vokabulars von 0.2.0 hat sich am 01.10. zweimal
bewegt (erster und zweiter Nachtrag), die Versionsnummer blieb. Das war
zulaessig, weil noch niemand 0.2.0 gezeichnet hatte. Geregelt war es nicht:
Die Ratsche im Test haelt den Abdruck gegen ein Literal, und wer das
Vokabular aendert und das Literal im selben Commit nachzieht, kommt durch
— vor wie nach einer Zeichnung.

**Gemessen.** Eine Aenderung nach der Zeichnung blieb nicht unbemerkt: Der
lebende Stand von A-O1 traegt den Hash des Moduls, der Verweis auf die
fruehere Abnahme scheitert, der naechste Fall braucht eine neue Abnahme.
Die Luecke lag im Schritt danach: Diese neue Abnahme durfte denselben
Uebergang 0.1.0 -> 0.2.0 mit einem anderen Vokabular zeichnen. Eine A-Box,
die 0.2.0 nach dem ersten Vokabular erklaert, bestand danach weiter den
Versionsvergleich in P-Q3.

**Regel.** Vor der ersten A-O1-Zeichnung ist eine Version ein Entwurf, nach
ihr ein Vertrag: Innerhalb einer abgenommenen Version gibt es genau ein
Vokabular; jede weitere Aenderung hebt die Version.

**Gebaut.**

* `gates.stand_belegen.tbox_vokabular_fehler` ist die eine Regel fuer
  Produzent und Gate. Fuehrt irgendeine Annahme in der A-O1-Kette des Falls
  oder der Linie die Version des Codes mit einem anderen Abdruck, wird
  verweigert, mit dem Ausweg "Version heben". Derselbe Abdruck bleibt
  zulaessig (das Modul hat sich bewegt, das Vokabular nicht). Jede Annahme
  der Kette zaehlt, nicht nur die geltende Spitze: Auch eine spaeter
  abgeloeste Annahme war eine Zeichnung.
* Der lebende Stand von A-O1 traegt drei Felder: `version`, `tbox_sha256`,
  `vokabular_sha256`. Der Abdruck steht damit im signierten Snapshot jeder
  Abnahme, und das Gate rechnet die Regel aus den Ketten und dem lebenden
  Code; dem Feld `vorher` des Belegs glaubt es dafuer nichts.
* `stand_belegen tbox --fall` verlangt `--vorher-linie`: Ohne die Linie
  zeigte die Sicht im Fall "Erstabnahme", obwohl die Linie die T-Box schon
  abgenommen hat.
* Die Ratsche im Test nennt ihren Gueltigkeitsbereich: Nachziehen ist nur
  fuer einen ungezeichneten Entwurf zulaessig; eine Zeichnung sieht sie
  nicht.

**Verworfene Alternative.** *Codepflege ohne Zeichnung:* Bewegt sich nur der
Modul-Hash und nicht der Abdruck, koennte der Verweis weiter gelten. Nicht
gebaut: `ontologie/tbox.py` traegt neben dem Vokabular die Pruefregeln, die
P-Q3 und P-K1 ausfuehren (Validatoren, Pflichtmengen, Wertebereiche). Eine
geaenderte Pruefregel ginge so ungezeichnet durch, und zwar leise, weil das
Vokabular beweislich unveraendert ist. Der Verweis haelt deshalb weiter
alle drei Felder mit `==`; ein Kommentar in dem Modul kostet nach der
Zeichnung eine Abnahme, deren Sicht "keine Aenderung am Vokabular" sagt.
Entscheidbar wird die Lockerung erst mit einem Register der oeffentlichen
Namen des Moduls, zweiklassig (Vokabular oder Regel) und mit `==` gehalten.

**Benannte Grenzen.** Die Regel liest die Ketten strukturell, ohne
Signatur: Ein untergeschobener Snapshot kann nur verweigern, nichts
erlauben. Sie sieht die Bereiche, die sie bekommt (Fall und Linie), keine
fremden Faelle. Seit Pruefrunde G (G13) haelt auch A-M4 sie in der
Standabnahme gegen Fall UND die Linie, die A-M4 bekommt (ADR-025, Nachtrag
Pruefrunde G): Wer A-O1 unter einer Kopie der Linie ohne Entscheide
zeichnete, kam vorher bis zur Annahme der Migration. Die Vergleichsgrundlage der Sicht (`vorher`) liefert der
Produzent; das Gate prueft an ihr nur die innere Stimmigkeit.

## Nachtrag 2026-10-01 (vierter): Pruefrunde G — Feststellung statt Luecke, Scope, Belege an der Spez

**Anlass.** Die blinde Pruefrunde G fand in diesem Bereich sieben bestaetigte
Funde (G03, G04, G18 bis G22). Die Regel des zweiten Nachtrags ("was die
Quellpruefung durchlaesst, rechnet die Strecke, und umgekehrt") galt nur in
einer Richtung, und A-M4 las die Regelangaben der Belege nicht. Gebaut ist je
Fund ein roter Test, der Fix an einer Stelle, eine Ratsche und eine
Mutationsprobe (Stand: "Fix gebaut", nicht "geschlossen").

**1. "Nicht belegt" ist in der Spez ausdruecklich (G18, G19).**
Regel: Der Block `quellverfahren` fuehrt den Dynamiksatz immer, als Zahl oder
als Feststellung `"nicht_belegt"` (`spez.tarifregeln.NICHT_BELEGT`, das Wort
des A-Box-Zustands `Zustand.NICHT_BELEGT`). Die Feststellung ist nur fuer ein
Merkmal aus `tbox.BESTAND_ERHOBEN` ein Wert; fuer ein Pflichtmerkmal ist sie
eine Luecke. Ein fehlender Schluessel heisst "nie erhoben":
`tarifregeln_der_spez` ruft `tbox.tarifregeln_luecken` jetzt mit `erhoben` und
verweigert ihn wie P-Q3. Die eine Projektion `spez.tarifregeln.spez_block`
nehmen `spez.erzeugen`, P-K1 (`validate_spez`, beide Richtungen) und der
Fixture-Weg `ergaenze_tarifregeln` (Eintrag `{"zustand": "nicht_belegt",
"fundstelle": ...}`; Weglassen, `wert: null`, ein Eintrag ohne Wert und
Zustand werden benannt verweigert). Die Belege der Laeufe nennen die
Feststellung (`quellverfahren.erhoehungssatz = "nicht_belegt"`).
Grund: Vorher war die Spez von "ausdruecklich nicht belegt" und "nie
erhoben" bytegleich; die Unterscheidung lebte nur in P-Q3, und die
Uebernahme zerlegte bei nie erhobenem Satz still aus dem Beitrag
(gemessen: Scheibe 3799,60 statt 3800,00).
Verworfen: *`null` als Feststellung* — die Spez speichert ohne `None`
(`exclude_none`), `Wert` kennt kein `None`, und `null` war schon die Lesart
von "fehlt". *Ein eigenes Feld `nicht_belegt: [...]` im Spez-Schema* — eine
zweite Stelle fuer denselben Block, Schema-Version heben und jede
eingefrorene Spez neu erzeugen, fuer ein Merkmal. *`0.0` als Satz* — liegt
ausserhalb des Wertebereichs (0 < e < 1) und waere eine Behauptung ueber den
Tarif statt einer Feststellung ueber die Quelle.
Versionen: T-Box-Vokabular unveraendert (der Abdruck von 0.2.0 hat sich
nicht bewegt); Spez-Schema (`SPEZ_VERSION`) unveraendert, weil das Modell
gleich bleibt und nur die Pflicht der Bestandsstrecke schaerfer wird — wie im
zweiten Nachtrag. Eine Spez eines Bestandsfalls, die vor diesem Nachtrag aus
einer A-Box mit "nicht belegt" erzeugt wurde, wird verweigert; Ausweg: neu
erzeugen. Die eingefrorenen Baldrian-Spez fuehren den Satz belegt (0,05) und
bleiben bytegleich; die P-K1-/A-M4-Fixture erzeugt ihre Spez ueber den
Produzenten und traegt die Feststellung jetzt von selbst.

**2. Die Bestandsstrecke rechnet nur im Scope bestand (G18).**
Regel: Die fuenf Kommandos beziehen die Regeln ueber EINE Tuer,
`gates.migrationssuite_lauf.tarifregeln_des_falls(fall, spez)`: Scope des
Falls `bestand` (sonst Verweigerung, Exit 2, mit Ausweg), dann
`tarifregeln_der_spez`. A-M4 bezieht sein Soll ueber dieselbe Tuer.
Grund: Punkt 2 des zweiten Nachtrags ("ein Tariffall fuehrt keinen Bestand,
keine seiner Rechnungen liest die Bloecke") war nur behauptet; gemessen lief
die ganze Strecke im Scope tarif mit Exit 0.
Verworfen: *die Pruefung in `spez.tarifregeln`* — die Schicht `spez` kennt
keinen Fall (neue Kante `spez -> fall`, eine Architekturentscheidung);
*jedes Kommando liest den Scope selbst* — fuenf Abschriften, die sechste
vergisst sie; *ein Schalter, der die Pruefung abschaltet* — nicht gebaut.
Benannte Grenze: P-B1 (`gates.bestand_validate`) und die Fortschreibung
(`bestand.cli_fortschreibung`) lesen die Config, nicht die Spez, und kennen
keinen Fall; sie liegen ausserhalb dieser Regel. An die Regeln der Spez sind
sie ueber die Config-Wache des Fuehrungswerts (Punkt 3) und die
Fuehrungsprobe gebunden.

**3. Die Wache des Fuehrungswerts haelt die Generation, mit der bewertet wird (G20).**
Regel: `bestand.migrationszugang.fuehrungswerte` loest jede Generation, die
im Bestand vorkommt, so auf wie die Bewertung (Name aus
`stamm.tarif_generation`); ihr Knoten muss unter den Knoten der Spez stehen
und ihr Tarifwerk genau das der Spez sein.
Grund: Die Wache suchte ueber den Knoten, bewertet wurde ueber den Namen;
mit einer Attrappe unter dem Knoten der Spez stellte die Suite einen
Fuehrungswert nach anderem Tarifwerk gruen aus (7 Policen, z. B. RKW
154.012,66 statt 153.702,08).
Verworfen: *die Bewertung auf Knoten umstellen* — der Name ist der Schluessel
des Bestands und der Bestandsfuehrung; die Fuehrung haette einen anderen
Rechenweg bekommen. Benannte Grenze: Die Bewertung loest an mehreren Stellen
inline ueber den Namen auf; die Wache nimmt denselben Schluessel, einen
gemeinsamen Helfer gibt es nicht.

**4. A-M4 rechnet den Fuehrungswert nach und weist ihn aus (G03; ADR-022).**
Regel: `abnahmebericht._bestands_suite_fehler` (Bericht und Entscheid rufen
dieselbe Funktion; der Parameter `fall` hat keinen Standardwert) rechnet den
Fuehrungswert der Suite ueber `migrationssuite_lauf.fuehrungswert_rechnen` —
denselben Weg wie die Produzentin — auf den GEBUNDENEN Bytes nach: Bestand
(`bestand_sha256`), jede Nebentabelle neben ihm (liegt sie dort, muss sie
gebunden sein, und umgekehrt), Config (`config_sha256`), Stichtage der Suite,
Tarifwerk der Spez, die A-M4 bindet. Abweichung in Konvention, Policenmenge
oder einem Feld eines Termins verweigert. Die Vorlage weist ihn aus:
Summary `fuehrungswert` (Art, Konvention, Bindungen, je Stichtag Anzahl in
Kraft und nicht in Kraft und Summen) und im HTML je Vertrag. Abnahmebericht
10.0.0.
Verworfen: *Auftrags-Echo der ganzen Suite und Neulauf in A-M4* (wie beim
aktuariellen Test) — fuer den Fuehrungswert genuegen die gebundenen
Eingaben; der Neulauf der ganzen Suite bleibt der offene Punkt der
AT-Schicht. *Nur ausweisen, nicht nachrechnen* — dann pinnte A-M4 weiter ein
ungeprueftes Soll der Zugangsprobe.

**5. Jeder Beleg nennt genau die Regeln der Spez, die A-M4 bindet (G04).**
Regel: A-M4 bindet die Spez der Generation, die die Suite nennt (Summary
`tarifregeln`: Pfad, SHA-256, Regeln). EINE Vergleichsfunktion
(`abnahmebericht.tarifregeln_beleg_fehler`) haelt jeden Beleg aus
`TARIFREGEL_BELEGE`: Uebernahmebeleg, Schichtbeleg, die drei Belege des
aktuariellen Tests, Suite, Fuehrungsprobe (gemessen, Ratsche mit `==`). Der
Beleg muss genau diese Regeln nennen und genau diese Spez gelesen haben
(Schluessel und Hash unter seinen Eingaben); ohne Regelangabe wird er
verweigert.
Grund: A-M4 las die Regelangaben nicht; eine Suite mit anderen Regeln als
aktuarieller Test und Probe wurde gepinnt, und ein alter Beleg auf einer
frueheren Spez blieb unbemerkt.
Verworfen: *die Belege nur untereinander vergleichen* — eine in sich
stimmige Faelschung aller Belege kaeme durch, und die Spez ist die belegte
Fassung, nicht die Mehrheit der Belege.
Benannte Grenzen: Die Generation, an der die Spez haengt, nennt die Suite;
gehalten wird sie durch den Vergleich mit jedem Beleg, auch der
nachgerechneten Probe. Schichtbeleg und aktuarieller Test werden an ihrem
Standardort gelesen; ein Beleg unter einem anderen `--out` ist fuer A-M4
unsichtbar (wie bei der Pflichtschicht). Das Feld `tarifwerk` der Probe auf
oberster Ebene haelt die Nachrechnung der Probe, nicht die
Vergleichsfunktion.
Nachbarfall: `betrieb.uebernahme.tarifwerk_fehler` verglich nur die
Schluessel, die der Uebernahmebeleg nennt; ein leeres oder halbes Tarifwerk
ging durch. Jetzt Gleichheit ueber alle Merkmale beider Seiten.

**6. Meldungen und Tarifplan (G21, G22).** Die Meldung bei einer
unterbestimmten Serie nennt `quellverfahren.erhoehungssatz` und den Weg ueber
A-Box, P-Q3 und Spez statt des entfallenen Schalters; eine Ratsche haelt, dass
kein Text in `src` (ausser Docstrings) einen Schalter aus
`ENTFALLENE_SCHALTER` nennt, ausser `spez/tarifregeln.py`. Der erzeugte
Tarifplan nennt im "Tarifwerk der Generation" jedes Merkmal aus
`tarifwerk()` (Text je Merkmal in `bestand.tarifplan_tabellen.TARIFWERK_TEXTE`,
gegen `tbox.TARIFWERK_MERKMALE` mit `==`); der Block in `klv.md` ist ueber den
Generator neu erzeugt.

Instrumente: `tests/test_am4_fuehrungswert_und_tarifregeln.py` (eigene,
abnahmereife Kette des zweiten Laufs, A-M4 ueber das Kommando),
`tests/test_tarifregeln_aus_spez.py` (Abschnitte Pruefrunde G).

## Nachtrag 2026-10-01 (fuenfter): Pruefrunde H — Regel der Hebung, Engines ohne Vorgabe

**1. Regel der Hebung (H13).** Eine Hebung darf nur tragen, was im alten
Artefakt steht; wo sie unterscheiden muesste, was dort nicht unterschieden
war, ist die benannte Verweigerung die ehrliche Antwort.
Regel: `spez.validierung._hebe_spez_0_1_0_auf_0_2_0` verweigert
(`SpezHebungFehler`) eine Datei, die sich T-Box 0.1.0 nennt und einen
Schluessel aus dem Vokabular von 0.2.0 traegt (`tarifwerk`, `quellverfahren`,
`urteil.geaenderte_tarifwerksmerkmale`, auch leer): Sie ist keine
0.1.0-Datei. Ausweg: die Regeln ueber die A-Box bringen (P-Q3,
`spez.erzeugen`) oder fuer eine Spez ohne A-Box die Bloecke entfernen, heben
und die Feststellung mit Fundstelle eintragen (`ergaenze_tarifregeln`).
Dieselbe Bauform hatte die Hebung der A-Box (`ontologie.abox`, Regel 0.1.0 ->
0.2.0): Eine 0.1.0-A-Box mit Aussagen in einem Block von 0.2.0 wurde
mitgehoben (gemessen: alle acht Tarifregel-Aussagen eines Falls), entgegen
ihrer Zusage "leere Bloecke"; sie wird jetzt ebenso verweigert (Ausweg:
Neu-Merge aus den Fragmenten).
Grund: Die Hebung der Spez trug Tarifregeln ohne Fundstelle und ohne A-Box in
eine geltende Spez, die jedes Kommando der Bestandsstrecke annahm, und
versperrte danach den Weg ueber die Feststellung ("bereits Tarifregeln").
Verworfen: *die Bloecke bei der Hebung leeren* — die Hebung verwuerfe still
Inhalt einer Datei, statt zu sagen, dass die Datei nicht ist, was sie
vorgibt.
Dieselbe Regel erklaert, warum es fuer die Schaerfung des vierten Nachtrags
("nicht belegt" muss ausdruecklich sein) KEINE Hebung gibt: Sie muesste
entscheiden, ob ein fehlender Dynamiksatz "nicht belegt" oder "nie erhoben"
hiess, und das steht in der alten Datei nicht. Die Antwort ist die benannte
Verweigerung an der Tuer (`spez.tarifregeln.tarifregeln_der_spez`, "nicht
erhoben") mit dem Weg ueber A-Box bzw. Feststellung.

**2. Der Lader nennt jeden Regelwert (bekannter Punkt a).** Regel: Der eine
Lader (`spez.validierung.lade_spez_aus_bytes`) haelt jeden Wert der Bloecke
`tarifwerk` und `quellverfahren` gegen den Wertebereich der T-Box
(`regelwert_befunde`, dieselbe typstrenge Regel wie
`tarifregeln_der_spez`) und verweigert (`SpezRegelwertFehler`) mit Merkmal,
erlaubtem Bereich und Ausweg (Spez neu erzeugen; "nicht_belegt" ist die
ausdrueckliche Feststellung). Grund: Ein Dynamiksatz `null` endete in einem
rohen Pydantic-Fehler ohne Ausweg, und ein Wert ausserhalb des Bereichs ging
durch den Lader und fiel erst an der Tuer der Bestandsstrecke — im Scope
`tarif` nie.

**3. Die Engines tragen keine Vorgabe fuer eine Tarifregel (H12).** Regel:
In `qa.migrationssuite` und `qa.aktuarieller_test` hat kein Argument und
kein Feld eines Pruefauftrags, das eine Tarifregel traegt (Merkmale aus
`tbox.TARIFWERK_MERKMALE` und dem Quellverfahren, dazu `dk_am_jahrestag`),
eine Vorgabe (18 Stellen, Ratsche mit `==`); die Felder der Pruefauftraege
sind Pflicht nur als Schluesselwort. Der einzige Weg zu den belegten Regeln
sind die Kommandos (`gates.migrationssuite_lauf`, `gates.aktuartest_lauf`),
die sie aus der Spez nennen; die Skills beschreiben genau diesen Weg.
Grund: Der Skill des Migrationscontrollings beschrieb "Auftraege selbst
bauen, `pruefe_bestand` rufen"; das lief ohne Fehler mit der Regel des
eigenen Geschaefts (2 von 29 statt 29 von 29 bestanden), und A-M4
verweigerte den Beleg erst am Ende.
Benannte Grenze: Weitere Funktionen mit einer Vorgabe fuer eine Tarifregel
stehen ausserhalb der beiden Engines (gemessen: 6 in `gates/`, 8 in
`bestand/`, 5 in `kern/`); jede Aufrufstelle in den Kommandos setzt die
Regel ausdruecklich.

Instrumente: `tests/test_spez_hebung_und_regelwerte.py`,
`tests/test_engine_tarifregel_ohne_vorgabe.py`,
`tests/test_dokumentierte_kommandos.py` (jedes woertliche Kommando der Skills
und Dokumente besteht den Parser seines Moduls, H14).
