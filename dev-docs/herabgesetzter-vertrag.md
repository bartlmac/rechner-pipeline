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

**Die Teilung ist nicht die einzige Schreibweise** (praezisiert
2026-08-28). Die Leistungsmathematik verlangt sie nicht: Barwerte sind
linear in der Summe, und voellig kostenfrei liefern beide Schreibweisen
exakt denselben Wert (nachgerechnet, Abweichung 0,00). Was die
Darstellung erzwingt, ist etwas anderes — **Beitrag und Summe
entkoppeln sich**. Ein Thiele-Vertrag ueber die neue Gesamtsumme
forderte nach dem Aequivalenzprinzip 3.105,02, der Kunde zahlt aber
2.679,39; die Luecke von 425,63 kann ein Modellpunkt ohne
Beitragsfeld nicht tragen.

Daraus folgen zwei gangbare Wege:

1. **Zwei Teile** — je in sich stimmig, der beitragspflichtige mit
   seinem eigenen Aequivalenzbeitrag.
2. **Ein Modellpunkt mit ausdruecklichem Beitrag** — dann traegt ein
   Vertrag einen Beitrag, der nicht der Aequivalenzbeitrag ist.

Sie unterscheiden sich NUR in der Kostenzuordnung, und zwar um Betraege
in der Groessenordnung der Verfahrensdifferenz selbst (rund 115 im
zehnten Jahr des Referenzvertrags). Den Ausschlag gibt eine
Randbedingung: Die Zweiteilung erhaelt die Verlustfreiheit im Moment
der Herabsetzung (17.750,35, unveraendert), der einzelne Modellpunkt
verliert dort still 127,93, weil sich seine Kostenbasis von der
urspruenglichen auf die herabgesetzte Summe verschiebt. Wer eine
Umwandlung verlustfrei nennt, darf die Reserve dabei nicht springen
lassen. Am Ablauf treffen beide dieselbe Summe.

**Die eigentliche Frage ist damit eine Kostenfrage**, keine
Darstellungsfrage: Traegt der herabgesetzte Vertrag seine
Verwaltungskosten auf der neuen Gesamtsumme, oder traegt der
fortgefuehrte Teil gamma1 auf seiner eigenen Summe und der umgewandelte
gamma3 auf seiner? Das steht im Tarifwerk, nicht im Code.

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

**Woran man merkt, dass es faellig wird**: Es ist bereits faellig, und
zwar blockierend. Die Migrationssuite weist den Wert am Folgestichtag
eines herabgesetzten Vertrags als Pruefluecke aus
(`dk_stichtag_2_nach_red_monat_<m>`), statt ihn falsch zu rechnen. Der
Bestands-Scope duldet aber keine Pruefluecke: `abnahmebericht` verlangt
"eine vollstaendig gepruefte Migrationssuite ohne Pruefluecken"
(:1307-1312). Nachgerechnet an einem einzigen Vertrag mit einer
Herabsetzung zwischen den Stichtagen: `vollstaendig_geprueft` faellt auf
`False`, und **A-M4 ist damit nicht erreichbar**. Der zweite
Baldrian-Fall traegt vier solche Vorfaelle.

Der Verlaufstest A-M2 zeigt daneben fuer die 25 herabgesetzten
Vertraege der Stichprobe ein Residuum in der Groessenordnung von zehn
Prozent des Deckungskapitals und mehr.
