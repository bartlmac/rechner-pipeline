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
