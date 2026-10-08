# Vorzeigeseite: Backlog der Verbesserungen

Ideen und Vorhaben fuer den Unternehmensauftritt (vorzeige-seite/,
werkzeuge/), gesammelt vom Maintainer und der Seiten-Session. Ein
erledigter Punkt wird geloescht, nicht abgehakt. Was eine Zahl oder
Tabelle auf die Seite bringt, muss aus einem Artefakt oder dem Code
erzeugt werden — die Drift-Regel (werkzeuge/README.md) gilt fuer jeden
Punkt hier.

**Was der LAUF liefern muss, damit die Seite es zeigen kann** — je
Stelle Zielbild, Ist im Code, Lücke, Wirkung auf den Fall — steht seit
2026-09-22 in `vorzeige-zielbild-artefakte.md` (Übergabe an dev). Diese
Liste hier bleibt die der Seite selbst.

## Drift-Sicherung

| Punkt | Stand | Anmerkung |
|---|---|---|
| Seite "Unsere Pruefgates" darf dem Code nicht davonlaufen | GEBAUT 2026-09-07, Sicherung in drei Schichten | (1) `gates/register.py` ist die Lesefassung als Code; `tests/test_gates_register.py` bindet die Programmgates an die `GATE`-Konstanten der Module, die Abnahmen an `models.zeichnung.GUELTIGE_GATES` und die Vorgaenger von A-M4 an `fall.BELEGROLLEN` (neue Belegrolle ohne Zuordnung = harter Fehler). (2) `unternehmensseite.pruefgates()` erzeugt die Seite je Bau aus dem Register, kein Bau ohne Register. (3) `drift.py` vergleicht die veroeffentlichte Seite mit dem frischen Entwurf. OFFEN: Die Saetze je Gate (Spalte "Was geprueft wird") sind Prosa IM Register — sie driften nicht vom Code weg, aber vom Verhalten; wer ein Gate fachlich aendert, muss den Satz mitziehen. Ein Test dafuer gibt es nicht (Semantik gehoert in Skills, nicht in Wortlisten-Tests). |

## Aus dem Seitenkonzept (2026-09-08)

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| Fallbericht-Kopf in Unternehmensstimme | Seitenkonzept, offene Folgepunkte | Der Satz "Dies ist eine Vorfuehrung, kein echter Bestand" steht bytegleich mit ebenen (T19-02/T21-05). Nach dem Merge von main: Verifikationssatz behalten, Vorfuehrungssatz in die Fusszeile. |
| Pruefgates fachlich fuer Aktuare | Seitenkonzept | Die generierte Tabelle liegt unter it/; ob das Aktuariat eine fachliche Fassung (Toleranzen, Stichproben) braucht, entscheidet die naechste Sichtung. |
| Verlinkung mit der Codebasis | Maintainer, 2026-09-08 | Zurueckgestellt, bis die Struktur steht; danach: was die Seite BRAUCHT (nicht was das Repo hat) erzeugt und verlinkt. |

| Zwei Nummernkreise benennen (T24-08) | dev, 2026-09-15 | Ab dem naechsten Neuaufsetzen vergibt das Zielsystem eigene Policennummern (Baldrian: Band 1..1000 statt 7000001+). Dann sprechen die Tagesseite (Betrieb) in ZIEL-, die Fall-Artefakte (Snapshots, Lieferungs-Ansichten, Berichte) in QUELLnummern — beide liegen im selben Auftritt. Geplant: ein Satz an der Journey-Station "Zugang in die Buecher". NICHT vorher bauen: der Satz waere heute falsch. |

| Rentenzahlungen als eigene Groesse | Maintainer, 2026-09-17 | Die Leistungstabelle zeigt heute nur ausgezahlte Kapitalleistungen (Ablauf, Rueckkauf, Todesfall); bei Invalidisierung und Reaktivierung steht nur die Fallzahl, weil die BU-Jahresrente eine Zusage ist und keine Zahlung. Gebraucht wird spaeter die in der Periode AUSGEZAHLTE Rente — und die ist eine andere Dimension: Sie betrifft ALLE Leistungsbezieher des Zeitraums, nicht nur die in ihm neu invalidisierten. Also eine Stromgroesse ueber den Rentenbestand, nicht ueber die Vorfaelle der Periode. Braucht eine Buchung im Tagesjournal (dev) und auf der Vertiefungsseite einen erklaerenden Satz zu genau diesem Unterschied. NICHT bestellt: erst auf Zeichen des Maintainers an die dev-Session. |

## Ideen (Maintainer, gesammelt ab 2026-09-07)

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| Fallportfolio: mehrere Migrationen je Bau | Seiten-Session, 2026-09-07 | `html:migrationen_bloecke` baut heute aus EINEM falldaten-Modell einen Block; mit dem zweiten Fall braucht der Bau mehrere Modelle (auftritt.py --fall mehrfach) und die Summenzeile wird echt. |
| Bruttojahresbeitrag im Bestandsmodell | Maintainer, 2026-09-07 | Neuzugang (Neugeschaeft, Erhoehungen, Migrationen) soll den BJB zeigen; Stamm und Journal fuehren heute keinen Beitrag. Quelle waere der Kern (Beitrag je Vertrag) im Tagesjournal als eigene Betragsart. Bis dahin Platzhalter mit den gebuchten Summen daneben. |
| Dauer und Kosten je Migration | Maintainer, 2026-09-07 | Stunden des agentischen Systems aus dem Sitzungsprotokoll, Token-Kosten geschaetzt — braucht ein Artefakt im Fall (z. B. abgeleitet/aufwand.json aus dem Verlaufsprotokoll), sonst bleibt es Platzhalter. |
| Aktuelle Migration als Kasten | Maintainer, 2026-09-07 | "Baldrian Rentenversicherungen" ist Prosa-Platzhalter; sobald ein Fall im Modell den Status "laufend" traegt, den Kasten aus dem Modell erzeugen. |
| Ereigniszuordnung an EINER Stelle | dev, 2026-09-19 | ZUGANGSQUELLEN und LEISTUNGSARTEN in werkzeuge/unternehmensseite.py sind die abgenommene fachliche Menge (Zugang: ZUG, ERH; Leistung: ABL, STO, TOD, INV, REA). Sobald der Tagesbetrieb die Monatszahlen "zugaenge"/"leistungen" selbst rechnet, gaebe es sie zweimal — dieselbe Klasse wie A-B1 (eine Gate-Menge an sechs Stellen) und T26-11. Vereinbart: Umzug nach src/rechner_pipeline/models/bestand.py neben EREIGNIS_VALUES, Seite und Produzent lesen von dort, dazu ein Test, dass jede genannte Art in EREIGNIS_VALUES steht. AUSFUEHRUNG: offen, Entscheid des Maintainers. Die merge-session haelt die Reihenfolge-Verabredung ("wer zuerst auf main ist, zieht um") fuer zu schwach — eine Verabredung zwischen zwei Zweigen ist genau die Stelle, an der wir schon dreimal standen; ihr Vorschlag ist ein eigener kleiner Commit VORHER, aus keinem der beiden Zweige heraus, danach lesen beide dieselbe Quelle (dieselbe Bewegung wie bei ROLLEN_DATEIEN). Dagegen steht nichts Fachliches, nur die Zustaendigkeit: main bewegt der Maintainer, src/ gehoert der dev-Session. Also entweder als eigener Zweig zum Mergen oder durch dev beim Bau der Monatszahlen; die merge-session haelt dev fuer richtig (Datei liegt in src/, und wer die Menge als erster braucht, merkt beim Bauen, ob der Zuschnitt taugt), die Seite steuert die Menge und den fachlichen Grund bei. DER TEST IST DER WICHTIGERE TEIL: in beide Richtungen pruefen — jede genannte Art steht in EREIGNIS_VALUES, UND keine Art aus EREIGNIS_VALUES fehlt in beiden Mengen, ausser sie ist ausdruecklich ausgenommen (heute PEX, eine Beitragsfreistellung ist weder Zugang noch Leistung). Sonst faellt eine neue oder umbenannte Ereignisart erst auf der Seite auf. |
| Monatszeile: keine Gesamtspalte | dev, 2026-09-19 | Die Monatstabelle bekommt in_kraft, zugaenge, leistungen. PEX (Beitragsfreistellung) ist weder Zugang noch Leistung und faellt heraus; die Spalten summieren sich also nicht auf die Vorfaelle des Monats. Loesung ohne Erklaertext: KEINE Spalte "Vorfaelle gesamt" danebenstellen, dann entsteht die Frage nicht. Erlaeuternde Fussnoten hat der Maintainer zweimal als Technik gestrichen. |
| | | |

## Aus der Pruefrunde der Seite (Rueckmeldung 01.10., entschieden 04.10.2026)

| Punkt | Herkunft | Anmerkung |
|---|---|---|
| Gesamtuebersicht der Seiten | Pruefrunde, Punkt 1 | Eine Art Inhaltsverzeichnis, automatisch erzeugt. Geparkt, weil zu kurzfristig fuer den Versand der klickbaren Fassung. Vorschlag: der Bau erzeugt die Uebersicht aus dem gebauten Baum (Titel je Seite, nach Bereich), verlinkt im Kopf jeder Seite; nie von Hand. |
| A-Box und T-Box erklaeren, mit Beispielen | Pruefrunde, Punkt 4 | Eigene Seite. Ort offen: Thema der KI oder der IT, nicht an der Fallbeschreibung (Maintainer: dort riskant). Spaeter genauer besprechen. Beispiele beim Bau aus dem Fall ziehen, nicht abtippen. |
| Snapshots und Fuehrungsprobe erklaeren | Pruefrunde, Punkt 9 | Fuer Version 1 ausdruecklich in Ordnung. Je ein Satz, wo das Wort zuerst vorkommt. |
| Karte auf dem Telefon | Maintainer, 04.10. | Die PC-Sicht hat Vorrang. Heute verschiebt sich die Karte in ihrem Rahmen (Mindestbreite 860 px), die Seite bleibt bildschirmbreit. |
| Fachdokumente und Artefakte gesamthaft bereinigen | Maintainer, 04.10. | Die Seite spricht mit der Stimme des Unternehmens und weiss nichts von ihrer Herstellung. Die Tarifplaene KLV und BU und die Grundsatzdokumentation tragen noch Saetze dazu (Abschnitt 13: fiktives Unternehmen dieses Arbeitsraums; Aktuariat der Vorzeige; Simulationswerkzeug), die Snapshots und Belege des Falls ihre Freitexte. Dazu die Berichte: Die Bestandsberichte des Stands-Pakets (A-B1) und des Falls sprechen von simuliertem Neugeschaeft und Simulationshorizont, die Betriebssicht (plv/) zeigt Entscheider und Schluesselklasse; die Seite kopiert sie bytegleich. Die drei Dokumente sind gezeichneter Kernstand (A-K2, A-T1): bereinigen heisst neu zeichnen und Fall 3 neu festhalten. Gesamthaft angehen: die Artefakte bereinigen und an EINEM Ort erzeugen. Nicht vor dem Versand. |
| Chronologie der Fall-Daten | Nachpruefung der Seite, 04.10. | Der Kontrollstichtag des Migrationscontrollings (01.01.2027) liegt nach dem Stand der Seite (Oktober 2026), und alle Abnahmen tragen den 02.10.2026 fuer einen Zugang zum 01.01.2026. Auf der Seite nicht zu loesen: entweder in der Fall-Definition (Stichtage, Zeitpunkte) oder als Wirkungstag gegen Abnahmetag ausweisen. Mit der gesamthaften Bereinigung. |
| Faehigkeiten mit Anzeigenamen | Nachpruefung der Seite, 04.10. | Die KI-Seite nennt die Faehigkeiten mit ihren Kennungen (z. B. author-rechner-toolbox-gate). Deutsche Anzeigenamen je Faehigkeit, verankert wie SKILL_TITEL und SKILL_STAND. |
| Platzhalter `<welt>` | Nachpruefung der Seite, 04.10. | Der Platzhalter der Bereinigung fuer die Laufzeitumgebung heisst `<welt>`, ein Wort der Herstellung; besser `<laufzeit>`. Aenderung im Werkzeug der Bereinigung, Manifest und Tabelle ziehen mit. |
| Wache fuer die Unternehmensstimme | Seiten-Session, 04.10. | Vorschlag, nicht beschlossen: eine Wache wie die der Bereinigung, die die Seiten ausserhalb von Hinter den Kulissen auf Woerter der Herstellung prueft, mit Positivkontrolle. Die Pruefung vom 04.10. lief von Hand ueber sechs Leser und sechs Gegenleser. |

## Berichte: was heute steht und was nachzuziehen ist (2026-09-20)

Die Tabelle der Monatsberichte verlinkt dreizehn Dokumente: zwoelf
Monatsberichte und den Jahresbericht 2025.

DER MONATSBERICHT IST EIN EIGENES DOKUMENT, kein enger gestellter
Jahresbericht. Der erste Versuch war einer: Er gab dem grossen Renderer
ein Zwoelf-Monats-Stichtagsraster mit. Das Raster steuert dort aber nur
Bestandsverlauf, Statusverlauf und die Auswertungstabellen; Ereignis-
summen, Ereignis-Chart und Nachweisungen haengen nicht daran und zeigten
weiter die ganze Historie -- "Geschaeftsvorfaelle 1994 bis 2026" unter
einer Zwoelf-Monats-Kurve. Dazu kuerzen die Charts des grossen Berichts
jeden Stichtag auf sein Jahr, sodass die Achse zwoelf Jahreszahlen trug.
Der Maintainer hat den Bericht in dieser Form zurueckgewiesen, zu Recht.

Jetzt rendert src/rechner_pipeline/bestand/monatsbericht.py: Bestand am
Stichtag mit Vergleich zu Vormonat und Vorjahresmonat, Vertragskonto und
Geschaeftsvorfaelle des Berichtsmonats, zwoelf Monate Verlauf in drei
Grafiken und einer Tabelle, Bewegung ueber den ganzen Zeitraum. Aus dem
Zeitraum faellt nichts heraus. Der Tageslauf ruft ihn ueber
_monatsbericht(); _bericht() macht nur noch den Jahres- und den
Teilbestandsbericht.

ZWEI BEFUNDE aus dem Bau, die nicht am Renderer haengen:

1. Die Bestandszahlen kommen aus den FESTGESCHRIEBENEN Abschluessen, nicht
   aus einer Nachrechnung. Nachgerechnet auf der heutigen Stichtagssicht
   ergab der 1.1.2026 2.530 Vertraege, der Abschluss dieses Tages fuehrt
   2.531, und die Unternehmensseite weist die 2.531 aus. Ein Bericht, der
   seiner eigenen Verlinkung widerspricht, ist kein Beleg (T24-02).

2. Bestandszaehlung und Vorfallzaehlung haben verschiedene Zeitachsen, und
   das ist richtig: Ein Ablauf tritt zum vereinbarten Tag ein, ob gebucht
   oder nicht; ein Storno wird gemeldet und wirkt in den Buechern erst mit
   der Buchung. Faellt ein Monatserster auf ein Wochenende, wirken die
   Ablaeufe am Samstag und werden am Montag gebucht -- im August 2026 drei
   Vertraege, die im Abschluss des einen Monats fehlen und im Journal des
   naechsten stehen. Das Vertragskonto gleicht deshalb die beiden
   Abschluesse ab statt Buchungen zu zaehlen; dann schliesst es per
   Konstruktion. tests/test_bestand_monatsbericht.py faehrt genau diesen
   Wochenendfall.

ERLEDIGT AM 2026-09-20, ABENDS: Die dev-Session hat A-M4 gezeichnet
(Snapshot 2cc6e28f..., Fall baldrian-klv-tg2015-lauf2, Systemstand
17091b3). Damit war der regulaere Weg wieder frei, und er ist gefahren:
Neuaufsetzen gegen den gezeichneten Fall, Tagesläufe bis heute (11507
Tage nachgeholt, 387 Monatsabschluesse), Paket-Export, Seitenbau. Die
Wache ist gruen, der Stand uebernommen.

Die dreizehn Berichte entstehen damit im Tageslauf, stehen mit Hash in
stand.json und liegen im geprueften Paket. Die Unternehmensseite
verlinkt sie unter plv/berichte/. Der Umweg von gestern — Berichte aus
dem Stand gerendert und NEBEN das Paket gelegt, gefunden ueber die
Konstante BERICHTE_AUS_DEM_STAND — ist damit ueberfluessig und aus
werkzeuge/unternehmensseite.py entfernt. Ein Ausweichpfad, den niemand
mehr braucht, ist kein Sicherheitsnetz, sondern eine zweite Wahrheit.

ZWEI UNTERSCHIEDE ZUM STAND VON GESTERN, beide gewollt:

* Zwoelf PEX-Buchungen haben sich im Betrag geaendert, vier davon
  verschieben den gebuchten Cent (Fix 9e9ca7e, Uebernahme bucht den
  PEX-Zuschlag). Die Zahlen der Seite bewegen sich entsprechend: 2.543
  statt 2.550 Vertraege in Kraft zum 01.09.2026.
* Der Lauf lief lokal, nicht im Container; der Image-Digest fehlt
  deshalb im Protokoll. Der Seitenbau weist das als LUECKE aus und sagt
  "so nicht veroeffentlichen" — richtig so. Vor dem Seiten-PR muss der
  Lauf einmal in der Laufzeitumgebung gefahren werden, damit der Digest
  im Protokoll steht.
