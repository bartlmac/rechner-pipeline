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

## Bewusst nicht Bestandteil

Die Modellierung simulierter Rueckfragen (naechste Ausbaustufe der
Regie); eine Identitaetspruefung natuerlicher Personen (der Schluessel
weist die Rolle nach, nicht die Person, ADR-008); die Frage, ob A-M4 eine
Mitzeichnung der Programmleitung braucht (offen, Fachverantwortlicher).
