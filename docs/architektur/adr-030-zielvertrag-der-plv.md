# ADR-030: Der Zielvertrag zwischen Migrationssystem und PLV

**Status:** angenommen am 29.10.2026 (Entscheid des Maintainers, E-007:
Option B für die Stufen 0 bis 2; die Stufen 3 bis 5 sind nicht beauftragt).
Ort der Implementierung entschieden am 02.11.2026 (eigenes Paket `plv/`).
Stufe 0 und Stufe 1 umgesetzt am 02.11.2026, Stufe 2 in drei Commits ab
dem 02.11.2026 (2a: die Prüfstrecke). Entwurf vom 22.10.2026 aus Auftrag
A-020, Befund A29-01 der externen Prüfrunde vom 14.10.2026.

## Kontext

ADR-017 hat entschieden: „Das Tool definiert die Schnittstelle, die es von
einem Zielsystem braucht (Parametrierung entgegennehmen, Werte liefern,
Verlauf liefern), und diese Schnittstelle ist Tool." Ob daraus ein eigenes
Modul oder eine Paketteilung folgt, sollte „ein ADR nach der Messung"
entscheiden. Bis zu diesem ADR gab es die Schnittstelle nur als Liste der
erlaubten Importe: `TOOL_NACH_VORZEIGE_ERLAUBT` in
`ontologie/code_karte.py`, eine Ratsche, in der jede neue Kante ein Befund
ist.

Der externe Prüfer (ToDo 29, A29-01) urteilt: Die Ratsche verhindert neue
unbemerkte Kanten, aber sie beschreibt die vorhandene Integration, statt
einen fachlichen Vertrag umzusetzen. Für Quellen gibt es mit `InputAdapter`
(`quellen/adapters/base.py`) eine austauschbare Abstraktion, für das
Zielsystem nicht. Ein anderes Zielsystem müsste viele Prüfer im Tool
anpassen.

**Die Messung (Stand 0b6470c, 22.10.2026; am Stand 9986830 vom 02.11.2026
nachgemessen: 36 Kanten, 62 verschiedene Namen):**

- 36 erlaubte Kanten aus 15 Modulen des Tools in 13 Module der PLV.
- Über diese Kanten gehen 66 Namen (AST-Messung über alle 36 Kanten),
  62 verschiedene: `ModelPoint`, `Rechenkern`, `erhoehungs_scheibe` und
  `vertrags_monatsreserve` kommen je über zwei Module.
- Am meisten importieren `gates/fuehrungsprobe` (6 Kanten),
  `gates/verankerung_belegen` (5), `gates/bestand_uebernehmen` (4) und
  `qa/aktuarieller_test` (4).
- Am häufigsten importiert werden `kern/__init__` (7 Kanten),
  `bestand/parquet_io` (5), `kern/beitragsreduktion` (4) und
  `kern/korrekturschicht` (4). Die meisten Namen liefert
  `bestand/migrationszugang` (16).

Nach dem, was sie tun, fallen die Namen in fünf Fähigkeiten:

| Fähigkeit | Was das Tool vom Zielsystem braucht | Heutige Namen (Auswahl) | Anzahl |
|---|---|---|---|
| 1 Rechnungsgrundlagen | den wirksamen Parametersatz je Vertrag, Tafeln, Produkte | `ModelPoint`, `BestandConfig`, `config_aus_text`, `grundlagen_je_police`, `PRODUKTE`, `hole`, `verfuegbare_tafeln`, `validiere_alterstafel`, `_parse_tables` | 11 |
| 2 Bestandsdaten | Bestand lesen und schreiben, Manifest | `read_portfolio`, `write_portfolio`, `lies_manifest_bytes`, `schreibe_manifest`, `ROLLEN_DATEIEN` | 10 |
| 3 Bewertung | Werte und Verlauf je Vertrag, Vorgänge, Korrekturschicht | `berechne`, `Rechenkern`, `vertrags_monatsreserve`, `Vorgangsfolge`, `vorgang`, `Korrekturschicht`, `schichtwert_bei`, `zuschlag_bei_pex`, `TEILKUENDIGUNG` | 23 |
| 4 Zugang | aus gelieferten Werten den Anfangszustand im Zielsystem ableiten | `uebernehmen`, `fuehrungswerte`, `leite_*` (9 Ableitungen), `bestimme_serie_mit_kandidaten` | 16 |
| 5 Bestandsprüfung | P-B1 auf einem Bestand fahren | `lies_und_pruefe_pb1`, `fortschreibung_pruefen`, `bestandszeilen`, `PB1_ROLLEN` | 6 |

Zwei Befunde der Prüfrunde ToDo 28 zeigen, was ein fehlender Vertrag kostet.
Bei T28-04 verglich die Führungsprobe nur die gesetzten Felder einer
Spez-Zelle, weil niemand den wirksamen Parametersatz einschließlich der
Defaults liefert. Den Default kennt nur `kern/model_point.py`, und
`models/bestand.py` importiert ihn von dort. Bei T28-01 war die
Komponentenzahl eines Vergleichs keine Aussage des Zielsystems, sondern
eine Behauptung im Bericht. Beide sind mit T28 repariert; der Vertrag
verschiebt die Reparaturen an ihren Ort, ohne sie zu ändern.

ADR-017 hat eine eigene Hülle bewusst abgelehnt: Eine Hülle hätte die
Nutzung versteckt, statt sie in der Liste zu messen. Jede Option unten muss
sich daran messen lassen.

## Optionen

### A: Die Ratsche bleibt, die gemessenen Namen werden der Vertrag

Die Namen kommen als zweite Ratsche neben die Kantenliste, mit einem
Zähltest: Jeder neue Name ist ein Befund. Dazu ein Dokument, das die fünf
Fähigkeiten beschreibt.

- Für: billig, nichts wandert, kein Wert ändert sich.
- Gegen: Der Vertrag bleibt die Summe dessen, was die PLV zufällig anbietet.
  Ein zweites Zielsystem müsste dieselben Namen mit derselben Semantik
  liefern, auch interne wie `_parse_tables`. T28-04 bleibt eine Frage an
  jeden einzelnen Prüfer.
- Aufwand: 1 Tag.

### B: Ein versionierter Zielvertrag im Tool, die PLV erfüllt ihn

Ein neues Tool-Paket `zielsystem/` (Ebene 2) beschreibt die Fähigkeiten als
Protokolle mit eigenen Datentypen, nach dem Muster von `InputAdapter`. Dazu
eine Versionskennung. Die PLV liefert eine Implementierung in Ebene 3,
außerhalb von `kern/`. Das Tool importiert aus der PLV nur noch an einer
Stelle, wo die Implementierung bekannt gemacht wird. Die Ratsche schrumpft
Fähigkeit für Fähigkeit, bis nur diese eine Kante übrig ist.

- Für: Das ist die Schnittstelle, die ADR-017 beschreibt. Der Vertrag
  versteckt nichts, er ist selbst die gemessene Fläche: versioniert, mit
  eigenen Konformitätstests, die jede Implementierung bestehen muss. Er
  kann den wirksamen Parametersatz einmal festlegen (die Wurzel von
  T28-04) und Aussagen wie die Komponentenzahl als Leistung des
  Zielsystems führen statt als Behauptung im Beleg (die Wurzel von
  T28-01).
- Gegen: mehrere Tage Arbeit ohne neue Fachfunktion. Die Grenze zwischen
  Fähigkeit 4 (Zugang) und dem Tool muss fachlich gezogen werden, weil die
  Ableitung des Anfangszustands heute halb Prüfstrecke und halb Führung
  ist.
- Aufwand: 7 bis 10 Arbeitstage, in fünf Stufen, je eine Fähigkeit.

### C: Eine Fassade in der PLV

Ein Modul in Ebene 3 reicht die Namen weiter, das Tool importiert nur noch
dieses Modul.

- Für: in einem Tag erledigt, die Ratsche fällt auf eine Kante.
- Gegen: Genau das hat ADR-017 abgelehnt. Die Kopplung bleibt dieselbe und
  wird nur unsichtbar. Austauschbar wird nichts.
- Aufwand: 1 Tag.

### D: Paketteilung oder eigenes Repository für die PLV

- Gegen: ADR-017 schließt das ausdrücklich aus („das Drift-Prinzip lebt
  von der Ko-Lokation"). Der Prüfer rät ebenfalls davon ab, solange kein
  Bedarf an unabhängiger Veröffentlichung belegt ist.
- Nicht weiter verfolgt.

## Entscheidung

**Option B, stufenweise.** Jede Stufe ist ein eigener Commit nach voller
Suite. Keine Stufe darf einen Wert ändern: Die Suite und die Referenzwerte
bleiben unverändert grün, und das Nachfahren des dritten Falls liefert
dieselben Bytes. Beauftragt sind die Stufen 0 bis 2; die Stufen 3 bis 5
werden danach neu entschieden.

**Der Vertrag** liegt im Paket `src/rechner_pipeline/zielsystem/` (Ebene 2,
Tool): `version.py` (die Versionskennung, drei Zahlen wie beim
Gate-Vertrag), `vertrag.py` (der Katalog der fünf Fähigkeiten, das
Wurzelprotokoll `Zielsystem`, je Stufe ein Protokoll je Fähigkeit),
`konformitaet.py` (die Prüfungen, die jede Implementierung bestehen muss)
und `anbieter.py` (die eine Stelle, die die Implementierung kennt, als
statischer Import). Das Paket importiert aus dem Tool nur `models`. Die
Protokolle sind strukturell (`typing.Protocol`): Eine Implementierung
importiert nichts aus dem Tool, sie hat nur die verlangte Form.

**Die Implementierung** liegt im neuen Paket `src/rechner_pipeline/plv/`
(Ebene 3, Objekt PLV nach ADR-028, neben `kern`, `bestand` und `betrieb`).
Es erfüllt den Vertrag mit dem, was Kern und Bestandsführung heute können,
und darf `kern`, `bestand`, `models` und `zielsystem` importieren. Die
Alternative, ein Modul in `bestand/`, ist verworfen: `bestand` ist Bestand
und Führung; Rechnungsgrundlagen und Bewertung sind Adapter des Kerns,
nicht der Führung. Beide Orte liegen außerhalb von `kern/`: Der Kernstand
A-K2 bindet das Paket `kern` (`models/kernabnahme.KERNSTAND`), die
Referenzwerte und die Grundsatzdokumentation; keine neue Kernabnahme ist
nötig.

**Die Versionskennung** nennt die PLV als eigene Aussage (Literal in
`plv/zielsystem.py`), nicht als Import der Konstante des Vertrags: Erst dann
ist die Verträglichkeitsprüfung eine Prüfung. Verträglich heißt gleiche
Haupt- und Nebenversion. In den Stufen 0 bis 2 kommt die Vertragsversion
nicht in die Belege der Gates: Das wäre ein Patch-Sprung je Gate und bräche
die Bytegleichheit des Nachfahrens. Ob sie später in die Belege gehört, ist
ein eigener Entscheid.

**Die Regel in der Schichtenkarte:** Das Tool kennt die Implementierung des
Zielsystems nur in `zielsystem/anbieter.py`. Die 36 Kanten vom Stand
9986830 bleiben als Altlast in `TOOL_NACH_VORZEIGE_ERLAUBT`
(`ALTLAST_KANTEN`), ein Test hält ihre Zahl mit Gleichheit fest, und jede
Stufe senkt sie. Eine neue Kante aus dem Tool in die Vorzeige bleibt ein
Befund; aus einem anderen Modul der Schicht `zielsystem` als dem Anbieter
ist sie ein Befund, auch wenn sie in der Ratsche stünde.

Reihenfolge der Stufen, nach Nutzen und Größe:

| Stufe | Inhalt | Stand |
|---|---|---|
| 0 | Gerüst: Paket `zielsystem/` mit Version 0.1.0, Katalog der Fähigkeiten, Wurzelprotokoll, Konformität, Anbieter; Paket `plv/` mit der PLV, die noch keine Fähigkeit anbietet; Regel und Zähltest in der Schichtenkarte; Skill, ADR-017, ADR-028, README | umgesetzt 02.11.2026 |
| 1 | Rechnungsgrundlagen (11 Namen): Der Vertrag liefert den wirksamen Parametersatz einer Generation bzw. einer Police vollständig, einschließlich der Defaults. Führungsprobe, Prüfstrecke und `models/bestand.py` lesen ihn von dort. Das schließt die Klasse von T28-04, nicht nur den einen Befund. | umgesetzt 02.11.2026 (unten) |
| 2 | Bewertung (23 Namen): Werte, Verlauf und Vorgänge je Vertrag für `qa/aktuarieller_test`, `qa/migrationssuite` und `qa/abzugsabgleich`. Hier gehört die Komponentenzahl eines gelieferten Werts hin (T28-01). Spiegelt der Vertrag die Kern-Schnittstellen 1:1, ist er die Fassade aus Option C; er muss schmaler sein und dieselben Werte liefern. | 2a (Vertrag, PLV, Prüfstrecke), 2b (die Gates) und 2c (Schichtbeleg an den Bestand binden) umgesetzt 02.11.2026 |
| 3 | Bestandsdaten (10 Namen) | nicht beauftragt |
| 4 | Bestandsprüfung (6 Namen) | nicht beauftragt |
| 5 | Zugang (16 Namen), zuletzt. Er ist am stärksten PLV-eigen. Vorher ist zu klären, welcher Teil der Ableitung Prüfstrecke (Tool) und welcher Führung (PLV) ist. | nicht beauftragt |

Je Fähigkeit trägt die Stufe ihr Protokoll in `PROTOKOLL_JE_FAEHIGKEIT`
ein. Bis dahin darf kein Zielsystem die Fähigkeit anbieten, weil der
Vertrag nicht sagt, was sie ist; so beschreibt der Vertrag nichts, was
niemand erfüllt.

### Stufe 1: Rechnungsgrundlagen (Vertrag 0.2.0)

Das Protokoll `zielsystem/rechnungsgrundlagen.py` sagt, was das Tool vom
Zielsystem braucht, ohne dessen Kern zu kennen: die Produkte, je Produkt
den `Parametersatz` (Felder mit Typ und die Defaults der Felder, die eine
Generation auslassen darf) und die Tafeln (Namen, Prüfung einer
Alterstafel, Lesen des Tafelspeichers). Den Modellpunkt aus den wirksamen
Feldern lieferte Stufe 1 ebenfalls; mit Stufe 2 nimmt die Bewertung die
Felder selbst entgegen, und die Methode ist entfallen. Die PLV erfüllt
das Protokoll in `plv/rechnungsgrundlagen.py` als
Weitergabe dessen, was `kern.produkte`, die Modellpunkt-Klassen und
`kern.tafeln` sagen; sie nennt die Version 0.2.0 selbst. Die
Konformitätsprüfung prüft über die Form hinaus, was das Protokoll in
Worten verlangt (`konformitaet.PRUEFUNG_JE_FAEHIGKEIT`).

Der wirksame Parametersatz hat damit einen Ort: `models.bestand.
model_point_kwargs`, der eine Weg des Tools zum vollständigen
Modellpunkt, liest die Defaults über den Vertrag
(`generation_field_defaults`), nicht mehr aus `kern/model_point.py`;
Führungsprobe und Prüfstrecke gehen diesen Weg (T28-04). Die Führung
liest dieselben Defaults direkt aus ihrem Kern (`bestand/config.py`).

Fünf Kanten der Altlast sind gelöst (36 auf 31): `models/bestand` und
`ontologie/code_index`, `qa/abzugsabgleich`, `quellen/tafel_import`,
`spez/erzeugen` lesen über `zielsystem/anbieter.py`. Ein Test hält je
Konsument mit einer fremden Umsetzung fest, dass er vom Vertrag liest
und nicht vom Kern.

Nicht in Stufe 1, mit Begründung: Die sechs Bewertungskonsumenten
(`fuehrungsprobe`, `generation_golden`, `verankerung_belegen`,
`bestand_uebernehmen`, `qa/aktuarieller_test`, `qa/migrationssuite`)
bauen den Modellpunkt weiter selbst, weil sie ihn an den Rechenkern
geben; ihre Kanten löst Stufe 2 zusammen mit der Bewertung.
`MissingMortalityTableError` (`qa/migrationssuite`) ist die Ausnahme der
Bewertung bei fehlender Tafel und geht mit ihr. Die Führungsprobe liest
die Config der Führung als Ganzes (`BestandConfig`, `config_aus_text`,
`grundlagen_je_police`: Generationen, Tarifwerk, Annahmen); was davon
Rechnungsgrundlage und was Bestandsdaten ist, entscheidet Stufe 2 mit
der Bewertung oder Stufe 3.

### Stufe 2a: Bewertung (Vertrag 0.3.0), die Prüfstrecke

Das Protokoll `zielsystem/bewertung.py` nimmt Vertragsdaten entgegen und
liefert Werte; es nennt keinen Rechenkern, keinen Baustein und keinen
Scheiben-Modellpunkt. Ein `Vertragswerte`-Objekt (aus den wirksamen
Feldern, den Scheiben als Jahr und Summe und den Tarifwerk-Schaltern)
liefert die Reserve des beitragspflichtigen Vertrags, die beitragsfreie
Summe, die Gesamtsumme, den Jahresbeitrag, die Komponentenzahl und seine
Vorgangsfolge (`Folge` mit `Stand`: Werte am Monat, Komponenten, Stand
vor und nach einem Vorgang, Jahresbeitrag, beitragsfreie Summe ohne
Zuschlag). Dazu die Korrekturschicht (aus dem Beleg lesen, Wert am Monat,
Zuschlag bei Beitragsfreistellung, trägt sie), die Vorgangsregeln (Rang
je Art, Verfahren, Umfänge, Umfang einer Teilkündigung), die
Prämiensätze, die Verlaufszeile und der volle Rechenlauf. Die Ausnahmen
des Zielsystems sind `Datenfehler` (`Vorgangsfehler`, `Schichtfehler`);
die PLV übersetzt ihre Kernausnahmen dorthin, mit dem Text des Kerns, und
die Prüfstrecke fängt nur noch diese. Die PLV erfüllt das Protokoll in
`plv/bewertung.py` als Weitergabe an `kern.rechenkern`,
`kern.vorgangsfolge`, `kern.korrekturschicht` und `kern.beitragsreduktion`.

Eine Grenze ist bewusst gezogen: Die beitragsfreie Reserve eines
Vertrags mit Erhöhungsscheiben kommt je Baustein
(`reserven_beitragsfrei`), nicht als Summe. Die beiden Prüfstrecken
summieren sie in verschiedener Reihenfolge, und Gleitkommasummen hängen
von ihr ab (auf Fall 3 gemessen: 2391 von 5517 Fällen verschieden in der
letzten Stelle). Der Vergleich kennt seine Komponenten ohnehin, weil
seine Toleranz mit ihnen wächst; die Summe bleibt deshalb beim Vergleich,
jeder in seiner Reihenfolge, und kein Beleg ändert ein Byte. Wo die
Prüfstrecken gleich summierten (beitragsfreie Summe, Jahresbeitrag),
summiert jetzt die PLV; wo der Kern summiert (Reserve mit Scheiben,
Werte eines Stands), tat er es schon vorher.

Konsumenten in 2a: `qa/migrationssuite`, `qa/aktuarieller_test` und
`qa/abzugsabgleich` lesen über den Anbieter; sieben Kanten der Altlast
sind gelöst (31 auf 24). Je Modul hält ein Test mit einer fremden
Bewertung fest, dass es vom Vertrag liest. Die Werte des Vertrags sind in
`tests/test_zielsystem.py` gegen den Kern als Kontrollrechnung gehalten,
bitgleich. Die Gates (`fuehrungsprobe`, `generation_golden`,
`verankerung_belegen`, `bestand_uebernehmen`, `aktuartest_lauf`,
`migrationssuite_lauf`) folgen in 2b.

### Stufe 2b: die Gates

Die sechs Gates (`fuehrungsprobe`, `generation_golden`, `verankerung_belegen`,
`bestand_uebernehmen`, `aktuartest_lauf`, `migrationssuite_lauf`) lesen
über den Anbieter; zehn Kanten der Altlast sind gelöst (24 auf 14). Die
14 verbleibenden gehen alle nach `bestand/` (Stufen 3 bis 5). Dafür
sagt der Vertrag acht Dinge mehr, die nur die Gates brauchen: den Stand
eines Vertrags vor jedem Vorgang (`Vertragswerte.stand`), einen Baustein
aus eigenen Feldern, wie die Führung eine gebuchte Erhöhung führt
(`mit_baustein`), was ein Vorgang gebucht hat (`Folge.ergebnis`,
`Vorgangsergebnis`), die Leistung eines terminalen Falls
(`Stand.leistung`), die Art und die Ordnung der Vorgänge
(`Vorgangsregeln.art`, `Vorgangsregeln.schluessel`), die Felder einer
Schicht (`schichtfelder`) und die Felder einer Erhöhungsscheibe, wie das
Zielsystem sie aus dem Grundvertrag ableitet (`Bewertung.scheibe`): Die
Übernahme schreibt sie in die Scheibentabelle der Führung. Die Scheibe
bleibt damit als Datensatz sichtbar, nicht als Modellpunkt des Kerns.

Die zwei Stellen aus A-054 (B2) lösen ausgelassene Felder jetzt über den
wirksamen Satz: `generation_golden` mit den Defaults des Parametersatzes,
`bestand_uebernehmen` über `model_point_kwargs`. Die Nachzüge B1 (zwei
Positivkontrollen) und B3 sind drin: Jeder Konsument bindet das Modul des
Anbieters, nicht den Namen, und importiert es früh; was der Anbieter zur
Laufzeit sagt, gilt, und ein Test kann ihn austauschen. Die beitragsfreie
Gesamtsumme zählt nur die Bausteine, die im Jahr der Freistellung
bestehen (vorher stand dieser Filter an einer von vier Stellen).

### Stufe 2c: der Schichtbeleg gehört zum Bestand (A-020, H3)

Mit der Bewertung geht die Korrekturschicht ausdrücklich "für diesen
Bestand" über den Vertrag an das Zielsystem; die Prüfstation
(`gates/aktuartest_lauf`) hält den abgeleiteten Schichtbeleg deshalb an
den Bestand des Laufs: Der mit `--bestand` gebundene Bestand muss mit
seinem SHA-256 unter den gebundenen Eingaben des Belegs stehen, sonst
verweigert der Lauf ("Schichtbeleg gehört zu einem anderen Bestand").
Das Ergebnis nennt die Bindung (`schichtbeleg`: Name, Art, SHA-256), und
die Vorlage A-M1 verlangt sie dort: `gates/aktuartest.py` 4.0.0 auf
5.0.0, Grund im Gate-Vertrag. Fall 3 läuft weiter (sein Schichtbeleg ist
der des eigenen Bestands); das neue Feld ist der einzige Unterschied in
`aktuartest*.json` gegenüber der Stufe-1-Probe. Führungsprobe und
Migrationssuite bleiben unberührt; ob der Schichtbeleg im Bestands-Scope
Pflicht sein soll (H2), ist ein eigener Auftrag.

### Stufe 2d: Nachzüge aus den Prüfungen A-054 und A-056

Die PLV baut auch den Grundvertrag innerhalb ihrer Übersetzung: Eine
Lieferung mit einer Tafel, die das Zielsystem nicht führt, ist ein
`Datenfehler` des Vertrags und damit ein Befund des Vertrags in
Prüfstrecke und aktuariellem Test, kein Absturz (A-056, B1). `felder`
eines Vertrags sind die wirksamen Felder, wie das Zielsystem sie führt,
nicht die gelieferten (B2). Die Konformität der Rechnungsgrundlagen
verlangt `ValueError` für eine leere Alterstafel und einen leeren
Tafelspeicher (A-054, H1); die PLV übersetzt dafür den Parserfehler
ihres Tafelspeichers. Die sechs Bedingungen der PLV-Umsetzung, die A-056
(B4) ohne Kontrollrechnung fand, sind jetzt gegen den Kern gehalten:
Beitragsdauer-Filter des Jahresbeitrags, Zuschlag bei der beitragsfreien
Summe, bestehende Bausteine in der Komponentenzahl, Schicht und Umfang
der Teilkündigung im Stand, und der Baustein aus eigenen Feldern mit
Feldern, die keine abgeleitete Scheibe sind. Nicht nachgezogen, weil
Hinweise ohne Bedingung: die drei Anbieterbindungen beim Import
(A-056 H1), die Übersetzung von `KorrekturschichtFehler` an den
Werte-Pfaden (H3), die Wache der Summationsreihenfolge jenseits der
Fall-3-Probe (H6).

## Nachweis je Stufe

- volle Suite grün;
- das Nachfahren des dritten Falls in einer Wegwerfwelt mit Testschlüsseln,
  die 16 Dateien der `ERWARTUNG` bytegleich;
- ab Stufe 1 die Zahl der Altlast-Kanten gesenkt (Stufe 0 ist Gerüst und
  lässt sie bei 36), die Ratsche gleich der Messung; `landkarte.md`,
  Code-Index und Code-Karte nachgezogen;
- keine Gate-Version geändert, weil sich kein Beleg-Byte ändert.

## Konsequenzen

- **Ebenen und Wache:** Die Code-Karte kennt die Schichten `zielsystem`
  (Tool) und `plv` (Vorzeige) und die Regel „das Tool kennt die
  Implementierung nur im Anbieter". `TOOL_NACH_VORZEIGE_ERLAUBT` schrumpft
  je Stufe. Kommt eine Kante neu hinzu, bleibt das ein Befund. Die
  Schichten `models`, `ontologie`, `spez`, `quellen` und `qa` dürfen seit
  Stufe 1 `zielsystem` importieren; `models/bestand.py` tut es erst beim
  Aufruf, weil die Vorzeige dieses Modul beim Laden importiert.
- **Ausnahmen:** Seit Stufe 2 kennen Prüfstrecke und Gates die
  Ausnahmetypen des Kerns nicht mehr; eine Verweigerung des Zielsystems
  ist ein `Datenfehler` des Vertrags. Die Befundtexte tragen weiter den
  Text des Kerns; nur der Typname in einem Abbruchtext ist der des Vertrags.
- **Die Gates kennen den Kern nicht mehr:** Aus `gates/` führt keine Kante
  mehr nach `kern/`; die Schicht `gates` darf `zielsystem` importieren.
- **Gezeichnete Gegenstände:** Der Kern wird nicht geändert. Referenzwerte,
  `plv/mathematik`, `plv/tarifplaene` und `plv/configs` bleiben unberührt.
- **Systemstand:** Jede Stufe ändert den Code und damit den Systemstand.
  Fall 3 ist auf seinem Stand gezeichnet. Ändert sich keine Gate-Version
  und kein Ergebnis, bleibt das Nachfahren gleich. Das ist je Stufe zu
  messen, nicht anzunehmen.
- **Laufzeit:** Der Tageslauf nutzt das Tool nicht. Die Laufzeit muss
  deshalb nicht umgestellt werden. Ein neues Image entsteht trotzdem mit
  jedem Merge.
- **Plattformanspruch:** Erst mit Stufe 5 ist die Aussage belegt, das Tool
  lasse sich an ein anderes Zielsystem anschließen. Bis dahin ist sie
  Absicht, nicht Stand. Texte für Dritte sollten das so sagen.
- **Doku:** ADR-017 und ADR-028 tragen einen Nachtrag mit Verweis auf dieses
  ADR. Der Skill `entwickle-im-zielsystem` nennt `zielsystem/` und `plv/`
  in der Schichtenkarte; das README nennt beide Pakete bei ihrer Ebene.

## Bewusst nicht Bestandteil

- ein zweites Zielsystem; der Vertrag wird an der PLV gebaut und an ihr
  geprüft;
- die Trennung von Simulation und Führung (ADR-031, A29-03);
- A29-02 (der Zyklus zwischen `models.schemas` und `gates._common`), nach
  Entscheid vom 22.10.2026 nicht in diesem Umfang;
- eine Änderung am Rechenkern oder an seinen Referenzwerten;
- die Vertragsversion in den Belegen der Gates (eigener Entscheid).
