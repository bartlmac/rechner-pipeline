# ADR-024: T-Box 0.2.0 — Tarifwerk, Geschäftsvorfälle, Zustandsextrakt

**Status:** angenommen am 2026-10-01 (Maintainer). Vorgeschlagen und als
Entwurf gebaut hat ihn der Architektur-Agent im Entwicklungsauftrag des
Maintainers; der Maintainer hat Vorschlag und Diffs durchgesehen und die
Umsetzung freigegeben. Die Abnahme der T-Box selbst ist ein Akt der Rolle
`mensch/architektur` (`A-O1.tbox-aenderung`, mit Änderungsbeleg und
Stellungnahme des Aktuariats). Seit ADR-025 geschieht sie bei der
Erstabnahme der Linie; dieses ADR ist das Artefakt ihres Belegs
(`deploy/welt/welt_aufstellen.sh`).

## Kontext

Die T-Box stand seit ihrer Einführung auf `0.1.0`. Der Mechanismus für
einen Übergang (Prüfung des Vorgängers in der Versionslinie, Beleg
`abgeleitet/tbox/aenderung.json`, `A-O1`) war gebaut, aber nie gelaufen.
In derselben Zeit hatten Kern und Bestandsführung aufgebaut, was ein
übernommener KLV-Bestand braucht: das Tarifwerk je Generation
(Erhöhungsscheiben mit $\gamma_1$, Stornoabzug je Baustein, Verfahren der
Herabsetzung), elf Geschäftsvorfälle mit Betragsarten, die Teilkündigung
als eigenen Vorgang (ADR-023), Verankerung, Erhöhungsscheiben und
Herabsetzungen als Zustandsextrakt (Grundsatzdokumentation 9.12, 9.14) und
die BU als zweite Produktfamilie. Die T-Box kannte davon nichts. Das
Tarifwerk einer übernommenen Generation erreichte die Prüfstrecke als
Schalter am Aufruf (`--red-verfahren`, `--stoab-je-baustein`,
`--scheiben-mit-gamma1`), ohne Herkunft. Die Zielfelder eines
Bestandsabzugs standen als Konstante in `ontologie.transformation`,
außerhalb der T-Box und ihrer Version.

## Entscheidung

1. **Version 0.2.0**, an die Linie angehängt: `TBOX_VERSIONEN =
   ("0.1.0", "0.2.0")`. Der Übergang ist rein additiv.
2. **Tarifwerk und Quellverfahren** sind belegte Aussagen der A-Box für
   die ganze Generation (`Tarifgeneration.tarifwerk`, `.quellverfahren`),
   mit Wertebereich, Merge, Diskrepanz am Knoten `<generation>/<block>`,
   Kettenprüfung, Coverage, Spez-Projektion und `P-K1` in beiden
   Richtungen. Die Namen sind die der Bestand-Config. In 0.2.0 werden sie
   ausgewiesen, nicht blockierend.
3. **Katalog-Vokabular** (Geschäftsvorfälle, Vertragsstatus, Vertragsfelder
   einer Lieferung, rechnende Vorgänge der Vorgeschichte, Zustandsextrakt,
   Formfunktionen, Produktfamilien mit Zuständen und Rechnungsgrundlagen)
   steht in der T-Box als Spiegel der Konstanten des Codes. Ein Test hält
   jede Spiegelung mit `==`; die T-Box importiert die Konstanten nicht.
4. **Die BU ist Vokabular, nicht instanziierbar** (`ABOX_FAMILIEN =
   ("klv",)`).
5. **Abdruck des Vokabulars** (`vokabular_sha256`), je Version im Test
   festgehalten: Eine Änderung am Vokabular ohne Versionssprung ist rot.
6. **Hebung bestehender A-Boxen** über eine deklarierte Regel je Schritt
   der Linie (`ontologie.abox.HEBUNGEN`). Der Schritt 0.1.0 -> 0.2.0
   ändert nur die Version; Entscheidungen (aufgelöste Diskrepanzen) wandern
   unverändert mit.

## Verworfene Alternativen

* **Import statt Spiegel:** Das Vokabular wanderte still mit dem Code,
  ohne Versionssprung und ohne `A-O1`.
* **BU als instanziierbare Familie:** Die T-Box verspräche eine A-Box, die
  weder Extraktion noch Spez noch `P-K1` verarbeiten können.
* **BU gar nicht:** Der Katalog der Geschäftsvorfälle ließe sich nicht
  gegen das Bewegungskonto halten (`INV`, `REA`, Betragsarten der BU).
* **Tarifwerk sofort Pflicht:** Jeder Tariffall ohne Bedingungswerk als
  Quelle wäre in `P-Q3` rot. Die Pflicht gehört an den Scope `bestand` und
  an die Kommandos, die die Regeln lesen (zweiter Nachtrag).
* **Quellverfahren im Tarifwerk:** Beide tragen `red_verfahren`, meinen
  aber Verschiedenes: die Lesart der Lieferung gegen die künftige Führung.
* **Altform lesbar** (`P-Q3` akzeptiert jede Version der Linie): Der
  Versionsvergleich wäre wieder nur nominal.

## Folgen

* Jede bestehende A-Box ist unter 0.2.0 fremd (`P-Q3`, `P-K1`). Laufende
  Fälle heben ihre A-Box (die Entscheidungen bleiben) oder führen neu
  zusammen; danach werden die Prüf-Gates auf dem neuen Stand neu
  gezeichnet. Abgeschlossene Fälle bleiben auf ihrem Stand.
* Den Übergang 0.1.0 -> 0.2.0 zeichnet `A-O1`, seit ADR-025 bei der
  Erstabnahme der Linie.
* Die Fachspezifikation trägt einen Abschnitt 12 (Tarifwerk und Verfahren
  der Quelle).
* Das Extraktionsschema (`QuellFragment`) hat die Felder `tarifwerk` und
  `quellverfahren`; `nicht_belegt` nennt Merkmale eines Blocks mit dem
  Blocknamen (`tarifwerk.red_verfahren`).

## Nachträge

Die Nachträge sind in ihrer Reihenfolge adressiert (erster bis fünfter
Nachtrag), die Punkte darin mit ihrer Nummer. Die Herleitung im Einzelnen
steht in der Geschichte dieser Datei.

## Nachtrag 2026-10-01: vor der ersten Zeichnung ergänzt

Am selben Tag erweiterten die Entscheide zur Folge von Vorgängen (ADR-023,
Nachtrag 2026-10-01) das Tarifwerk um ein Merkmal. Weil noch niemand 0.2.0
gezeichnet hatte, wurde die Version ohne neue Nummer ergänzt und ihr
Abdruck neu gesetzt (`tests/test_tbox_erweiterung_020.py`):

* Merkmal `tku_umfang` mit dem Wertebereich `TKU_UMFAENGE` =
  (`alle_bausteine`, `grundversicherung`): welche Bausteine eine
  Teilkündigung kürzt (Tarifplan KLV 7.2). Spiegel von
  `kern.vorgangsfolge.TKU_UMFAENGE` und der Schlüssel von
  `bestand.config.TarifGeneration.tarifwerk()`.
* Vorgabe des eigenen Geschäfts: `tku_umfang = alle_bausteine`.
* Lesart des Quellverfahrens (Beschreibung, nicht Vokabular): Ab der
  Migration gilt das Vokabular des Zielsystems (Grundsatzdokumentation
  7.1). `teilkuendigung` heißt „der Tarif kennt keine
  Beitragsherabsetzung“; eine gelieferte Absetzung danach und nach einer
  Beitragsfreistellung war eine Teilkündigung.

Befüllung, Spez-Projektion, Coverage und Fachspezifikation lesen die
Merkmale aus `GENERATIONS_BLOECKE` und tragen das neue Merkmal ohne eigene
Änderung.

## Nachtrag 2026-10-01 (zweiter): die nächste Stufe ist gebaut — die Kommandos lesen die Spez

Der Maintainer nahm den Vorschlag an, dass die Tarifregeln eines
übernommenen Tarifs bei einer Bestandsmigration in der A-Box stehen, belegt
aus dem Bedingungswerk, und dass die Kommandos sie von dort lesen statt aus
Schaltern. Er ergänzte, auch die übrigen Regeln nachzuziehen: „kein
Schalter von Hand, sondern Tabelle“.

**Invariante.** Die Regeln eines Tarifs stehen einmal und belegt (A-Box ->
Spez), und jedes Kommando der Bestandsstrecke rechnet mit genau dieser
Fassung. Kein Kommando rechnet mit einer Vorgabe, die niemand belegt hat.

1. *Pflicht im Scope `bestand`.* `tbox.BESTAND_PFLICHT` umfasst das ganze
   Tarifwerk und im Quellverfahren `red_verfahren`, `dk_stichtag` und
   `formfunktion`; `tbox.BESTAND_ERHOBEN` umfasst `erhoehungssatz` (belegt
   oder ausdrücklich `nicht_belegt`). Das Fenster folgt der Formfunktion.
   Eine Regel, `tbox.tarifregeln_luecken`, gilt für `P-Q3` und die
   Kommandos. `P-Q3` (2.0.0) verweigert im Scope `bestand` mit Code
   `tarifregeln` und Ausweg; die Coverage weist das Urteil je Generation
   aus (`tarifregeln_bestand`), unabhängig vom Scope.
2. *Die Grenze.* Im Scope `tarif` bleibt der Block ausgewiesen, nicht
   blockierend: Ein Tariffall führt keinen Bestand, und eine Tarifmeldung
   ohne Bedingungswerk wäre sonst rot, ohne dass etwas falsch gerechnet
   würde. Die Pflicht gehört dorthin, wo die Regel rechnet.
3. *Quellverfahren erweitert* (vor der ersten Zeichnung, ohne neue
   Version, Abdruck neu gesetzt): `erhoehungssatz` (Zahl, 0 < e < 1),
   `dk_stichtag` (`kalendertag`, `jahrestag`), `formfunktion`
   (`tbox.FORMFUNKTIONEN`), `fenster` (ganze Zahl >= 1). Zahlbereiche sind
   `tbox.Zahlbereich`, so typstreng wie die Aufzählungen.
4. *Ein Zugang.* `spez.tarifregeln.tarifregeln_der_spez` liefert die Regeln
   aus der Spez, gelesen über den einen Lader, oder verweigert
   (`TarifregelnFehler`, mit Ausweg). Übernahme, Verankerung, aktuarieller
   Test, Migrationscontrolling und Führungsprobe beziehen sie dort;
   `--generation-spez` ist an der Übernahme Pflicht.
5. *Die Schalter entfallen.* `--red-verfahren`, `--stoab-je-baustein`,
   `--scheiben-mit-gamma1`, `--tku-umfang`, `--erhoehungssatz`,
   `--dk-stichtag`, `--formfunktion` und `--fenster` werden an allen fünf
   Kommandos mit Meldung verweigert (Exit 2, mit dem Abschnitt der Spez),
   nicht mit dem nackten Fehler von argparse: Wer einen davon aus einer
   alten Notiz tippt, erfährt, wo die Regel jetzt steht.
6. *Abgegrenzt.* Das Tarifwerk ist Regel des Tarifs (Führung). Das
   Quellverfahren ist Eigenschaft der Quelle bzw. der Migration: Lesart der
   Lieferung, Dynamiksatz, Stichtag des gelieferten Deckungskapitals,
   Ausgestaltung der Korrekturschicht (Grundsatzdokumentation 10 Nr. 9).
   `--red-anteil-kandidat` ist eine Arbeitsannahme des Laufs und bleibt
   Schalter; registrierte Eingaben bleiben Schalter mit Dateinamen
   (`--red-anteile-datei`, `--anker-erwartungswerte`,
   `--plausibilitaet-*`).
7. *Gefunden beim Bau.* Der Umfang der Teilkündigung erreichte die
   Prüfaufträge von aktuariellem Test und Migrationscontrolling nie
   (`--tku-umfang` wirkte nur auf den Anfangszustand); jetzt geht er in
   jeden Auftrag. Das Migrationscontrolling verweigert eine Config, deren
   Tarifwerk nicht das der Spez ist
   (`bestand.migrationszugang.fuehrungswerte`).
8. *Belege.* Übernahmebeleg, Schichtbeleg, aktuarieller Test, Suite und
   Führungsprobe nennen die Regeln, mit denen sie gerechnet haben
   (`tarifregeln` bzw. `tarifwerk`/`quellverfahren`). Die Führungsprobe
   trägt Fassung 5; `A-M4` nimmt Fassung 4 nicht mehr an.

**Verworfen:**
* Schalter als Übersteuerung der Spez: Ein Schalter, der die belegte Regel
  überstimmen kann, ist wieder Zweitwissen, und der Aufruf hätte das letzte
  Wort über einen Beleg.
* „PLV-Regel, wenn nichts belegt ist“: Das ist der stille Default, an dem
  im zweiten Lauf die Regel des übernommenen Tarifs erst in `A-M3`
  auffiel.
* Formfunktion und Fenster in einem eigenen Block `migration`: semantisch
  sauberer, kostet aber ein weiteres Feld in vier Modellen für zwei
  Merkmale. Der eigene Block bleibt die Alternative, wenn die
  Korrekturschicht mehr Merkmale bekommt.
* `--red-anteil-kandidat` in die Spez: Die Kandidatenmenge ist eine
  Arbeitsannahme des Laufs, keine Regel des Tarifs.

**Fixtures.** Die eingefrorenen Spez der Baldrian-Läufe haben keine A-Box.
Ihre Regeln kommen über `spez.validierung.ergaenze_tarifregeln` aus dem
Dokument der Feststellung (`tests/fixtures/<lauf>/tarifregeln.json`, je
Merkmal mit Fundstelle). Die Fixture für `P-K1` und `A-M4` liefert die
Regeln im Scope `bestand` über ihren Produzenten (`tests/e2e_fixture.py`).

## Nachtrag 2026-10-01 (dritter): eine Version, ein Vokabular — Entwurf und Vertrag

Der Abdruck des Vokabulars von 0.2.0 hatte sich zweimal bewegt, die
Versionsnummer blieb. Das war zulässig, weil noch niemand 0.2.0 gezeichnet
hatte, aber nicht geregelt: Wer nach einer Zeichnung das Vokabular änderte
und das Literal im Test im selben Commit nachzog, kam durch. Zwar scheitert
dann der Verweis auf die frühere Abnahme, doch die neue Abnahme durfte
denselben Übergang 0.1.0 -> 0.2.0 mit einem anderen Vokabular zeichnen.

**Regel.** Vor der ersten A-O1-Zeichnung ist eine Version ein Entwurf,
danach ein Vertrag: Innerhalb einer abgenommenen Version gibt es genau ein
Vokabular, und jede weitere Änderung hebt die Version.

* `gates.stand_belegen.tbox_vokabular_fehler` ist die eine Regel für
  Produzent und Gate. Führt irgendeine Annahme in der A-O1-Kette des Falls
  oder der Linie die Version des Codes mit einem anderen Abdruck, wird mit
  dem Ausweg „Version heben“ verweigert. Jede Annahme der Kette zählt, auch
  eine später abgelöste.
* Der lebende Stand von `A-O1` trägt drei Felder: `version`,
  `tbox_sha256` und `vokabular_sha256`. Der Abdruck steht damit im
  signierten Snapshot jeder Abnahme, und das Gate rechnet die Regel aus den
  Ketten und dem lebenden Code.
* `stand_belegen tbox --fall` verlangt `--vorher-linie`, sonst zeigte die
  Sicht im Fall „Erstabnahme“, obwohl die Linie die T-Box schon abgenommen
  hat.

**Verworfen:** Codepflege ohne Zeichnung, also den Verweis gelten lassen,
wenn sich nur der Hash des Moduls bewegt und nicht der Abdruck.
`ontologie/tbox.py` trägt neben dem Vokabular die Prüfregeln von `P-Q3` und
`P-K1`; eine geänderte Prüfregel ginge so ungezeichnet durch. Der Verweis
hält deshalb alle drei Felder mit `==`. Lockern ließe sich das erst mit
einem Register der öffentlichen Namen des Moduls, getrennt nach Vokabular
und Regel.

**Grenzen.** Die Regel liest die Ketten strukturell, ohne Signatur; ein
untergeschobener Snapshot kann nur verweigern, nichts erlauben. Sie sieht
die Bereiche, die sie bekommt (Fall und Linie), keine fremden Fälle. Seit
Prüfrunde G hält auch `A-M4` sie gegen Fall und Linie (ADR-025, Nachtrag
Prüfrunde G). Die Vergleichsgrundlage der Sicht (`vorher`) rechnet das
Gate seit Prüfrunde H beim Zeichnen nach (ADR-025, zweiter Nachtrag zu Prüfrunde H, Punkt 2).

## Nachtrag 2026-10-01 (vierter): Prüfrunde G — Feststellung statt Lücke, Scope, Belege an der Spez

Die Prüfrunde G fand hier sieben Befunde (G03, G04, G18 bis G22). Die
Regel des zweiten Nachtrags galt nur in einer Richtung, und `A-M4` las die
Regelangaben der Belege nicht.

**1. „Nicht belegt“ ist in der Spez ausdrücklich (G18, G19).** Der Block
`quellverfahren` führt den Dynamiksatz immer, als Zahl oder als
Feststellung `"nicht_belegt"` (`spez.tarifregeln.NICHT_BELEGT`, das Wort
des A-Box-Zustands `Zustand.NICHT_BELEGT`). Die Feststellung ist nur für
ein Merkmal aus `tbox.BESTAND_ERHOBEN` ein Wert, für ein Pflichtmerkmal
eine Lücke. Ein fehlender Schlüssel heißt „nie erhoben“, und
`tarifregeln_der_spez` verweigert ihn wie `P-Q3`. Die eine Projektion
`spez.tarifregeln.spez_block` nutzen `spez.erzeugen`, `P-K1`
(`validate_spez`, beide Richtungen) und `ergaenze_tarifregeln`. Vorher waren
„ausdrücklich nicht belegt“ und „nie erhoben“ in der Spez bytegleich, und
die Übernahme zerlegte bei nie erhobenem Satz still aus dem Beitrag.
*Verworfen:* `null` als Feststellung (die Spez speichert ohne `None`, und
`null` war schon die Lesart von „fehlt“); ein eigenes Feld im
Spez-Schema; `0.0` als Satz (außerhalb des Wertebereichs und eine Aussage
über den Tarif statt über die Quelle). T-Box-Vokabular und Spez-Schema
bleiben unverändert. Eine ältere Spez eines Bestandsfalls mit „nicht
belegt“ wird verweigert; Ausweg: neu erzeugen.

**2. Die Bestandsstrecke rechnet nur im Scope `bestand` (G18).** Die fünf
Kommandos beziehen die Regeln über einen Zugang,
`gates.migrationssuite_lauf.tarifregeln_des_falls(fall, spez)`: Scope des
Falls `bestand` (sonst Verweigerung, Exit 2, mit Ausweg), dann
`tarifregeln_der_spez`. `A-M4` bezieht sein Soll über denselben Zugang.
Punkt 2 des zweiten Nachtrags war vorher nur behauptet; die ganze Strecke
lief im Scope `tarif` mit Exit 0. *Verworfen:* die Prüfung in
`spez.tarifregeln` (die Schicht `spez` kennt keinen Fall) und eine Prüfung
in jedem Kommando (der sechste Aufrufer vergäße sie). *Grenze:* `P-B1`
(`gates.bestand_validate`) und die Fortschreibung
(`bestand.cli_fortschreibung`) lesen die Config, nicht die Spez. An die
Regeln der Spez sind sie über die Config-Wache des Führungswerts (Punkt 3)
und die Führungsprobe gebunden.

**3. Die Wache des Führungswerts hält die Generation, mit der bewertet
wird (G20).** `bestand.migrationszugang.fuehrungswerte` löst jede
Generation des Bestands so auf wie die Bewertung (Name aus
`stamm.tarif_generation`); ihr Knoten muss unter den Knoten der Spez
stehen und ihr Tarifwerk genau das der Spez sein. Vorher suchte die Wache
über den Knoten, bewertet wurde über den Namen, und mit einer Attrappe unter
dem Knoten der Spez stellte die Suite einen Führungswert nach anderem
Tarifwerk grün aus. *Verworfen:* die Bewertung auf Knoten umzustellen; der
Name ist der Schlüssel von Bestand und Bestandsführung.

**4. `A-M4` rechnet den Führungswert nach und weist ihn aus (G03;
ADR-022).** `abnahmebericht._bestands_suite_fehler` rechnet den Führungswert
der Suite über `migrationssuite_lauf.fuehrungswert_rechnen`, denselben Weg
wie die Produzentin, auf den gebundenen Bytes nach: Bestand, jede
Nebentabelle neben ihm, Config, Stichtage der Suite und Tarifwerk der Spez,
die `A-M4` bindet. Eine Abweichung in Konvention, Policenmenge oder einem
Feld eines Termins wird verweigert. Die Vorlage weist den Führungswert in
der Zusammenfassung (`fuehrungswert`) und im HTML je Vertrag aus.
*Verworfen:* die ganze Suite in `A-M4` neu zu fahren, denn für den
Führungswert genügen die gebundenen Eingaben; und ihn nur auszuweisen,
denn dann pinnte `A-M4` ein ungeprüftes Soll der Zugangsprobe.

**5. Jeder Beleg nennt genau die Regeln der Spez, die `A-M4` bindet
(G04).** `A-M4` bindet die Spez der Generation, die die Suite nennt (Pfad,
SHA-256, Regeln). Eine Vergleichsfunktion
(`abnahmebericht.tarifregeln_beleg_fehler`) hält jeden Beleg aus
`TARIFREGEL_BELEGE`: Übernahmebeleg, Schichtbeleg, die drei Belege des
aktuariellen Tests, Suite und Führungsprobe. Jeder muss genau diese Regeln
nennen und genau diese Spez gelesen haben; ohne Regelangabe wird er
verweigert. *Verworfen:* die Belege nur untereinander zu vergleichen, denn
eine in sich stimmige Fälschung aller Belege käme durch. *Grenzen:*
Schichtbeleg und aktuarieller Test werden an ihrem Standardort gelesen;
ein Beleg unter einem anderen `--out` ist für `A-M4` unsichtbar. Im selben
Zug vergleicht `betrieb.uebernahme.tarifwerk_fehler` alle Merkmale beider
Seiten, nicht mehr nur die Schlüssel, die der Übernahmebeleg nennt.

**6. Meldungen und Tarifplan (G21, G22).** Die Meldung bei einer
unterbestimmten Serie nennt `quellverfahren.erhoehungssatz` und den Weg
über A-Box, `P-Q3` und Spez statt des entfallenen Schalters. Ein Test hält,
dass kein Text in `src` (außer Docstrings und `spez/tarifregeln.py`) einen
Schalter aus `ENTFALLENE_SCHALTER` nennt. Der erzeugte Tarifplan nennt im
„Tarifwerk der Generation“ jedes Merkmal aus `tarifwerk()` (Text je
Merkmal in `bestand.tarifplan_tabellen.TARIFWERK_TEXTE`, gehalten gegen
`tbox.TARIFWERK_MERKMALE`).

Tests: `tests/test_am4_fuehrungswert_und_tarifregeln.py`,
`tests/test_tarifregeln_aus_spez.py`.

## Nachtrag 2026-10-01 (fünfter): Prüfrunde H — Regel der Hebung, Engines ohne Vorgabe

**1. Regel der Hebung (H13).** Eine Hebung darf nur tragen, was im alten
Artefakt steht. Wo sie unterscheiden müsste, was dort nicht unterschieden
war, ist die benannte Verweigerung die ehrliche Antwort.
`spez.validierung._hebe_spez_0_1_0_auf_0_2_0` verweigert
(`SpezHebungFehler`) eine Datei, die sich T-Box 0.1.0 nennt und einen
Schlüssel aus dem Vokabular von 0.2.0 trägt (`tarifwerk`,
`quellverfahren`, `urteil.geaenderte_tarifwerksmerkmale`, auch leer). Sie
ist keine 0.1.0-Datei. Ausweg: die Regeln über die A-Box bringen (`P-Q3`,
`spez.erzeugen`) oder für eine Spez ohne A-Box die Blöcke entfernen, heben
und die Feststellung mit Fundstelle eintragen (`ergaenze_tarifregeln`).
Ebenso verweigert die Hebung der A-Box (`ontologie.abox`) eine 0.1.0-A-Box
mit Aussagen in einem Block von 0.2.0; Ausweg ist ein neuer Merge aus den
Fragmenten. *Verworfen:* die Blöcke bei der Hebung zu leeren; die Hebung
verwürfe still Inhalt, statt zu sagen, dass die Datei nicht ist, was sie
vorgibt. Aus derselben Regel gibt es für die Verschärfung im vierten
Nachtrag („nicht belegt“ muss ausdrücklich sein) keine Hebung: Sie müsste
entscheiden, ob ein fehlender Dynamiksatz „nicht belegt“ oder „nie
erhoben“ hieß, und das steht in der alten Datei nicht.

**2. Der Lader prüft jeden Regelwert.** Der eine Lader
(`spez.validierung.lade_spez_aus_bytes`) hält jeden Wert der Blöcke
`tarifwerk` und `quellverfahren` gegen den Wertebereich der T-Box
(`regelwert_befunde`, dieselbe typstrenge Regel wie
`tarifregeln_der_spez`) und verweigert (`SpezRegelwertFehler`) mit
Merkmal, erlaubtem Bereich und Ausweg. Vorher endete ein Dynamiksatz
`null` in einem rohen Pydantic-Fehler, und ein Wert außerhalb des Bereichs
fiel erst an der Bestandsstrecke auf, im Scope `tarif` nie.

**3. Die Engines tragen keine Vorgabe für eine Tarifregel (H12).** In
`qa.migrationssuite` und `qa.aktuarieller_test` hat kein Argument und kein
Feld eines Prüfauftrags, das eine Tarifregel trägt, eine Vorgabe; die
Felder der Prüfaufträge sind Pflicht, nur als Schlüsselwort zu übergeben.
Der einzige Weg zu den belegten Regeln sind die Kommandos
(`gates.migrationssuite_lauf`, `gates.aktuartest_lauf`), die sie aus der
Spez nennen. Vorher beschrieb der Skill des Migrationscontrollings, die
Aufträge selbst zu bauen; das lief ohne Fehler mit der Regel des eigenen
Geschäfts, und erst `A-M4` verweigerte den Beleg am Ende. In Prüfrunde I
(I14) zeigte sich dieselbe Lücke im Kern: Die Migrationssuite rief ihn für
die Scheibe einer Erhöhung zwischen den Stichtagen ohne die Regel auf und
rechnete still ohne $\gamma_1$. Seit Kern 3.20.0 hat in `kern/` und
`bestand/` keine Funktion mehr eine Vorgabe für eine Tarifregel, die ihre
Aufrufer kennen. Ausnahmen mit Grund hält `tests/test_runde_i_tarifregeln.py`
fest, darunter die Merkmale der Generation in der Bestand-Config, die die
Quelle des Tarifwerks der Führung ist.

Tests: `tests/test_spez_hebung_und_regelwerte.py`,
`tests/test_engine_tarifregel_ohne_vorgabe.py`.
