# Der herabgesetzte Vertrag hat im Zielkern keine Darstellung

## 1 Problem

Nach einer Beitragsherabsetzung besteht ein Vertrag aus zwei Teilen: Ein
Bruchteil `f` laeuft beitragspflichtig weiter, der freigewordene Rest ist
in beitragsfreie Versicherungssumme umgewandelt. Der Zielkern kennt beide
Teile einzeln, aber nicht ihre Verbindung.

Drei Fundstellen, die zusammen die Luecke ergeben:

* `kern/model_point.py` — `ModelPoint` traegt keinen Beitrag; er folgt
  aus der Versicherungssumme. Ein Modellpunkt mit der herabgesetzten
  Gesamtsumme haette damit den falschen Beitrag.
* `kern/rechenkern.py`, `vertrags_monatsreserve` — summiert Scheiben,
  aber alle beitragspflichtig (`kern.monatsreserve(versetzt)`). Eine
  beitragsfreie Teilsumme laesst sich nicht einhaengen.
* `kern/rechenkern.py`, `reserve_beitragsfrei(a0, a)` — gilt fuer den
  GANZEN Vertrag, nicht fuer einen Teil davon.

Die Wertaenderung IM Moment der Herabsetzung rechnet der Kern korrekt
(`kern/beitragsreduktion.py`), und der Geschaeftsvorfalltest A-M3 prueft
sie. Es fehlt die Fortschreibung DANACH.

Gemessen am Referenzvertrag (x=45, n=30, t=20, VS 100.000, Herabsetzung
in Jahr 5 auf 60 Prozent des Beitrags):

| Jahr | Kern heute | zwei Teile | Differenz |
|---:|---:|---:|---:|
| 5 | 17.750,35 | 17.750,35 | 0,00 |
| 10 | 38.893,34 | 30.860,38 | 8.032,96 |
| 20 | 87.283,36 | 60.784,12 | 26.499,24 |
| 30 | 100.000,00 | 69.531,16 | 30.468,84 |

## 2 Warum es zaehlt

Ein Vertrag, der vor der Migration herabgesetzt wurde, laesst sich nicht
konstruktiv neu rechnen — der Kern rechnet ihn mit seinen
Ursprungsparametern, also so, als waere nie herabgesetzt worden. Dann
landet die gesamte Wirkung der Herabsetzung im Residuum statt nur die
Verfahrensdifferenz, und die Korrekturschicht traegt eine Groesse, die
sie nicht tragen soll.

Am Ablauf traegt die Schicht per Terminalbedingung null. Der Vertrag
zahlte dort die urspruengliche Summe aus, im Beispiel 100.000 statt
69.531 — ein knappes Drittel zu viel, und zwar an den Kunden.

Ausserdem rechnet die Engine eine ZWEITE Herabsetzung auf der
urspruenglichen Summe und damit falsch. Der Fall ist nicht theoretisch:
Der zweite Baldrian-Fall enthaelt 35 herabgesetzte Vertraege in der
Vorgeschichte, davon 25 in der Stichprobe des Verlaufstests.

## 3 Loesungsskizze

Den herabgesetzten Vertrag als zwei Teile fuehren: eine
beitragspflichtige Scheibe mit der Summe `VS * f` — deren abgeleiteter
Beitrag stimmt dann wieder — und eine beitragsfreie mit der
umgewandelten Zusatzsumme. Dafuer muss `vertrags_monatsreserve`
beitragsfreie Teile aufnehmen koennen; heute summiert sie nur
beitragspflichtige.

Zwei Randbedingungen sprechen dafuer, und beide sind nachgerechnet: Im
Moment der Herabsetzung ergibt die Zweiteilung denselben Wert wie
`kern.beitragsreduktion` (verlustfrei, Abweichung null), und am Ablauf
genau die herabgesetzte Versicherungssumme. Eine Darstellung, die beide
Enden trifft, ist mit einiger Sicherheit die richtige.

**Was die Skizze NICHT leistet.** Sie sagt nichts darueber, wie der
Vertrag GELIEFERT wird — ob das abgebende Unternehmen die
Ursprungssumme und den Anteil mitgibt oder nur die neue Gesamtsumme. Sie
loest auch die Rumpfjahr-Frage nicht (Herabsetzung nur am
Vertragsstichtag, siehe offene-punkte.md), und sie sagt nichts zur
BU-Seite. Ob die Zweiteilung auch die richtige Darstellung fuer den
Bestandsbericht und die Kennzahlen ist, waere gesondert zu pruefen —
dort erscheint ein solcher Vertrag heute als ein Vertrag, nicht als
zwei.

## 4 Einordnung

**Aufwand** mittel: eine Erweiterung von `vertrags_monatsreserve` um
beitragsfreie Teile, eine Darstellung des geteilten Vertrags im
Migrationszugang, Tests fuer die beiden Randbedingungen. Der
Zustandsbegriff der Bestandsfuehrung ist mitbetroffen (`models/bestand.py`
kennt `POL` und `PEX`, aber nichts Geteiltes).

**Abhaengigkeiten**: Die Rumpfjahr-Konvention muss nicht vorher
entschieden sein; beide Fragen sind unabhaengig. Der Migrationszugang
und die Korrekturschicht sind betroffen, sobald ein Bestand
herabgesetzte Vertraege enthaelt.

**Wer entscheidet**: das Aktuariat — ob die Zweiteilung die richtige
Modellierung ist oder ob die Herabsetzung anders gefuehrt gehoert.

**Woran man merkt, dass es faellig wird**: Der Verlaufstest A-M2 des
Baldrian-Falls meldet fuer die 25 herabgesetzten Vertraege der
Stichprobe ein Residuum in der Groessenordnung von zehn Prozent des
Deckungskapitals und mehr. Die Migrationssuite weist den Wert am
Folgestichtag solcher Vertraege ausdruecklich als Pruefluecke aus
(`dk_stichtag_2_nach_red_monat_<m>`), statt ihn falsch zu rechnen — wer
diese Luecke schliessen will, braucht dieses Vorhaben.
