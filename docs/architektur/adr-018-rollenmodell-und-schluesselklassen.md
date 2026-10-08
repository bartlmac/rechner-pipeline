# ADR-018: Rollenmodell des KI-Tools — Agenten legen vor, Menschen zeichnen, der Schlüssel sagt, wer besetzt

**Status:** angenommen am 2026-09-05 (Maintainer). Ersetzt die Rollenregel
des Vier-Rollen-Modells vom 2026-09-01 und präzisiert P2 und ADR-008.

## Kontext

Bis zum zweiten Baldrian-Lauf galt: Agenten bereiten vor, „der Mensch“
entscheidet (`--rolle mensch`). Für diesen Lauf entstand das
Vier-Rollen-Modell: Eine Zeichnungsordnung bindet Rollen an
Schlüssel-Fingerabdrücke, und die Rolle, der der Schlüssel gehört,
entscheidet und zeichnet (`ontologie.entscheide`, `gates.gate_entscheid`).
Im Lauf besetzten KI-Sitzungen diese Rollen im Mandat und zeichneten als
Rolle „mensch“.

Zwei Prüfungen fanden die Folgen. Prinzip P2, ADR-008, `AGENTS.md` und
drei Skills sagten weiter „Mensch“, während der Code die Rolle des
Schlüssels entscheiden ließ. Ein Skill und ein Docstring erlaubten eine
Auflösung „ohne Menschen“, die kein Code kannte. Snapshot, Ledger und
Fachbericht konnten nicht ausweisen, ob ein Mensch oder eine KI-Sitzung
gezeichnet hatte, und die Rollen selbst waren im Repository nirgends
definiert. Die Frage, wer einen Quellenwiderspruch entscheiden darf, hatte
drei Antworten.

## Entscheidung

### 1. Zwei Sorten Rollen, getrennt durch die Ebene (ADR-017)

**Agentenrollen des KI-Tools** (Ebene 2) haben je ein Ziel, die
Perspektive eines laufenden Unternehmens, Skills, Werkzeuge und
Schreibgrenzen. Sie sind im Repository als Agentendefinitionen versioniert,
arbeiten zusammen, bis ein Problem gelöst ist, und legen dann vor. Eine
Abnahme zeichnen sie nie (Nachtrag 2026-09-16). Eine fünfte Rolle,
`agent/betrieb`, kam mit dem ersten Nachtrag hinzu.

| Kennung | Anzeige | Ziel |
|---|---|---|
| `agent/aktuariat` | Aktuariats-Agent | das Unternehmen bildet nach der Migration fachlich alles richtig ab (Transformation, aktuarielle Tests, Controlling, Bestandsfortführung) |
| `agent/architektur` | Architektur-Agent | die Migration arbeitet in der vorgegebenen IT-Architektur |
| `agent/rechenkern` | Rechenkern-Agent | das Zielsystem bleibt stabil: Regressionstests, Dokumentation, Kern-Abnahmeprotokoll |
| `agent/programmleitung` | Programmleitungs-Agent | die Migration wird effizient geliefert; orchestriert die drei anderen |

**Menschliche Rollen** sind Funktionen des Unternehmens. Sie prüfen die
Vorlagen, stellen Rückfragen, sehen selbst nach und zeichnen mit ihrem
Schlüssel.

| Kennung | Anzeige |
|---|---|
| `mensch/aktuariat` | Verantwortlicher Aktuar |
| `mensch/architektur` | IT-Verantwortung |
| `mensch/rechenkern` | Rechenkern-Verantwortung |
| `mensch/betrieb` | Betriebsverantwortung |
| `mensch/programmleitung` | Programmleitung |
| `mensch/quell-aktuar` | Aktuar des abgebenden Hauses |

Eine menschliche Rolle trägt denselben Namen wie die Agentenrolle, die ihr
zuarbeitet; die Ebene steht im Präfix (Entscheid des Maintainers vom
2026-09-16). `agent/rechenkern` legt vor, `mensch/rechenkern` zeichnet.
Angezeigt wird der Titel der Funktion, etwa „Verantwortlicher Aktuar“ für
`mensch/aktuariat`. `mensch/quell-aktuar` hat kein Gegenstück, denn er
gehört zum abgebenden Haus.

Die früheren Kennungen `plv-aktuar`, `plv-va`, `quelle-experte`,
`programmleiter` und der Platzhalter `mensch` entfallen; die Vorzeige
bildet sie auf die neuen ab. Ebenso entfallen die zwischenzeitlichen Namen
nach der Verantwortung (`verantwortlicher-aktuar`, `it-verantwortung`,
`entwicklungsverantwortung`, `betriebsverantwortung`). Wer zeichnet, ist
eine Funktion; wer vorbereitet, ist ein Agent; wie der Schlüssel besetzt
war, steht im Snapshot.

### 2. Schlüsselklassen

Die Zeichnungsordnung trägt je Rolle eine **Schlüsselklasse**:

| Klasse | Bedeutung | Darf zeichnen |
|---|---|---|
| `mensch` | ein Schlüssel in der Hand einer natürlichen Person | ja |
| `simulation` | ein Schlüssel, mit dem die Vorzeige eine menschliche Rolle nachahmt | ja, und jeder Beleg sagt es |
| `agent` | ein Schlüssel einer Agentenrolle | nein; er weist die Herkunft einer Vorlage aus |

Die Rollenkennung bleibt bei Simulation dieselbe wie in der Wirklichkeit,
nur die Klasse wechselt. Ein Bericht schreibt etwa „gezeichnet:
Verantwortlicher Aktuar, Schlüssel: Simulation“. Ein Agentenschlüssel an
einem Annahme-Snapshot ist ein Fehler. Die Klasse `betrieb` kam mit dem
Nachtrag vom 2026-09-30 hinzu.

### 3. Der Snapshot trägt die Besetzung

Jeder P9-Snapshot und jede endgültige Entscheidung einer Diskrepanz tragen
unter `zeichnung` die Rolle (aus dem Schlüssel bestimmt), die
Schlüsselklasse und bei Simulation den Hash des Mandats, unter dem die
simulierte Rolle handelte. Aus dem signierten Beleg allein ist damit
ablesbar, welche Rolle wie besetzt war.

### 4. Auflösung von Widersprüchen: Option a

Der Abzugsabgleich erzeugt nur Belege. Eine Diskrepanz löst nie eine
Maschine endgültig auf; der Satz „die Auflösung darf ohne Menschen
erfolgen“ in Skill und Docstring wurde gestrichen. P2 bleibt: Agenten
lösen nur vorläufig auf, die endgültige Auflösung zeichnet eine menschliche
Rolle, in der Vorzeige mit Simulationsschlüssel.

### 5. Der zweite Baldrian-Lauf ist eine ausgewiesene Ausnahme

Seine sechzehn Snapshots haben KI-Sitzungen im Mandat unter der Rolle
„mensch“ gezeichnet, mit dem Simulationsschlüssel, bevor es die Klasse
dafür gab. Sie bleiben gültig und gepinnt, nichts wird nachsigniert.
Fachbericht und Fallseite weisen aus, dass die zeichnenden Rollen mit KI
besetzt waren und der Schlüssel ein Simulationsschlüssel ist. Neue Fälle
laufen unter diesem ADR.

## Konsequenzen

- `models.zeichnung`: Ordnung Schema 2 mit `schluesselklasse` und den neuen
  Kennungen; Agentenrollen ohne Gate-Berechtigung; alte Kennungen werden mit
  Meldung abgewiesen, nicht still umgedeutet.
- `gates.gate_entscheid` und `ontologie.entscheide`: `--rolle` entfällt
  zugunsten der Ordnung, ohne Ordnung keine Annahme. Bei Schlüsselklasse
  `simulation` ist `--mandat` Pflicht; Gate, Entscheidungskommando und
  Snapshot-Schema verweigern eine simulierte Zeichnung ohne Mandats-Hash.
  Eine Ablehnung durch eine Agentenrolle bleibt möglich (ADR-008, Punkt 6).
  Das Snapshot-Schema steigt auf Version 7; ältere Snapshots bleiben
  lesbar.
- Skills und `AGENTS.md` folgen den Rollen. Die Agentenrollen liegen als
  Definitionen unter `.claude/agents/`, gespiegelt in `.agents/`; die
  Gleichheit beider prüft ein Test.
- Fachbericht, Fallseite und Fachspezifikation zeigen Rolle und Klasse;
  „gezeichnet“ steht nur bei geprüfter Signatur.
- Die Regie der Vorzeige (Ebene 4, ADR-017) hält die Auftragsprofile der
  simulierten Menschen und erzeugt deren Mandate. Die Auftragsprofile der
  Agentenrollen gehören zum Werkzeug und liegen im Repository.

## Nachträge

Die Nachträge sind nach Datum adressiert; Code und Tests verweisen in
dieser Form auf sie (etwa „ADR-018, Nachtrag 2026-09-30“). Die Herleitung
im Einzelnen steht in der Geschichte dieser Datei.

## Nachtrag 2026-09-16: Die Betriebsrolle, und zwei Sorten Rollen

Niemand verantwortete die Bestandsführung, also das, was nach der Migration
jeden Tag läuft. Die Frage fiel abwechselnd der IT-Verantwortung und dem
Verantwortlichen Aktuar zu. Der eine betreibt die Maschine, der andere
verantwortet die Rechnung; den Bestand führt keiner von beiden. Neu sind
deshalb `agent/betrieb` (Betriebs-Agent) und `mensch/betrieb`
(Betriebsverantwortung). Die Betriebsverantwortung ist eine fachliche Rolle
mit Verantwortung für den Kundenservice, nicht die IT: Sie verantwortet,
was gegenüber dem Versicherungsnehmer gilt. Sie zeichnet die Auslieferung
(`A-B1`).

### Linie und Fall

Das Unternehmen führt einen Bestand (Linie: täglich, unabhängig von einem
Fall), und es migriert (Projekt: je Fall, endlich).

| Rolle | Linie | Fall |
|---|---|---|
| `mensch/betrieb` | ja | ja |
| `mensch/aktuariat` | ja | ja |
| `mensch/rechenkern` | ja | ja |
| `mensch/architektur` | ja | ja |
| `mensch/programmleitung` | nein | ja |
| `mensch/quell-aktuar` | nein | ja |

Die Linienrollen gibt es, solange es das Unternehmen gibt. Die
Programmleitung entsteht mit einem Fall und endet mit ihm, der Aktuar des
abgebenden Hauses ebenso. Eine Fallrolle hat im Tagesbetrieb nichts zu
zeichnen, und eine Linienrolle zeichnet Dinge, die kein Fall abdeckt, etwa
die Auslieferung des laufenden Bestands.

**Anlass ist der Fall, Geltung ist die Linie.** Eine T-Box wächst, weil ein
Fall eine Frage erzwingt: Baldrian liefert `RK`, das Zielsystem kannte kein
Raucherkennzeichen. Ist die Erweiterung abgenommen, erbt der nächste Fall
sie. Dasselbe gilt für den Rechenkern. Daraus folgten zwei Entscheidungen:

* `A-O1.tbox-aenderung` (vorher `A-K1`) nimmt die Änderung der T-Box ab.
  Es zeichnet `mensch/architektur`, denn wer verantwortet, welche Begriffe
  das Zielsystem führt, verantwortet sein Datenmodell. Die fachliche Seite
  gehört dem Aktuariat, deshalb verlangt der Belegvertrag dessen
  Stellungnahme je betroffenem Feld. Eine Doppelunterschrift kennt das
  System nicht: Die Unterschrift gehört einer Rolle, ein Beleg kann aus
  einer anderen kommen.
* `A-K2.kernaenderung`, gezeichnet von `mensch/rechenkern`, nimmt Code und
  Dokumentation des Rechenkerns ab. Pflichtbeleg ist die Regression: Der
  geänderte Kern bewertet nach der Migration den laufenden Bestand weiter,
  und diese Wirkung sieht sonst niemand. Der Beleg rechnet jeden Vertrag mit
  altem und neuem Kern und weist die Differenz je Vertrag aus. Ein Aggregat
  reicht nicht, weil sich gegenläufige Abweichungen aufheben, eine
  Stichprobe nicht, weil der gesuchte Fehler einen von tausend Verträgen
  treffen kann. Bis das Werkzeug dafür gebaut ist, gilt die Ausnahme im
  Nachtrag 2026-10-01 („Der Stand des Falls ist abgenommen“, Punkt 4).

Damals waren beide Abnahmen des Falls, und `A-B1` lag als Abnahme der Linie
im Fall, weil das Entscheid-Kommando keinen anderen Ort kannte. Den Ort für
Abnahmen der Linie schuf ADR-025 (siehe den Nachtrag zur Erstabnahme).

**Der Maintainer dieses Repositorys gehört nicht zum Rollenmodell.** Er
gehört zur Entwicklung des Werkzeugs, nicht zum Unternehmen, das damit
arbeitet. Der Platzhalter `mensch` mit `gates: ["*"]` entfällt ohne
Nachfolger.

## Nachtrag 2026-09-16: Agenten zeichnen keine Abnahme

Die Regel „Agentenrollen zeichnen nie“ ging zu weit. Zu schützen ist die
Abnahme, also die Aussage eines Menschen, dass er für etwas einsteht. Ein
Agent, der einen Ankersatz zeichnet, sagt dagegen „ich habe dieses Paket
erzeugt“. Das ist eine Aussage über Urheberschaft, und sein Beleg trägt die
Klasse `agent`. Wer die Klasse liest, wird nicht getäuscht.

* Eine Agentenrolle zeichnet keine Abnahme. Ihre `gates`-Liste bleibt leer,
  und der Validator erzwingt das.
* Eine Agentenrolle darf einen Satz zeichnen, der keine Abnahme ist (heute
  den Ankersatz eines Stands-Pakets, `models.anker`).
* Abnahmen bleiben den Klassen `mensch` und `simulation` vorbehalten.

Der praktische Grund (Entscheid des Maintainers): Bei vielen kleinen
Migrationstranchen mit täglichen Exporten kann kein Mensch jeden Export
zeichnen. Ein Agent kann es, und der Beleg sagt, dass es einer war. Der
Mensch zeichnet dort, wo etwas nach außen geht, einmal je Auslieferung
(`A-B1.auslieferung`).

**Verworfen:** ein eigener Signaturmechanismus nur für Urheberschaft. Zwei
Mechanismen wären zwei Wahrheiten über dasselbe.

## Nachtrag 2026-09-30: Schlüsselklasse betrieb

Eine Prüfrunde fand: Der Tagesbetrieb hatte keinen Zeugen außer sich
selbst. Wer die Ablage beschreiben konnte, konnte Protokoll und Eingänge
stimmig umschreiben, und jede Prüfung las nur, was derselbe Schreiber
hinterlassen hatte.

Entscheid des Maintainers: Der Betrieb bekommt einen Schlüssel wie die
übrigen Rollen. Die Schlüsseldatei liegt beim Menschen außerhalb der
Ablage (0600, ein Hardlink, 32 bis 4096 Byte), der Fingerabdruck steht in
der Zeichnungsordnung, gezeichnet wird mit HMAC nach `models.anker`
(Verfahren `hmac-sha256-v2`). Neu ist nur die Rolle:

* Ebene und Klasse `betrieb` (`betrieb/tageslauf`, Schlüsselklasse
  `betrieb`). Ebene und Klasse gehören zusammen; eine Rolle `mensch/...`
  mit Klasse `betrieb` oder umgekehrt weist die Ordnung ab.
* Die `gates`-Liste ist leer. `betrieb` gehört nicht zu den zeichnenden
  Klassen, und kein P9-Snapshot nimmt sie an.

Eine eigene Klasse braucht es, weil ein Programm, das Protokollzeilen und
Eingänge zeichnet, weder für etwas einsteht noch etwas vorlegt. Es bezeugt
nur, dass es diese Zeile geschrieben hat. Unter einer der vorhandenen
Klassen hieße jede Protokollzeile „ein Mensch hat das gezeichnet“ oder „ein
Agent hat das vorgelegt“.

Gezeichnet werden jede Zeile des Tagesprotokolls (Schema 3) und jede
`eingang.json` bei der Registrierung (Schema 3, über alle Felder samt
A-M4-Zeichnungsblock). Ohne Betriebsschlüssel läuft kein Tag, wird nichts
registriert und nichts exportiert; ein Menschen- oder Agentenschlüssel wird
mit Ausweg abgewiesen. Wer keinen Schlüssel hält, etwa der Empfänger eines
Stands-Pakets, prüft Form, Kette und Vorlauf und erfährt, dass die Signatur
für ihn nicht prüfbar ist.

Das nimmt eine frühere Abwägung zurück: `models.anker` hatte die Zeichnung
jeder Zeile verworfen, weil sie einen Schlüssel in einen unbeaufsichtigten
Nachtlauf legt. Das bleibt wahr; der Schlüssel liegt jetzt dort, nur
lesend eingebunden. Ohne ihn bezeugte der Lauf aber nichts, was ein zweiter
Schreiber nicht ebenso bezeugen könnte. Der Anker bleibt der Bezug nach
außen.

**Aufschalten.** Bestehende Ablagen werden aufgeschaltet, nicht neu
aufgesetzt: Die erste gezeichnete Zeile pinnt den ungezeichneten Vorlauf
(Zahl und Hash der Zeilen). Das geschieht nur ausdrücklich und einmal
(`tageslauf --aufschalten`, in der Bibliothek `aufschalten=True`), beim
ersten Lauf nach dem Umstieg. Denn ein Protokoll ohne gezeichnete Zeile ist
aus der Ablage allein nicht von einem gezeichneten zu unterscheiden, das
jemand ohne Schlüssel herabgestuft hat.

* Trägt das Protokoll Zeilen, aber keine gezeichnete, verweigern
  Tageslauf, Export und Neuaufsetzen (Exit 2) und nennen beide Lesarten:
  Altbestand, dann einmal `--aufschalten`; schon gezeichnet gewesen, dann
  ein Kettenbruch, und das Protokoll kommt aus der Sicherung. Aufschalten
  kann nur der Tageslauf (und das Neuaufsetzen, das die alte Ablage
  archiviert), der Export nie.
* `--aufschalten` auf ein gezeichnetes oder leeres Protokoll wird
  verweigert. Ein Schalter, der dauerhaft im Timer stünde, öffnete die
  Herabstufung wieder.
* Hat ein gezeichnetes Protokoll später wieder keine gezeichnete Zeile, ist
  das ein Kettenbruch. Die Ablage sieht das nicht; den Bezug nach außen
  liefert der Anker beim nächsten Export. Zwischen Aufschaltung und erstem
  Export schützt nur die Entscheidung des Menschen.

**Zeugen eines Eingangs** sind nur gebundene Zeilen: eine gezeichnete Zeile
(Schema 3) oder eine Zeile des gepinnten Vorlaufs. Ein ungezeichneter
Eingang (Schema 2) tritt nur ein, wenn eine gezeichnete Protokollzeile oder
der gepinnte Vorlauf ihn bezeugt.

**Offen: Schlüsselwechsel.** Der Tageslauf prüft mit genau dem aktuellen
Betriebsschlüssel. Wird er ersetzt, sind die alten Zeilen nicht mehr
prüfbar, und der Tag läuft nicht. Der nächste Schritt wäre ein Ring aus
mehreren Schlüsseln, gegen den die alten Zeilen weiter geprüft werden. Bis
dahin ist der Weg bei einem Wechsel das Neuaufsetzen; es rechnet die
Signatur der alten Ablage nicht nach und archiviert sie.

## Nachtrag 2026-10-01: Der Stand des Falls ist abgenommen — A-K2 und A-O1

`A-K2.kernaenderung` war vorgesehen, aber unwirksam: Es gab keinen
Produzenten für die Belege, kein Gate verlangte die Abnahme, und kein
Ablauf nannte sie. Der Rechenkern war außerhalb jedes Falls von Version
3.6.0 auf 3.15.0 gewachsen, ohne eine einzige Abnahme. Der Maintainer
entschied, das Gate vor dem Merge in Prozess, Dokumentation und Vorzeige
aufzunehmen, ebenso die Erweiterung der T-Box als Abnahmepunkt.

1. **Gegenstand ist der Kernstand, auf dem ein Fall rechnet,**
   einschließlich der Änderungen, die außerhalb eines Falls entstanden
   sind. Vorgelegt wird mit `--von` gleich dem zuletzt abgenommenen
   Kernstand. Die Pfadmenge steht einmal in `models.kernabnahme.KERNSTAND`:
   das Paket `kern/` mit den Rechnungsgrundlagen, die eingefrorenen
   Referenzwerte und die Grundsatzdokumentation. Nicht dazu gehören der
   Zweitkern (ADR-013), die Parametrierung (ADR-006) und die Schichten, die
   den Kern benutzen. Die Tarifpläne gehörten zunächst dazu; seit ADR-025
   sind sie Teil des Tarifwerks (`A-T1`).
2. **Eine Regel für mehrere Gegenstände.** `A-M4` verlangt in beiden
   Scopes, dass der Stand, auf dem der Fall läuft, abgenommen ist: der
   Kernstand (`A-K2`, `mensch/rechenkern`, Pflichtrolle `kernstand`) und
   der T-Box-Stand (`A-O1`, `mensch/architektur`, Pflichtrolle
   `tboxstand`), nach derselben Funktion (`models.standabnahme`,
   `gate_entscheid.standabnahme_pruefen`). Erfüllt ist das auf genau einem
   Weg:
   * (a) *abgenommen im Fall:* eine eindeutige, signierte Annahme im Fall
     auf demselben Scope- und Systemstand, gezeichnet von einer Rolle, der
     die Ordnung das Gate gibt, mit Belegen am festen Ort, gegen den
     lebenden Code nachgerechnet;
   * (b) *keine Änderung:* Der Stand ist derselbe, den die geltende Abnahme
     der Linie abgenommen hat (seit Prüfrunde G). Ein Verweis am festen Ort
     (`abgeleitet/kern/verweis.json` bzw. `abgeleitet/tbox/verweis.json`,
     Produzent `gates.stand_belegen verweisen`) trägt die vollständige,
     signierte Kopie dieses Snapshots. `A-M4` prüft Signatur, Rolle und
     Klasse und hält dessen Feld `stand` mit `==` gegen den lebenden. Der
     A-M4-Snapshot vermerkt „keine Änderung seit Abnahme <snapshot>
     (<Herkunft>)“: unverändert heißt belegt, nicht ungeprüft;
   * (c) *Basislinie,* nur T-Box: Solange die Versionslinie ein Element
     hat, gab es keinen Übergang. Seit ADR-025 entfallen, für Schema 8
     lesbar.

   Hat der Fall eine Kette des Gates, gilt nur (a): Eine Ablehnung im Fall
   lässt sich nicht durch einen Verweis umgehen. Gate-Version 3.0.0,
   P9-Schema 8.
3. **Zwei Prüfungen.** Die qualitative Prüfung der Änderungen:
   `gates.kernstand_belegen` zeigt je Modul des Kernstands den Diffstat,
   die Commits mit Datum und Betreff und was nicht committet ist, dazu
   Versionsübergang, Kern-Hashes und die bewegten Referenzwerte, mit einer
   lesbaren Sicht für den Prüfer. Das Gate rechnet den Beleg nach. Das
   Ergebnis der Regression: Das Werkzeug dafür ist noch nicht gebaut.
4. **Die Regression ist eine benannte Ausnahme, kein Ergebnis.** Bis es
   das Werkzeug gibt, trägt `abgeleitet/kern/regression.json` den Zustand
   `nicht_gefahren` mit dem Grund „Werkzeug noch nicht erstellt“. Solange
   `models.kernabnahme.REGRESSION_AUSNAHME_ERLAUBT` gilt, nimmt das Gate
   nur diese Form an, auch keinen formal vollständigen Ergebnis-Beleg, denn
   kein Werkzeug kann ihn erzeugt haben (verschärft in Prüfrunde G).
   Snapshot (Feld `ausnahmen`), Ledger, Sicht und jede Anzeige führen den
   Satz „Regression: Ausnahme — nicht gefahren, Werkzeug noch nicht
   erstellt“. Die Zeichnung von `A-K2` deckt damit nur die qualitative
   Prüfung. Zwei Tests halten Konstante und Werkzeug zusammen: Die
   Konstante kippt nicht ohne Werkzeug, und ein Werkzeug lässt sie nicht
   stehen.
5. **`dirty` sperrt die Regression, nicht die Sicht.** Die qualitative
   Prüfung zeigt nicht committete Änderungen ausdrücklich („ohne
   Commit-Beschreibung“); den sauberen Arbeitsbaum verlangt erst der echte
   Regressionsbeleg.

**Verworfen:** ohne Regression keine Abnahme, denn dann gäbe es das Gate
weiter nicht, während der Kern sich ändert. Ebenso, den Platzhalter als
bestanden zu führen: Ein gezeichneter Beleg darf nichts behaupten, was
niemand gefahren hat.

**Wer an Kern und T-Box schreibt.** In der Entwicklung des Werkzeugs darf
ein Agent im Auftrag des Maintainers eine Erweiterung der T-Box oder eine
Änderung des Kerns als Entwurf bauen. In einer laufenden Migration schreibt
kein Agent an der T-Box: Er legt den Änderungsvorschlag vor
(`gates.stand_belegen tbox`, mit der Stellungnahme des Aktuariats),
`mensch/architektur` prüft die Diffs und zeichnet `A-O1`. Für den Kern gilt
dasselbe: Der Rechenkern-Agent legt den Kernstand vor
(`gates.kernstand_belegen`), `mensch/rechenkern` zeichnet `A-K2`.

**Grenze.** Die Signaturprüfung bleibt HMAC: Wer `A-M4` zeichnet, braucht
die Schlüssel von `mensch/rechenkern` und `mensch/architektur` im Ring, um
deren Annahmen zu prüfen, und könnte mit ihnen auch zeichnen.

## Nachtrag 2026-10-01: Erstabnahme des Zielsystems, Versionslinie der Ordnung, Wurzelrolle

Entschieden und gebaut in ADR-025. Für dieses Rollenmodell ändert sich:

1. **Die Linie hat eigene Abnahmen und einen Ort dafür:** den
   Linienbereich (`linie/`, nicht eingecheckt, kein Fall). Dort zeichnen die
   vier fachlichen Linienrollen die Erstabnahme ihres Gegenstands:
   `mensch/rechenkern` den Kernstand (`A-K2`), `mensch/architektur` die
   T-Box (`A-O1`), `mensch/aktuariat` das Tarifwerk der PLV (neu: `A-T1`),
   `mensch/betrieb` den Anfangsbestand einer Ablage (neu: `A-B3`). `A-B1`
   bleibt im Fall, bis eine Auslieferung der Linie ansteht.
2. **Wege der Standabnahme.** Ein Fall zeichnet nur, was sich durch ihn
   ändert (Weg a), und verweist sonst auf die geltende Abnahme der Linie
   (Weg b). `A-M4` verlangt zusätzlich das Tarifwerk (Pflichtrolle
   `tarifwerkstand`). Weg c entfällt.
3. **Wer damals zeichnen durfte.** Die Zeichnungsordnung bekommt eine
   Versionslinie (`models.ordnungslinie`). Gezeichnet wird nur unter ihrer
   Spitze, und jede Zeichnung pinnt das Glied. Wer eine Abnahme liest, hält
   Rolle, Klasse und Gate gegen die Ordnung dieses Glieds, nicht gegen die
   heutige.
4. **Die Wurzelrolle: der Vorstand.** Die Versionslinie braucht eine
   Instanz, die Zeichnungsrechte vergibt: `mensch/vorstand`
   (`models.ordnungslinie.WURZELROLLE`). In einem Versicherer vergibt der
   Vorstand die Vollmachten und beschließt die Übernahme eines Bestands.
   Der Vorstand ist eine Rolle des Unternehmens, kein Nachfolger des
   Platzhalters; der Maintainer spielt sie im Regie-Modus wie die anderen
   simulierten Rollen. Sie hat kein Agenten-Gegenstück, denn ein Agent
   vergibt keine Zeichnungsrechte. Sie trägt `A-Z1` und keine fachliche
   Abnahme (seit ADR-026 zusätzlich `A-M6`), keine andere Rolle trägt
   `A-Z1`, und weder eine Rolle mit `gates: ["*"]` noch
   `mensch/quell-aktuar` kommen in die Linie. Ihre Wirkung endet an der
   Grenze des eigenen Hauses (ADR-025, Abschnitt 8).
5. **Gegenstücke.** `agent/betrieb` hat seine Definition
   (`.claude/agents/betrieb.md`). Jede fachliche Linienrolle hat ihr
   vorlegendes Gegenstück; ohne Gegenstück bleiben der Vorstand und
   `mensch/quell-aktuar`.

## Nachtrag 2026-10-01: Der Lebenslauf eines Falls — Fallauftrag und Fallabbruch

Entschieden und gebaut in ADR-026. Für dieses Rollenmodell ändert sich:

1. **Die Tabelle Linie/Fall bekommt ihre Gates.**

   | Rolle | Linie | Fall | Gates | Recht aus |
   |---|---|---|---|---|
   | `mensch/vorstand` | ja | nein | `A-Z1`, `A-M6` (Fallauftrag) | der Ordnung der Linie |
   | `mensch/programmleitung` | nein | ja | `A-M5` (Fallabbruch) | dem Fallauftrag |
   | `mensch/quell-aktuar` | nein | ja | keine | dem eigenen Haus (im Auftrag als Platz benannt) |

   Die Programmleitung führt durch den Prozess und nimmt nichts fachlich
   ab. Zeichnen kann sie genau einen Akt: den Abbruch ihres Falls.
2. **Woher eine Rolle ihr Recht hat.** Eine Rolle der Linie hat es aus der
   Ordnung der Linie, und zwar aus dem Stand, unter dem sie zeichnete. Eine
   Rolle des Falls hat es aus dem Fallauftrag, der die Programmleitung mit
   Rolle und Fingerabdruck benennt und ihr `A-M5` gibt.
   `models.zeichnung.zeichnende_rolle_fehler` hält beides an einer Stelle
   (`FALLROLLEN_GATES`). Eine Rolle, die erst mit dem Fall entsteht, kann
   ihr Recht nicht aus der Linie haben; sie hat es aus dem Akt, der den
   Fall entstehen lässt.
3. **Agent.** `agent/programmleitung` beginnt einen Fall nur mit einem
   geltenden Auftrag, liest ihn, zeichnet ihn nie und legt bei einem
   Abbruchkriterium die Vorlage des Fallabbruchs vor.

## Nachtrag 2026-10-01: Prüfrunde G — Regression, Verweis, Linie, lebender Stand

Die Regeln stehen ausführlich in ADR-025 (Nachtrag Prüfrunde G). Für dieses
Rollenmodell:

1. **Die Regression ist bis zu ihrem Werkzeug eine Ausnahme, nie
   „bestanden“** (G10, als Härtung gebaut auf Entscheid des Maintainers).
   Vorher wurde ein von Hand geschriebenes Ergebnis angenommen, und die
   Ausnahme verschwand aus dem signierten Snapshot. Solange die Konstante
   gilt, nimmt `A-K2` keinen Ergebnis-Beleg an. *Verworfen:* den
   Ergebnis-Beleg nachzurechnen, denn ohne Werkzeug gibt es nichts, womit.
2. **Weg b verweist nur auf die geltende Abnahme der Linie** (G11). Das
   Gate hält den verwiesenen Snapshot gegen die geltende, angenommene
   Spitze der Kette seines Gates in der Linie, mit Signaturprüfung.
   `stand_belegen verweisen --snapshot` ist entfallen. *Verworfen:* der
   Verweis auf den Snapshot eines früheren Falls, denn dessen Herkunft ist
   vom Gate aus nicht prüfbar.
3. **Wer auf der Linie gründet, prüft ihre Glieder gegen den Vorstand**
   (G09). Damit liegt der Schlüssel der Wurzelrolle in mehr Ringen als
   vorher, und die HMAC-Grenze gilt auch für ihn (ADR-025, ADR-026).
4. **Der lebende Stand ist der des Codes, der rechnet** (G12): `--repo-root`
   muss das ausgeführte Paket tragen, sonst verweigert jedes Kommando der
   Gates.

## Bewusst nicht Bestandteil

Die Modellierung simulierter Rückfragen (nächste Ausbaustufe der Regie);
eine Identitätsprüfung natürlicher Personen (der Schlüssel weist die Rolle
nach, nicht die Person, ADR-008); die Frage, ob `A-M4` eine Mitzeichnung
der Programmleitung braucht (offen).
