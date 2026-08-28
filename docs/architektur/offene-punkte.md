# Offene Punkte

Fragen, die bewusst offen sind. Sie stehen hier, damit sie nicht in
Notizen oder Sitzungsprotokollen verschwinden und irgendwann still durch
eine Konvention im Code beantwortet werden.

Ein Punkt gehoert hierher, wenn drei Dinge zutreffen: Er verlangt eine
fachliche Entscheidung und keine technische; er beruehrt mehr als eine
Stelle im Code; und es gibt heute eine Zwischenloesung, die traegt, aber
nicht die endgueltige ist. Ist ein Punkt entschieden,
wird er hier geloescht und die Entscheidung steht dort, wo sie hingehoert
— in einem ADR, in der Grundsatzdokumentation oder im Tarifplan.

## O-1 Rumpfjahr-Konvention bei unterjaehrigem Verankerungszeitpunkt

Die Korrekturschicht rechnet auf dem Jahresgitter, der
Verankerungszeitpunkt $t_a$ folgt aber dem letzten rechnenden
Geschaeftsvorfall vor dem Stichtag. Ein Vorfall im Maerz bei
Vertragsstichtag im Dezember ergibt ein $t_a$, das auf keinem
Jahrespunkt liegt.

**Heute**: Der Fall faellt mit sprechender Meldung aus. Auf den
Jahrestag zu runden waere eine stille Konvention gewesen — genau die
findet spaeter niemand mehr.

**Zu entscheiden**: entweder ein Monatsgitter fuer die Schicht oder eine
ausdrueckliche Rumpfjahr-Konvention. Die Frage ist groesser als die
Schicht: Auch die Beitragsreduktion ist deshalb bis auf Weiteres nur am
Vertragsstichtag moeglich (`kern.beitragsreduktion`, Beschluss
2026-08-28).

## O-2 Werkzeug der Quellsimulation: Repo-Bestandteil oder Beispielandockung

Die Vorfuehrung beansprucht, dass sich alles in diesem Repo
nachvollziehen laesst. Ein Teil des Werkzeugs, mit dem die Unterlagen
des abgebenden Unternehmens entstehen — Berechnungslaeufe in der
Tarifmappe, Bearbeitung der Mitteilungen —, liegt aber auf einer
Office-Umgebung ausserhalb des Repos.

**Heute**: Was ohne Office geht, entsteht hier (siehe
`simulation/quellwerkzeug/`); der Rest laeuft ueber Auftragsdateien an die
Office-Seite.

**Zu entscheiden**: welche Teile versionierter Repo-Bestandteil werden
und welche als ausdruecklich gekennzeichnete *Beispielandockung*
mitlaufen — im Repo, aber nicht als zugesagte Schnittstelle. Die
Trennlinie fehlt, und ohne sie waechst das Repo entweder um fremde
Werkzeuge oder die Vorfuehrung bleibt unvollstaendig.

## O-3 Reihenfolge der aktuariellen Abnahmen

A-M1 bis A-M3 gehen dem Controlling A-M4 voraus (ADR-012). Ob A-M2
(Verlaufstest) und A-M3 (Geschaeftsvorfalltest) auch **Voraussetzung**
von A-M4 sind oder nur zeitlich davor liegen, ist offen.

**Heute**: Nur A-M1 ist Voraussetzung. A-M2 und A-M3 laufen, ihr
Ergebnis blockiert das Controlling aber nicht.

**Zu entscheiden**: Ein Bestand, der am Stichtag stimmt und zum Ablauf
falsch zahlt, wuerde heute durch das Controlling gehen. Ob das
hinnehmbar ist, haengt daran, wie belastbar A-M2 ohne einen langen
Verlauf echter Faelle ist.

## O-4 Heilungsklasse von PEX, INV und REA

Die Heilungstabelle (`kern.korrekturschicht.HEILUNG`) fuehrt fuer jeden
Geschaeftsvorfall, ob er die Korrekturschicht aufloest. Drei Eintraege
sind uebernommen, aber fachlich nicht bestaetigt (`geprueft=False`):

* **PEX** steht in Abschnitt 9.7 unter Klasse A. Plausibel, weil die
  Freistellung neu rechnet — nicht bestaetigt.
* **INV** und **REA** wechseln den Zustand des BU-Graphen. Ob ein
  solcher Wechsel neu rechnet, haengt an der BU-Zustandsbewertung, die
  noch nicht steht.

**Heute**: PEX heilt, INV und REA heilen nicht. Die Tabelle weist die
Unsicherheit aus, statt sie zu verschweigen.

## O-5 Der Bestandsbericht kennt den Migrationszugang nicht

`MIG` ist Geschaeftsvorfall im Journal und in der Kennzahlenrechnung,
erscheint aber in den Berichtstexten des Bestandsberichts nicht. Ein
Leser sieht den Zugang in den Zahlen und findet ihn im Text nicht
wieder.

**Heute**: Luecke in der Darstellung, nicht in der Rechnung.

## O-6 Schutz echter Laeufe

Echte Migrationslaeufe liegen unter `runs/` neben Probelaeufen. Ein
Aufraeumen trifft beide. Ein Lauf, der einmal Grundlage einer Abnahme
war, sollte nicht durch dieselbe Handbewegung verschwinden koennen wie
ein Versuch von gestern.

**Heute**: keine Trennung, kein Schutz.

## O-7 Der herabgesetzte Vertrag hat im Zielkern keine Darstellung

Nach einer Beitragsherabsetzung besteht ein Vertrag aus zwei Teilen: Ein
Bruchteil ``f`` laeuft beitragspflichtig weiter, der freigewordene Rest
ist in beitragsfreie Summe umgewandelt. Der Zielkern kennt beide Teile
einzeln, aber nicht ihre Verbindung:

* ``ModelPoint`` traegt keinen Beitrag — er folgt aus der
  Versicherungssumme. Ein Modellpunkt mit der herabgesetzten Gesamtsumme
  haette damit den falschen Beitrag.
* ``vertrags_monatsreserve`` summiert Scheiben, aber alle
  beitragspflichtig. Eine beitragsfreie Teilsumme laesst sich nicht
  einhaengen.
* ``reserve_beitragsfrei(a0, a)`` gilt fuer den GANZEN Vertrag, nicht
  fuer einen Teil davon.

**Was heute geht**: Die Wertaenderung IM Moment der Herabsetzung
(``dDK``) rechnet der Kern korrekt (``kern.beitragsreduktion``), und der
Geschaeftsvorfalltest A-M3 prueft sie. Das ist der Vorfall selbst —
solange er der erste ist. Bei einem Vertrag, der schon einmal
herabgesetzt wurde, rechnet die Engine die zweite Herabsetzung auf der
urspruenglichen Summe und damit falsch. Der Fall ist nicht theoretisch:
Im zweiten Baldrian-Fall trifft er zwei Vertraege.

**Was heute nicht geht**: die Fortschreibung DANACH. Ein Vertrag, der vor
der Migration herabgesetzt wurde, laesst sich nicht konstruktiv neu
rechnen — der Kern rechnet ihn mit seinen Ursprungsparametern, also so,
als waere nie herabgesetzt worden. Die gesamte Wirkung der Herabsetzung
landet dann im Residuum, statt nur die Verfahrensdifferenz. Am Ablauf
traegt die Schicht per Terminalbedingung null, und der Vertrag zahlte die
urspruengliche Summe aus — nicht die herabgesetzte.

**Groessenordnung** (Referenzvertrag x=45, n=30, t=20, VS 100.000,
Herabsetzung in Jahr 5 auf 60 Prozent des Beitrags):

| Jahr | Kern heute | zwei Teile | Differenz |
|---:|---:|---:|---:|
| 5 | 17.750,35 | 17.750,35 | 0,00 |
| 10 | 38.893,34 | 30.860,38 | 8.032,96 |
| 20 | 87.283,36 | 60.784,12 | 26.499,24 |
| 30 | 100.000,00 | 69.531,16 | 30.468,84 |

Am Ablauf zahlte der Kern 100.000 statt der herabgesetzten 69.531,16 —
ein knappes Drittel zu viel, und das an den Kunden.

**Zu entscheiden**: Die naheliegende Darstellung ist ein Vertrag aus zwei
Teilen — ein beitragspflichtiger mit der Summe ``VS * f`` (dessen
abgeleiteter Beitrag stimmt dann wieder) und ein beitragsfreier mit der
umgewandelten Zusatzsumme. Sie trifft beide Randbedingungen exakt: Im
Moment der Herabsetzung ergibt sie denselben Wert wie
``kern.beitragsreduktion`` (verlustfrei, Abweichung null), und am Ablauf
genau die herabgesetzte Versicherungssumme. Das ist ein starkes Indiz,
dass sie richtig ist — sie verlangt aber, dass
``vertrags_monatsreserve`` beitragsfreie Teile aufnehmen kann. Ob dieser
Weg gegangen wird oder die Herabsetzung anders modelliert gehoert, ist
eine fachliche Entscheidung.

Der zweite Baldrian-Fall enthaelt 35 solche Vertraege in der
Vorgeschichte, davon 25 in der Stichprobe des Verlaufstests — der Punkt
wird also gemessen, sobald der Test laeuft.
