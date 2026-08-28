# ADR-010: Aktuarieller Test und Migrationscontrolling sind getrennte Gates

Status: angenommen und umgesetzt (Beschluss Auftraggeber 2026-08-26 zu den
Punkten E3 und E4 des Migrationskonzepts; Umsetzung 2026-08-26:
`qa.aktuarieller_test`, `gates.aktuartest`, Gate A-M1 in P9 mit
erzwungener Reihenfolge vor A-M4, Belegrollen je Gate)

Normative Referenz: **Grundsatzdokumentation**
(`docs/mathematik/grundsatzdokumentation.md`), Abschnitt 9.15 — die
Trennung der beiden Pruefebenen und die Toleranzform. Dieses ADR
instanziiert sie in unserer Gate-Architektur; es definiert nichts
fachlich neu.

*Zur Herkunft:* Bei Beschluss dieses ADR lag die Methode als Fachkonzept
„Konstruktive Neuberechnung und Korrekturschicht" v0.2 vor (Kapitel
6.1-6.3). Dieses Dokument ist seither vollstaendig in die
Grundsatzdokumentation aufgenommen; die Verweise unten sind entsprechend
umgestellt.

## Kontext

Die Grundsatzdokumentation trennt in 9.15 zwei Pruefebenen mit unterschiedlichem Zeitbezug, Gegenstand
und Verantwortlichem:

* **Migrationscontrolling** misst am Migrationsstichtag $t_0$ gegen die
  Bilanz: Vollstaendigkeit, Ueberleitung, Deckungskapital- und
  ZZR-Summen je Bestandsgruppe. Voller Bestand, aggregierend.
  Verantwortung: Migrationsprojekt.
* **Aktuarieller Test** misst am Verankerungszeitpunkt $t_a$ gegen die
  Methode: Verteilung des Residuums, geclustert nach Historientyp,
  Ausreisseranalyse, Floor-Pruefungen. $t_a$ ist **je Vertrag verschieden**
  (Grundsatzdokumentation 9.12). Verantwortung: Aktuariat / Verantwortlicher Aktuar.

Unsere heutige Abnahme vermischt beides. `qa.migrationssuite` vergleicht je
Vertrag gegen **ein** Stichtagspaar, das fuer die ganze Suite gilt,
aggregiert zu einem Suite-Urteil und meldet jeden ungeprueften Vertrag als
Pruefluecke; `gates.abnahmebericht` rendert daraus eine einzige
Entscheidungsvorlage fuer ein einziges menschliches Gate. ADR-009 hat diese
Vermischung sogar festgeschrieben, indem die Scope-Bindung genau zwei
chronologische Stichtage fuer die gesamte Suite erzwingt.

Das ist als Controlling richtig und als aktuarieller Test unbrauchbar.

## Entscheidung

### 1. Zwei deterministische Gates, zwei Berichte, zwei Ledger

Der aktuarielle Test bekommt ein eigenes Kommando mit eigenem Bericht und
eigenem Gate-Ledger. Der bestehende Abnahmebericht bleibt, was er faktisch
ist: die Vorlage des Migrationscontrollings am $t_0$.

### 2. Zwei menschliche Gates in fester Reihenfolge

Neben A-Q1 (fachliche Konflikte), A-M4 und A-K1 tritt **A-M1: aktuarielle
Abnahme**. Die Reihenfolge ist nicht empfohlen, sondern erzwungen:

> **A-M1 geht A-M4 voraus.** Ein A-M4-Entscheid ohne geltende, signierte
> A-M1-Annahme ist unmoeglich.

Begruendung (Auftraggeber, 26.08.): Der aktuarielle Test kommt zuerst; erst
danach werden der Gesamtbestand und die finanziellen Folgen geprueft und
abgenommen. Eine finanzielle Abnahme ohne nachgewiesene methodische Guete
waere ohne Aussage.

Die Reihenfolge wird ueber den Snapshot-Mechanismus abgebildet: Der
A-M4-Snapshot pinnt die geltende, signierte A-M1-Annahme desselben Stands
als Pflichtrolle ``am1_snapshot`` (das ``vorgaenger``-Feld der Kette
bleibt gate-intern, ADR-008). Damit gilt
der bestehende Kettenvertrag aus ADR-008 unveraendert weiter — Schema,
kanonischer Hash, Freigabesignatur, Zyklenfreiheit, genau eine Spitze.

### 3. Rueckschleife ist zulaessig, Reihenfolge bleibt

Eine Ablehnung an A-M4 fuehrt zurueck in Analyse und ggf. erneuten Test. Die
Kette bildet das als neue Snapshots ab; es entsteht keine Sonderlogik.
Unzulaessig bleibt allein die Umkehrung: A-M4 vor A-M1.

### 4. Der aktuarielle Test rechnet je Vertrag zu seinem eigenen $t_a$

Der Vergleichszeitpunkt ist ein **Vertragsattribut**, kein Suite-Parameter.
Daraus folgen drei Invarianten, die im Code gelten und nicht nur in der
Doku stehen:

* **Keine Interpolation.** Verglichen wird am Rechenpunkt; unterjaehrige
  Mischwerte sind im Test unzulaessig (Grundsatzdokumentation 9.12: sonst misst $R$
  Interpolationskonventionen mit und ist als Diagnoseinstrument entwertet).
* **Keine Summation der Vergleichsgroessen.** Werte zu verschiedenen
  Stichtagen zu addieren, ergibt fachlich nichts. Die Test-Engine bildet
  deshalb keine Deckungskapital-Summe; sie kennt ausschliesslich
  Verteilungsgroessen des Residuums (Grundsatzdokumentation 9.15: Toleranzen auf Maximum und
  hohen Perzentilen, nie auf Mittelwert oder Median).
* **Pruefsummen sind Transportsicherung, kein fachlicher Abgleich.**
  Mitgelieferte Summen werden gepruefet und getrennt ausgewiesen, nie als
  Teil des aktuariellen Urteils.

### 5. Stichprobenprofil

Der aktuarielle Test laeuft auf einer **Stichprobe**. Die Stichprobe ist
Teil des Beleges: benanntes Profil, deterministisch und reproduzierbar,
mit ausgewiesener Grundgesamtheit.

Es gibt zwei Profile. Beide sind aus einem konkreten Bedarf entstanden,
keines auf Vorrat:

**`vollbestand`** — die Stichprobe ist der ganze Bestand. Fuer einen
Bestand in der Groessenordnung des Showcase-Falls ist das die fachlich
richtige Wahl und zugleich der Randfall der Parametrisierung.

**`geschichtet`** (ergaenzt 2026-08-28) — je Historientyp-Cluster aus
Lieferobjekt 2 eine feste Anzahl, Ziehreihenfolge ueber einen Hash mit
dokumentiertem Startwert, Abdeckung je Cluster im Beleg. Der Anlass ist
der zweite Baldrian-Fall: Unter 500 Vertraegen tragen 35 eine
Herabsetzung. Eine ungeschichtete Ziehung kann diesen Cluster
vollstaendig verfehlen — der Test bestuende dann, ohne den Vorgang je
gerechnet zu haben, und das ist kein bestandener Test, sondern ein
ungeprueftes Verfahren. Ist ein Cluster kleiner als die Sollzahl, wird er
vollstaendig gezogen und die Untererfuellung ausgewiesen, statt sie zu
verschweigen.

Weitere Profile bleiben offen. Die Erweiterungsstelle ist benannt
(`qa.stichprobe.PROFILE`); sie erfindet keine Profile auf Vorrat.

### 6. „Vollstaendig geprueft" bedeutet auf den beiden Ebenen Verschiedenes

Im Controlling heisst es: jeder Vertrag des Bestands wurde geprueft — ein
ungeprueter Vertrag ist eine Pruefluecke. Im aktuariellen Test heisst es:
die **Stichprobe** wurde vollstaendig abgearbeitet. Die Nichtpruefung der
Nicht-Stichprobe ist dort kein Befund, sondern die Definition.

Ohne diese Unterscheidung meldet das Gate einen korrekt durchgefuehrten
Test als unvollstaendig.

## Konsequenzen

* `P9_GATES` waechst um `A-M1`; das P9-Schema hebt seine Version an. Die
  scope-getriebene Pflichtbelegmenge aus ADR-009 wird **je Gate**
  aufgeloest statt nur je Scope — A-M1 und A-M4 verlangen verschiedene
  Belege.
* ADR-009 erhaelt einen Nachtrag: Die dortige Belegmenge beschreibt ab
  hier A-M4; A-M1 hat eine eigene.
* Der Skill `pruefe-migrationsabnahme` zerfaellt in zwei Skills entlang
  der beiden Verantwortlichkeiten (umgesetzt als
  `aktuartest-durchfuehren` und `pruefe-migrationscontrolling`); das
  Runbook `migrationsfall-durchfuehren` routet auf beide und haelt die
  Reihenfolge ein.
* Bestehende Faelle: Ein Fall, dessen A-M4 vor Einfuehrung dieses ADR
  entschieden wurde, traegt keine gepinnte A-M1-Annahme. Solche Ketten werden
  nicht umgedeutet; der Fall wird nach revisionsfester Archivierung der
  Altkette auf dem neuen Vertrag neu entschieden (Verfahren analog
  ADR-008).
* Punkte E3 und E4 des Migrationskonzepts sind damit entschieden und
  werden dort als entschieden gefuehrt.

## Bewusst nicht Bestandteil dieser Entscheidung

* Die **Korrekturschicht** und der Migrationszugang (Grundsatzdokumentation Abschnitt 9). Dieses
  ADR trennt die Pruefebenen; es baut die Methode nicht. Der aktuarielle
  Test kann seine eigentliche Kennzahl — die Verteilung von
  $R_{\mathrm{hist}}$ — erst rechnen, wenn es ein $R$ gibt. Bis dahin
  traegt er den vorhandenen Wertvergleich, nur am richtigen Zeitpunkt und
  ohne Summation.
* Die **Ueberschussprojektion** im Controlling (Folgejahr). Als kuenftige
  Erweiterung benannt, nicht gebaut.
* Die **Stichprobenprofile** jenseits von `vollbestand` und
  `geschichtet` (siehe 5).

## Verworfene Alternativen

* **Ein Gate mit zwei Vorlagen.** Verwischt die Verantwortung: Der
  Verantwortliche Aktuar und die Projektleitung entscheiden verschiedene
  Dinge zu verschiedenen Zeitpunkten auf verschiedenen Mengen. Ein
  gemeinsamer Entscheid haette keinen eindeutigen Entscheider.
* **Test nach dem Controlling.** Widerspricht der fachlichen Reihenfolge:
  Eine finanzielle Abnahme des Gesamtbestands vor dem Nachweis
  methodischer Guete nimmt etwas ab, dessen Grundlage noch offen ist.
* **Den Test ueber dieselbe Engine mit zwei Stichtagsspalten fahren.**
  Haette die Summations- und Interpolationsverbote nicht erzwingen
  koennen; beide sind hier Richtigkeitsregeln, keine Darstellungsfragen.
