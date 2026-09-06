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
Schluessel. Jede hat ein Gegenstueck unter den Agentenrollen, dazu die
Gegenseite des abgebenden Hauses.

| Kennung | Anzeige | Gegenstueck |
|---|---|---|
| `mensch/verantwortlicher-aktuar` | Verantwortlicher Aktuar | Aktuariats-Agent |
| `mensch/it-verantwortung` | IT-Verantwortung | Architektur-Agent |
| `mensch/entwicklungsverantwortung` | Entwicklungsverantwortung | Rechenkern-Agent |
| `mensch/programmleitung` | Programmleitung | Programmleitungs-Agent |
| `mensch/quell-aktuar` | Aktuar des abgebenden Hauses | keines (Gegenseite) |

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
  zugunsten der Ordnung; ohne Ordnung keine Annahme; Ablehnung durch
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

## Bewusst nicht Bestandteil

Die Modellierung simulierter Rueckfragen (naechste Ausbaustufe der
Regie); eine Identitaetspruefung natuerlicher Personen (der Schluessel
weist die Rolle nach, nicht die Person, ADR-008); die Frage, ob A-M4 eine
Mitzeichnung der Programmleitung braucht (offen, Fachverantwortlicher).
