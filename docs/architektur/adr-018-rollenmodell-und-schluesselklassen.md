# ADR-018: Rollenmodell des KI-Tools — Agenten legen vor, Menschen zeichnen, der Schluessel sagt, wer besetzt

Status: akzeptiert (Auftraggeber, 2026-09-05); ersetzt die Rollenregel des
Vier-Rollen-Modells vom 2026-09-01 und praezisiert P2 und ADR-008.

## Kontext

Bis zum zweiten Baldrian-Lauf galt: Agenten bereiten vor, "der Mensch"
entscheidet (`--rolle mensch`). Fuer den Lauf wurde daraus das
Vier-Rollen-Modell: Eine Zeichnungsordnung bindet Rollen an
Schluessel-Fingerabdruecke, und die Rolle, die den Schluessel hat,
entscheidet und zeichnet (`ontologie.entscheide`, `gates.gate_entscheid`).
Diese Rollen wurden im Lauf von KI-Sessions im Mandat besetzt und
zeichneten als Rolle "mensch".

Die Reviews T20 und U1 fanden die Folgen: P2, ADR-008, AGENTS.md und
drei Skills sagen weiter "Mensch"; der Code laesst die Schluesselrolle
entscheiden; ein Skill und ein Docstring erlauben eine Aufloesung "ohne
Menschen", die kein Code kennt; Snapshot, Ledger und Fachbericht koennen
nicht ausweisen, ob ein Mensch oder eine KI-Session gezeichnet hat; die
Rollen selbst haben im versionierten Repo keine Definition. Die Frage
"wer darf einen Quellenwiderspruch entscheiden" hatte drei Antworten.

## Entscheidung

### 1 Zwei Sorten Rollen, getrennt durch die Ebene (ADR-017)

**Agentenrollen des KI-Tools** (Ebene 2). Vier, jede mit Ziel,
Perspektive eines laufenden Unternehmens, Skills, Werkzeugen und
Schreibgrenzen; versioniert im Repo als Agentendefinitionen. Sie
arbeiten zusammen, bis ein Problem geloest ist, und legen dann vor.
Sie zeichnen NIE.

| Kennung | Anzeige | Ziel |
|---|---|---|
| `agent/aktuariat` | Aktuariats-Agent | das Unternehmen bildet nach der Migration fachlich alles richtig ab (Transformation, aktuarielle Tests, Controlling, Bestandsfortfuehrung) |
| `agent/architektur` | Architektur-Agent | die Migration arbeitet in der vorgegebenen IT-Architektur |
| `agent/rechenkern` | Rechenkern-Agent | das Zielsystem bleibt stabil: Regressionstests, Dokumentation, Kern-Abnahmeprotokoll |
| `agent/programmleitung` | Programmleitungs-Agent | die Migration wird effizient geliefert; orchestriert die drei anderen |

**Menschliche Rollen** (Funktionen des Unternehmens). Sie pruefen die
Vorlagen, stellen Rueckfragen, sehen selbst nach und zeichnen mit ihrem
Schluessel. Sie tragen DENSELBEN Namen wie die Agentenrolle, die ihnen
zuarbeitet; die Ebene steht im Praefix, nicht im Namen.

| Kennung | Anzeige |
|---|---|
| `mensch/aktuariat` | Verantwortlicher Aktuar |
| `mensch/architektur` | IT-Verantwortung |
| `mensch/rechenkern` | Rechenkern-Verantwortung |
| `mensch/betrieb` | Betriebsverantwortung |
| `mensch/programmleitung` | Programmleitung |
| `mensch/quell-aktuar` | Aktuar des abgebenden Hauses |

**Entscheid des Maintainers 2026-09-16: gleiche Namen auf beiden Ebenen.**
Zuvor hiessen die menschlichen Rollen nach ihrer Verantwortung
(`verantwortlicher-aktuar`, `it-verantwortung`, `entwicklungsverantwortung`,
`betriebsverantwortung`), die Agentenrollen nach ihrem Fachgebiet
(`aktuariat`, `architektur`, `rechenkern`, `betrieb`). Die Paare waren
nicht ablesbar, die Tabelle brauchte dafuer eine eigene Spalte
"Gegenstueck". Jetzt traegt die Kennung das Fachgebiet und das Praefix die
Ebene: `agent/rechenkern` legt vor, `mensch/rechenkern` zeichnet. Die
Spalte entfaellt, weil der Name die Paarung IST — dasselbe Prinzip, das
bei der Simulation schon galt ("die Rollenkennung bleibt dieselbe wie in
der Wirklichkeit"), eine Ebene hoeher angewandt. Der gesetzliche Titel
geht dabei nicht verloren: Die Kennung ist `mensch/aktuariat`, angezeigt
wird "Verantwortlicher Aktuar". `mensch/quell-aktuar` behaelt seinen
Namen, er hat als Gegenseite kein Agenten-Gegenstueck.

Die bisherigen Kennungen `plv-aktuar`, `plv-va`, `quelle-experte`,
`programmleiter` und der Platzhalter `mensch` entfallen; die Vorzeige
bildet sie auf die neuen ab. Wer zeichnet, ist eine Funktion; wer
vorbereitet, ist ein Agent; wie der Schluessel besetzt war, steht im
Snapshot.

### 2 Schluesselklassen

Die Zeichnungsordnung traegt je Rolle eine **Schluesselklasse**:

| Klasse | Bedeutung | Darf zeichnen |
|---|---|---|
| `mensch` | ein Schluessel in der Hand einer natuerlichen Person | ja |
| `simulation` | ein Schluessel, mit dem die Vorzeige eine menschliche Rolle nachahmt | ja, und jeder Beleg sagt es |
| `agent` | ein Schluessel einer Agentenrolle | nein; er weist die Herkunft einer Vorlage aus |

Die Rollenkennung bleibt bei Simulation dieselbe wie in der Wirklichkeit;
nur die Klasse wechselt. Ein Bericht schreibt "gezeichnet:
Verantwortlicher Aktuar, Schluessel: Simulation". Ein Agentenschluessel
an einem Annahme-Snapshot ist ein Fehler, kein Sonderfall.

### 3 Der Snapshot traegt die Besetzung

Jeder P9-Snapshot und jede endgueltige Diskrepanz-Entscheidung tragen
unter `zeichnung` die Rolle (aus dem Schluessel bestimmt, wie bisher),
die Schluesselklasse und bei Simulation den Hinweis auf das Mandat, unter
dem die simulierte Rolle handelte (Hash des Mandatsdokuments). Damit ist
aus dem signierten Beleg allein ableitbar, welche Rolle wie besetzt war
(U1, Klasse K1).

### 4 Auflösung von Widerspruechen: Option a

Der Abzugsabgleich ist ausschliesslich Beleg-Erzeuger. Eine Diskrepanz
loest nie eine Maschine endgueltig auf; die Formulierung "die Aufloesung
darf OHNE Menschen erfolgen" in Skill und Modul-Docstring war Drift und
wird gestrichen. P2 bleibt: Agenten loesen ausschliesslich vorlaeufig auf,
die endgueltige Aufloesung zeichnet eine menschliche Rolle — in der
Vorzeige mit Simulationsschluessel.

### 5 Der zweite Baldrian-Lauf ist eine ausgewiesene Ausnahme

Seine sechzehn Snapshots wurden von KI-Sessions im Mandat unter der
Rolle "mensch" gezeichnet, mit dem Simulationsschluessel, bevor es die
Klasse dafuer gab. Sie bleiben gueltig und gepinnt; nichts wird
nachsigniert. Fachbericht und Fall-Seite weisen aus, dass die
zeichnenden Rollen KI-besetzt waren und der Schluessel ein
Simulationsschluessel ist. Neue Faelle laufen unter diesem ADR.

## Konsequenzen

- `models.zeichnung`: Ordnung Schema 2 mit `schluesselklasse` und den
  neuen Kennungen; `agent`-Rollen ohne Gate-Berechtigung; die alten
  Kennungen werden mit Meldung abgewiesen, nicht still gemappt.
- `gates.gate_entscheid` und `ontologie.entscheide`: `--rolle` entfaellt
  zugunsten der Ordnung; ohne Ordnung keine Annahme; bei Schluesselklasse
  `simulation` ist `--mandat` PFLICHT — Gate, Entscheidungskommando und
  das Snapshot-Schema selbst verweigern eine simulierte Zeichnung ohne
  Mandats-Hash (Review T22-07: "optional, empfohlen" hatte die
  zentrale Aussage dieses ADR nicht durchgesetzt); Ablehnung durch
  Agentenrollen bleibt moeglich (ADR-008, Punkt 6). Snapshot- und
  Entscheidungs-Schema um Besetzung und Mandat; bricht das
  Snapshot-Schema (Version 7), Altsnapshots bleiben lesbar.
- Skills und AGENTS.md werden auf die Rollen nachgezogen; die vier
  Agentenrollen entstehen als Definitionen unter `.claude/agents/` mit
  Paritaet in `.agents/` (test-tragend wie die Skills).
- Renderer (Fachbericht, Fall-Seite, Fachspez) zeigen Rolle und Klasse;
  "gezeichnet" nur mit verifizierter Signatur (T20-02).
- Die Regie der Vorzeige (Ebene 4, ADR-017) haelt die Auftragsprofile
  der simulierten Menschen und erzeugt deren Mandate; die Auftragsprofile
  der Agentenrollen sind Tool und liegen im Repo.

## Nachtrag 2026-09-16: Die Betriebsrolle, und zwei Sorten Rollen

Das Rollenmodell hatte eine Luecke, die sich im Betrieb immer wieder
gemeldet hat: **Wer verantwortet die Bestandsfuehrung?** Vier
Agentenrollen und fuenf menschliche — und keine davon fuer das, was nach
der Migration JEDEN TAG laeuft. Die Frage fiel deshalb abwechselnd der
IT-Verantwortung und dem Verantwortlichen Aktuar zu, und beides war
falsch: Der eine betreibt die Maschine, der andere verantwortet die
Rechnung; den Bestand fuehrt keiner von beiden.

Neu, als fuenfte Agentenrolle und sechste menschliche:

| Kennung | Anzeige |
|---|---|
| `agent/betrieb` | Betriebs-Agent |
| `mensch/betrieb` | Betriebsverantwortung |

Die Betriebsverantwortung ist eine **fachliche** Rolle mit
Kundenservice-Verantwortung, nicht die IT: Sie verantwortet, was dem
Versicherungsnehmer gegenueber gilt, nicht den Rechner, auf dem es
entsteht. Sie zeichnet die Auslieferung (`A-B1`).

### Linie und Fall — zwei Sorten Rollen

Dabei faellt eine Unterscheidung auf, die das Modell bisher gar nicht
kannte. Das Unternehmen tut ZWEIERLEI: Es fuehrt einen Bestand (Linie,
taeglich, fallunabhaengig) und es migriert (Projekt, je Fall, endlich).

| Rolle | Linie | Fall |
|---|---|---|
| `mensch/betrieb` | ja | ja |
| `mensch/aktuariat` | ja | ja |
| `mensch/rechenkern` | ja | ja |
| `mensch/architektur` | ja | ja |
| `mensch/programmleitung` | nein | ja |
| `mensch/quell-aktuar` | nein | ja |

Die ersten vier gibt es, solange es das Unternehmen gibt. Die
Programmleitung entsteht mit einem Fall und endet mit ihm; der Aktuar
des abgebenden Hauses ohnehin. Das ist keine Feinheit: Eine Fallrolle
hat im Tagesbetrieb nichts zu zeichnen, und eine Linienrolle zeichnet
Dinge, die kein Fall abdeckt — die Auslieferung des laufenden Bestands
ist genau so ein Ding.

**Offen und ausdruecklich benannt:** `A-B1.auslieferung` ist eine
LINIEN-Abnahme, ihr Snapshot liegt aber heute im FALL
(`<fall>/entscheide/`), weil das Entscheid-Kommando keinen anderen Ort
kennt. Solange eine Laufzeitumgebung genau einen Fall traegt, faellt das
nicht auf; sobald sie mehrere traegt, ist nicht mehr bestimmt, in welchen
Fall die Auslieferung des Gesamtbestands gehoert. Der Ausweg waere ein
Entscheidungsraum der ABLAGE neben dem des Falls. Das ist eine eigene
Entscheidung und hier nur festgehalten, nicht getroffen.

**Dieselbe Bauform ein zweites Mal: `A-O1`.** Das Register nennt sie
"Tarifgeneration", ihr Belegvertrag verlangt seit Review T22-02 aber eine
T-Box-Aenderung (`fall.py`, `BELEGROLLEN["A-O1"]`), und zwar
scope-unabhaengig — "weil eine T-Box-Aenderung das Vokabular aller Faelle
betrifft". Damit zeichnet A-O1 heute zwei verschiedene Dinge unter einem
Namen: eine Tarifgeneration (Anlass Fall, Geltung Fall) und eine
Erweiterung des Vokabulars (Anlass Fall, Geltung LINIE).

Die Aufloesung der scheinbaren Inkonsequenz — "eine T-Box definiert man
fuer einen Fall" gegen "das Vokabular aller Faelle" — ist die
Unterscheidung dieses Abschnitts: **Anlass ist der Fall, Geltung ist die
Linie.** Niemand erfindet eine T-Box; sie waechst, weil ein Fall eine
Frage erzwingt (Baldrian liefert `RK`, die Ziel-Ontologie kennt kein
Raucherkennzeichen). Ist die Erweiterung abgenommen, erbt der naechste
Fall sie, ohne gefragt zu haben — deshalb wird die T-Box-Version
laufuebergreifend verglichen, was bei Fall-Eigentum sinnlos waere.
Dasselbe Muster traegt der Rechenkern: veranlasst durch einen Fall,
verantwortet von der Linie.

**Entschieden am 2026-09-16, nachdem die Frage gestellt war:** `A-O1`
zerfaellt nicht, aber der Rechenkern bekommt eine eigene Abnahme. Neu ist
`A-K2.kernaenderung`, gezeichnet von `mensch/rechenkern`; sie nimmt die
Aenderung an Code und Dokumentation des Rechenkerns ab. Sie ist eine
FALL-Abnahme: Kernaenderungen entstehen heute nur im Fall, und die
spaeteren Anlaesse — Produkteinfuehrung, regulatorische Aenderung — haben
denselben Charakter. Damit bleibt die Linie ohne eigene Abnahme, und die
Frage nach dem Ort der Linien-Snapshots betrifft nur noch `A-B1`.

Zugleich bekommt die T-Box ihren eigenen Gegenstand: `A-K1` heisst
jetzt `A-O1.tbox-aenderung` und liegt nicht mehr unter `K` (Rechenkern),
womit sie nichts zu tun hat. Gezeichnet wird sie von
`mensch/architektur` — wer verantwortet, welche Begriffe das Zielsystem
fuehrt, verantwortet sein Datenmodell. Die fachliche Seite der Frage
gehoert dagegen dem Aktuariat, und deshalb verlangt der Belegvertrag
zusaetzlich dessen Stellungnahme je betroffenem Feld. Dasselbe Muster
wie bei `A-B1`: Die Unterschrift gehoert einer Rolle, der Beleg kommt
aus einer anderen; eine Doppelunterschrift kennt das System nicht, denn
geteilte Verantwortung ist keine.

`A-K2` traegt `regression` als PFLICHTbeleg. Das ist die eigentliche
Entscheidung dahinter: Der geaenderte Kern bewertet nach der Migration
den LAUFENDEN Bestand weiter, und diese Wirkung sieht sonst niemand. Der
Beleg rechnet jeden Vertrag mit altem und neuem Kern durch und weist die
Differenz je Vertrag aus — kein Aggregat, denn gegenlaeufige
Abweichungen heben sich in der Summe auf, und keine Stichprobe, denn der
Fehler, der einen von tausend Vertraegen trifft, ist der gesuchte.

**Nicht Teil des Rollenmodells ist der Maintainer** dieses Repos. Er
gehoert zur Entwicklungsumgebung des Werkzeugs, nicht zum Unternehmen,
das damit arbeitet — der Platzhalter `mensch` mit `gates: ["*"]` entfaellt
wie in Abschnitt 1 angekuendigt und bekommt keinen Nachfolger.

## Nachtrag 2026-09-16: Agenten zeichnen keine ABNAHME

Die Regel hiess "Agentenrollen legen vor und zeichnen nie". Das war eine
Haelfte zu viel.

Schuetzenswert ist die **Abnahme** — die Aussage eines Menschen, dass er
fuer etwas einsteht. Nicht schuetzenswert in diesem Sinn ist jede
Signatur: Ein Agent, der einen Ankersatz zeichnet, sagt "ich habe dieses
Paket erzeugt". Das ist eine Aussage ueber URHEBERSCHAFT, keine Abnahme,
und sein Beleg traegt die Klasse `agent` — genau dafuer wurde die Klasse
eingefuehrt (T20/U1: aus keinem Beleg war ablesbar, ob ein Mensch oder
eine KI-Session gezeichnet hatte). Wer die Klasse liest, wird nicht
getaeuscht; das Verbot war die zweite, staerkere Absicherung, und sie
passt nicht mehr, seit Agentenrollen untereinander Pakete uebergeben.

Praezisiert gilt also:

* Eine Agentenrolle zeichnet **keine Abnahme**. Ihre `gates`-Liste bleibt
  leer, und der Validator erzwingt das unveraendert — was ein Agent
  zeichnet, ist kein Gate.
* Eine Agentenrolle **darf** einen Satz zeichnen, der keine Abnahme ist
  (heute: den Ankersatz eines Stands-Pakets, `models.anker`).
* Die Abnahmen bleiben `mensch` und `simulation` vorbehalten.

**Der praktische Grund** (Entscheid des Maintainers 2026-09-16): Bei
vielen kleinen Migrationstranchen mit taeglichen Exporten kann kein
Mensch jeden Export zeichnen. Ein Agent kann es, und der Beleg sagt, dass
es einer war. Der Mensch zeichnet dort, wo etwas nach AUSSEN geht —
einmal je Auslieferung, ueber die neue Abnahme `A-B1.auslieferung`.

**Verworfen: ein zweiter, eigener Signaturmechanismus** nur fuer
Urheberschaft. Zwei Mechanismen waeren zwei Wahrheiten ueber dasselbe;
wer prueft, muesste beide kennen und wissen, welcher wo gilt. Dieselbe
Doppelung hat Review T25-06 in anderer Gestalt gekostet.

## Nachtrag 2026-09-30: Schluesselklasse betrieb

Die Pruefrunde nach T27 (Runde C) fand den Kern der Betriebsbefunde an
einer Stelle: **Der Tagesbetrieb hatte keinen Zeugen ausser sich selbst.**
Wer die Ablage beschreiben konnte, schrieb Protokoll und Eingaenge stimmig
um — eine auf Schema 1 herabgestufte Zeile, eine zweite gruene Zeile fuer
denselben Tag, Kennzahlen, Herkunft und Uebernahmeangaben der letzten
Zeile, ein Eingang nach seinem Eintritt. Jede Pruefung las nur, was
derselbe Schreiber hinterlassen hatte.

Entscheid des Maintainers: Der Betrieb bekommt einen Schluessel **genau
wie die vorhandenen Rollen** — Schluesseldatei beim Menschen, ausserhalb
der Ablage (0600, ein Hardlink, 32 bis 4096 Byte); Fingerabdruck in der
Zeichnungsordnung; HMAC-Zeichnung nach `models.anker` (Verfahren
`hmac-sha256-v2`). Neu ist nur die Rolle:

* Ebene und Klasse `betrieb` (`betrieb/tageslauf`, Schluesselklasse
  `betrieb`). Ebene und Klasse gehoeren zusammen; eine Rolle
  `mensch/...` mit Klasse `betrieb` oder umgekehrt weist die Ordnung ab.
* Die `gates`-Liste ist leer, wie die eines Agenten. `betrieb` steht NICHT
  unter den zeichnenden Klassen; kein P9-Snapshot nimmt sie an.

**Der Grund fuer eine eigene Klasse:** Ein Programm, das Protokollzeilen
und Eingaenge zeichnet, ist weder `mensch` noch `simulation` noch
`agent`. Es steht fuer niemanden ein und legt nichts vor; es bezeugt,
dass es diese Zeile geschrieben hat. Es zeichnet Urheberschaft, nie ein
Gate. Unter einer der vorhandenen Klassen hiesse jede Protokollzeile "ein
Mensch hat das gezeichnet" oder "ein Agent hat das vorgelegt" — genau die
Verwechslung, gegen die die Klassen eingefuehrt wurden.

Was gezeichnet wird: jede Zeile des Tagesprotokolls (Schema 3) und jede
`eingang.json` bei der Registrierung (Schema 3, ueber alle Felder samt
A-M4-Zeichnungsblock). Ohne Betriebsschluessel laeuft kein Tag, wird
nichts registriert und nichts exportiert; ein Menschen- oder
Agentenschluessel wird mit Ausweg abgewiesen. Wer keinen Schluessel haelt
(der Konsument eines Stands-Pakets), prueft Form, Kette und Vorlauf und
sagt, dass die Signatur fuer ihn nicht pruefbar ist.

Dies nimmt eine fruehere Abwaegung zurueck: `models.anker` hatte die
Zeichnung jeder Zeile beim Lauf verworfen, weil sie einen Schluessel in
einen unbeaufsichtigten Nachtlauf legt. Das bleibt wahr — der Schluessel
liegt jetzt dort, lesend eingebunden. Die Runde C hat gezeigt, dass der
Lauf ohne ihn nichts bezeugt, was ein zweiter Schreiber nicht ebenso
bezeugen koennte. Der Anker bleibt der Bezug nach aussen; die Zeichnung
bindet jede Zeile, auch die, die noch nie verankert wurde.

Bestehende Ablagen werden **aufgeschaltet**, nicht neu aufgesetzt: Die
erste gezeichnete Zeile pinnt den ungezeichneten Vorlauf (Zahl und Hash
der rohen Zeilen). Aufgeschaltet wird nur **ausdruecklich und einmal**
(`tageslauf --aufschalten`, Bibliothek `aufschalten=True`), beim ersten
Lauf nach dem Umstieg. Der Grund (Pruefer der Nachbesserung): Ein
Protokoll ohne gezeichnete Zeile ist aus der Ablage allein nicht von
einem gezeichneten zu unterscheiden, das ein Schreiber ohne Schluessel
herabgestuft hat (Zeichnungen und Pin entfernt, Zahlen gefaelscht, Kette
neu verkettet) — die erste Fassung pinnte eine solche Geschichte still und
zeichnete sie damit. Deshalb gilt:

* Traegt das Protokoll Zeilen, aber keine gezeichnete, verweigern
  Tageslauf, Export und Neuaufsetzen (Exit 2) und nennen beide Lesarten:
  Altbestand -> einmal `--aufschalten`; schon gezeichnet gewesen ->
  Kettenbruch, das Protokoll aus der Sicherung wiederherstellen.
  Aufschalten kann nur der Tageslauf (und das Neuaufsetzen, das die alte
  Ablage archiviert); der Export nie.
* `--aufschalten` auf ein gezeichnetes oder leeres Protokoll wird
  **verweigert**, nicht still uebergangen: Ein Schalter, der dauerhaft im
  Timer stuende, oeffnete die Herabstufung wieder.
* Ist ein gezeichnetes Protokoll spaeter wieder ohne gezeichnete Zeile,
  ist das ein Kettenbruch, kein zweiter Aufschaltfall. Die Ablage sieht
  das nicht; den Bezug nach aussen liefert der Anker: Die Zeile, die der
  letzte Export verankert hat, steht dann nicht mehr im Protokoll, und der
  naechste Export verweigert. Zwischen Aufschaltung und erstem Export
  schuetzt nur die Entscheidung des Menschen.

**Zeugen** eines Eingangs sind nur gebundene Zeilen: eine gezeichnete
Zeile (Schema 3) oder eine Zeile des gepinnten Vorlaufs. Ein Protokoll
ohne gezeichnete Zeile bezeugt nichts — ausser im Lauf, der es mit
`--aufschalten` uebernimmt und dessen erste Zeile genau diesen Vorlauf
pinnt. Ein ungezeichneter Eingang (Schema 2) tritt nur ein, wenn eine
gezeichnete Protokollzeile oder der gepinnte Vorlauf ihn bezeugt; neu
eintreten kann er nicht.

**Offen: Schluesselwechsel.** Der Tageslauf prueft mit einem Ring aus
genau dem aktuellen Betriebsschluessel. Wird der Schluessel ersetzt, sind
die alten Zeilen fuer ihn "nicht pruefbar" — im Betrieb ein harter
Befund, der Tag laeuft nicht. Naechster Schritt, wie bei den
Freigabeschluesseln: eine Zeichnungsordnung mit abgeloesten Rollen und
ein Ring aus mehreren Schluesseln, gegen den die alten Zeilen weiter
geprueft werden, waehrend nur der aktuelle zeichnet. Bis dahin ist der
Weg bei einem Wechsel das Neuaufsetzen (es rechnet die Signatur der alten
Ablage nicht nach und archiviert sie).

Zukunft (ausdruecklich nicht Teil dieses Nachtrags): Der Betrieb soll wie
die Linie eine Agenten- und eine Menschenrolle bekommen, um
Migrationszugang und Controllingvorgang zu verifizieren, auch im
Regie-Modus.

## Nachtrag 2026-10-01: Der Stand des Falls ist abgenommen — A-K2 und A-O1

**Befund.** `A-K2.kernaenderung` (Nachtrag 2026-09-16) stand im
Entscheid-Kommando, im Belegvertrag und in der Ordnung, war aber
unwirksam: Es gab keinen Produzenten fuer die beiden Belege, kein Gate
verlangte A-K2, und kein Ablauf nannte es. Der obige Satz "Kernaenderungen
entstehen heute nur im Fall" traf nicht zu: Der Rechenkern ist ausserhalb
jedes Falls von Version 3.6.0 (`origin/main`) auf 3.15.0 gewachsen — neun
Minor-Versionen ohne eine einzige Abnahme.

**Entscheid des Maintainers.** "Zeichnung Rechenkernentwickler — wir
sollten dieses Gate formell einpflegen, in den Prozess, die Dokumentation
und die Vorzeige." Zeitpunkt: vor dem Merge.

1. **Gegenstand ist der Kernstand, auf dem ein Fall rechnet** —
   einschliesslich der Aenderungen, die ausserhalb eines Falls entstanden
   sind. Damit loest sich der Widerspruch oben: A-K2 ist keine Abnahme
   einer Aenderung, die im Fall entsteht, sondern die Abnahme des Stands,
   den der Fall benutzt; vorgelegt mit `--von` = dem zuletzt abgenommenen
   Kernstand. Die Pfadmenge "Code und Dokumentation des Rechenkerns" steht
   einmal in `models.kernabnahme.KERNSTAND`: das Paket `kern/`
   (einschliesslich der Rechnungsgrundlagen), die eingefrorenen
   Referenzwerte, die Grundsatzdokumentation und die Tarifplaene — nicht
   der Zweitkern (ADR-013), nicht die Parametrierung (ADR-006), nicht die
   Schichten, die den Kern benutzen.
2. **EINE Regel fuer zwei Gegenstaende** (zweiter Entscheid desselben
   Tages: "T-Box-Erweiterung muss auch ein Abnahmepunkt im Prozess sein,
   wird bei 'keiner Aenderung' durchgewunken (da keine Aenderung
   vorhanden)"). A-M4 verlangt in beiden Scopes, dass der Stand, auf dem
   der Fall laeuft, abgenommen ist — fuer den **Kernstand** (A-K2,
   `mensch/rechenkern`, Pflichtrolle `kernstand`) und den
   **T-Box-Stand** (A-O1, `mensch/architektur`, Pflichtrolle
   `tboxstand`), nach derselben Funktion (`models.standabnahme`,
   `gate_entscheid.standabnahme_pruefen`). Erfuellt auf genau einem Weg:
   (a) *abgenommen im Fall* — eine eindeutige, signierte Annahme im Fall
   auf demselben Scope- und Systemstand, gezeichnet von einer Rolle, der
   die Ordnung das Gate gibt (`models.zeichnung.zeichnende_rolle_fehler`),
   ihre Belege am festen Ort und gegen den lebenden Code nachgerechnet;
   (b) *keine Aenderung* — der Stand ist identisch zu dem, den ein FRUEHER
   angenommener Snapshot abgenommen hat: Ein Verweis am festen Ort
   (`abgeleitet/kern/verweis.json` bzw. `abgeleitet/tbox/verweis.json`,
   Produzent `gates.stand_belegen verweisen`) traegt die vollstaendige,
   signierte Kopie dieses Snapshots; A-M4 prueft Signatur, Rolle und Klasse
   nach derselben Regel und haelt sein Feld `stand` per `==` gegen den
   lebenden (Kern: Version, Sammelhash des Kernpakets, der Referenzwerte
   und der ganzen Pfadmenge; T-Box: Version und SHA-256 des Moduls). Kein
   neuer Entscheid; der A-M4-Snapshot fuehrt woertlich "keine Aenderung
   seit Abnahme <snapshot> (<Herkunft>)" — durchgewunken heisst belegt
   unveraendert, nicht ungeprueft; (c) *Basislinie*, nur T-Box: Solange
   die Versionslinie ein Element hat, gab es keinen Uebergang. Fuer den
   Kern gibt es keine Basislinie — seine erste Abnahme ist zu zeichnen.
   Hat der Fall eine Kette des Gates, gilt nur (a): Eine Ablehnung im Fall
   laesst sich nicht durch einen Verweis umgehen. Die Snapshots von A-K2
   und A-O1 tragen dafuer den abgenommenen `stand`, der A-M4-Snapshot die
   `standabnahmen` (Weg und Anzeige je Gegenstand). Gate-Version 3.0.0,
   P9-Schema 8 (Major: ein vorher gruener A-M4-Entscheid wird ohne
   abgenommenen Kernstand rot).
3. **Zwei Pruefungen.** (1) Die *qualitative Pruefung der Aenderungen*:
   `gates.kernstand_belegen` zeigt je Modul des Kernstands den Diffstat
   gegen den Arbeitsbaum, die Commits des Zweigs mit Datum und
   Betreffzeile als Kurzbeschreibung und was nicht committet ist, dazu
   Versionsuebergang, beide Kern-Hashes und die bewegten Referenzwerte;
   daneben eine lesbare Sicht fuer den Pruefer. Das Gate rechnet den Beleg
   nach, statt ihm zu glauben. (2) Das *Ergebnis der Regression*: Das
   Werkzeug ist noch nicht gebaut.
4. **Die Regression ist eine benannte Ausnahme, kein Ergebnis.** Bis zum
   Produzenten traegt `abgeleitet/kern/regression.json` den Zustand
   `nicht_gefahren` mit dem Grund "Werkzeug noch nicht erstellt" — kein
   Feld, das wie ein Ergebnis aussieht. Das Gate nimmt genau diese Form an,
   solange `models.kernabnahme.REGRESSION_AUSNAHME_ERLAUBT` gilt, und
   nichts anderes Unvollstaendiges; ein echter Regressionsbeleg wird nach
   der Regel vom 2026-09-16 geprueft (jeder Vertrag, Differenz je Vertrag,
   sauberer Arbeitsbaum). Snapshot (Feld `ausnahmen`), Ledger, Sicht und
   jede Anzeige fuehren den Satz woertlich: "Regression: Ausnahme — nicht
   gefahren, Werkzeug noch nicht erstellt". Die Zeichnung von A-K2 deckt
   damit ausdruecklich NUR die qualitative Pruefung. Zwei Waechter halten
   Konstante und Produzent zusammen: Die Konstante kippt nicht, solange es
   keinen Produzenten gibt, und ein Produzent laesst sie nicht stehen.
5. **`dirty` sperrt die Regression, nicht die Sicht.** Bis hierher sperrte
   ein nicht committeter Arbeitsbaum den Aenderungsbeleg, begruendet mit
   der Reproduzierbarkeit der Regression. Die Regel steht jetzt beim
   echten Regressionsbeleg; die qualitative Pruefung zeigt nicht
   committete Aenderungen ausdruecklich ("ohne Commit-Beschreibung").

**Verworfene Alternativen.**

* *Ohne Regression keine Abnahme* (Entscheid vom 2026-09-16): verworfen
  fuer jetzt. Das Gate gaebe es sonst weiter nicht, waehrend der Kern sich
  aendert — das ist genau die Lage, die zu diesem Nachtrag gefuehrt hat.
  Die Regel bleibt fuer jeden echten Regressionsbeleg in Kraft und gilt
  wieder vollstaendig, sobald die Konstante kippt.
* *Den Platzhalter als bestanden fuehren*: verworfen. Ein gezeichneter
  Beleg darf nichts behaupten, was niemand gefahren hat; ein
  `vertraege_geprueft == vertraege_gesamt` mit Nullen saehe aus wie ein
  Ergebnis und wuerde von jedem Leser als eines gelesen.

**Wer an Kern und T-Box schreibt.** In der ENTWICKLUNG der Loesung
darf ein Agent unter Auftrag des Maintainers eine Erweiterung der T-Box
oder eine Aenderung des Kerns als Entwurf im Arbeitsbaum bauen. In der
LAUFZEIT einer Migration schreibt kein Agent an der T-Box: Er legt den
Aenderungsvorschlag vor (`gates.stand_belegen tbox`, die aktuarielle
Stellungnahme vom Aktuariat), `mensch/architektur` prueft die Diffs und
zeichnet A-O1 — im Regie-Modus die simulierte Rolle unter Mandat. Fuer
den Kern gilt sinngemaess dasselbe: Der Rechenkern-Agent legt den
Kernstand vor (`gates.kernstand_belegen`), `mensch/rechenkern`
zeichnet A-K2.

**Grenze.** Die Signaturpruefung bleibt HMAC: Wer A-M4 zeichnet, braucht
die Schluessel von `mensch/rechenkern` und `mensch/architektur` im
Ring, um die A-K2- und A-O1-Annahmen (im Fall oder im Verweis) zu
pruefen — dieselbe Grenze wie bei A-B2 und A-M4 (Abschnitt
"zeichnende_rolle_fehler", models.zeichnung).

## Nachtrag 2026-10-01: Erstabnahme des Zielsystems, Versionslinie der Ordnung, Wurzelrolle

Entschieden und gebaut in ADR-025 (Befund des Maintainers: "Entweder gibt
es eine Initialzeichnung an allen relevanten Zustaenden oder gar nicht").
Fuer dieses Rollenmodell aendert sich:

1. **Die Linie hat eigene Abnahmen, und einen Ort dafuer.** Die offene
   Frage nach dem "Ort der Linien-Snapshots" (Nachtrag 2026-09-16) ist
   beantwortet: der Linienbereich (`linie/`, gitignored, kein Fall), in
   dem dieselbe Mechanik zeichnet. Dort zeichnen die vier fachlichen
   Linienrollen die Erstabnahme ihres Gegenstands — `mensch/rechenkern`
   den Kernstand (A-K2), `mensch/architektur` die T-Box (A-O1),
   `mensch/aktuariat` das Tarifwerk der PLV (neu: A-T1), `mensch/betrieb`
   den Anfangsbestand einer Ablage (neu: A-B3). Der Satz oben "Damit bleibt
   die Linie ohne eigene Abnahme" gilt nicht mehr; `A-B1` bleibt, wo es
   ist, bis eine Auslieferung der Linie ansteht.
2. **Wege der Standabnahme.** Ein Fall zeichnet nur, was sich durch ihn
   aendert (Weg a), und verweist sonst auf die geltende Abnahme der Linie
   (Weg b); A-M4 verlangt dazu das Tarifwerk (Pflichtrolle
   `tarifwerkstand`). Weg (c), die Basislinie der T-Box, entfaellt (fuer
   Schema 8 lesbar).
3. **Wer durfte damals zeichnen.** Die Zeichnungsordnung bekommt eine
   Versionslinie im Linienbereich (`models.ordnungslinie`). Mit Linie wird
   nur unter ihrer Spitze gezeichnet, und jede Zeichnung pinnt das Glied;
   wer eine Abnahme liest, haelt Rolle, Klasse und Gate gegen die Ordnung
   DIESES Glieds, nicht gegen die heutige. Die Regel aus dem Nachtrag zur
   Rollenregel ("die Rolle ist die des Schluessels") gilt unveraendert —
   nur der Stand der Ordnung, gegen den sie gehalten wird, ist jetzt der
   der Zeichnung.
4. **Die Wurzelrolle: der Vorstand.** Die Versionslinie braucht eine
   Instanz, die Zeichnungsrechte vergibt: `mensch/vorstand` (Anzeige
   "Vorstand"; `models.ordnungslinie.WURZELROLLE`). In einem Versicherer
   vergibt der Vorstand die Vollmachten und beschliesst die Uebernahme eines
   Bestands. Der Satz oben ("Nicht Teil des Rollenmodells ist der Maintainer
   dieses Repos ...") bleibt WAHR: Die Wurzel ist eine Rolle des
   Unternehmens, kein Nachfolger des Platzhalters; der Maintainer spielt sie
   im Regie-Modus wie die anderen simulierten Rollen. Sie ist eine Rolle der
   Linie ohne Agenten-Gegenstueck (ein Agent vergibt keine
   Zeichnungsrechte), traegt genau `A-Z1` und keine fachliche Abnahme, keine
   andere Rolle traegt `A-Z1`, eine Ordnung mit `gates: ["*"]` und eine Rolle
   des abgebenden Hauses (`mensch/quell-aktuar`) kommen nicht in die Linie.
   Ihre Wirkung ist unbegrenzt innerhalb des eigenen Hauses und endet an der
   Hausgrenze (ADR-025, Abschnitt 8).
5. **Paritaet.** `agent/betrieb` hat seine Definition
   (`.claude/agents/betrieb.md`): Jede fachliche Linienrolle hat ihr
   vorlegendes Gegenstueck; ohne Gegenstueck bleiben begruendet der
   Vorstand und `mensch/quell-aktuar`.

## Bewusst nicht Bestandteil

Die Modellierung simulierter Rueckfragen (naechste Ausbaustufe der
Regie); eine Identitaetspruefung natuerlicher Personen (der Schluessel
weist die Rolle nach, nicht die Person, ADR-008); die Frage, ob A-M4 eine
Mitzeichnung der Programmleitung braucht (offen, Fachverantwortlicher).
