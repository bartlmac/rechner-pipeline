# Migrierte Vertraege brauchen Zahlungspfade, nicht Produktparameter

## 1 Problem

Der Zielkern kann einen Vertrag nicht bewerten, dessen Leistung oder
Beitrag sich mitten im Verlauf geaendert hat. Der Anlass war die
Beitragsherabsetzung, aber die Ursache liegt tiefer und trifft mehr.

**Das Rueckgrat kann es laengst.** `kern/zustandsmodell.py` nimmt
Zahlungen als Funktionen des Jahres entgegen:

    zahlung_zustand(zustand, jahr)      vorschuessig auf Zustaenden
    zahlung_uebergang(von, nach, jahr)  nachschuessig auf Uebergaengen

Das ist das Leistungs- und Beitragsspektrum: ein beliebiger
Leistungsverlauf, ein beliebiger Beitragsverlauf, Rueckwaertsrekursion
ueber beides. Beitraege sind negative Zustandszahlungen, der Todesfall
ist eine Uebergangszahlung, der Ablauf eine Zustandszahlung im letzten
Jahr. Die Korrekturschicht nutzt genau diese Allgemeinheit bereits
(`kern/korrekturschicht.py:318`: `zahlung_zustand=lambda s, j:
form.werte[j] ...`), und die BU tut es auch.

**Verloren geht sie eine Schicht darueber.** Zwischen dem Rueckgrat und
dem KLV-Produkt sitzt `ZustandsBarwerte`
(`kern/zustandsmodell.py:231`), und die rechnet genau drei Dinge:

| Zahlungsart | was sie ist |
|---|---|
| `annuitaet` | **1** je Jahr, solange aktiv |
| `tod` | **1** bei Tod |
| `erleben` | **1** bei Erleben des Ablaufs |

Drei EINHEITS-Barwerte. `produkte/klv.py` skaliert sie mit der
Versicherungssumme und dem Beitrag. In dieser Skalierung steckt die
Annahme, dass Summe und Beitrag ueber die Laufzeit konstant sind.

Fuer Neugeschaeft ist das richtig — ein Tarifrechner rechnet aus
Produktparametern. Fuer einen Migrationskern ist es zu eng: Ein
uebernommener Vertrag ist kein Produktparametersatz, sondern ein Vertrag
mit einer Geschichte.

**Der Messpunkt.** Nach einer Herabsetzung auf 60 Prozent des Beitrags
(Referenzvertrag x=45, n=30, t=20, VS 100.000, Jahr 5) fordert ein
Vertrag ueber die neue Gesamtsumme nach dem Aequivalenzprinzip 3.105,02;
der Kunde zahlt 2.679,39. Die Luecke von 425,63 kann ein Modellpunkt
ohne Beitragsfeld nicht tragen. Die Leistungsmathematik ist daran
unschuldig: voellig kostenfrei liefern Zweiteilung und einzelner
Modellpunkt exakt denselben Wert (Abweichung 0,00). Was sich entkoppelt,
sind Beitrag und Summe.

## 2 Warum es zaehlt

Ohne Zahlungspfade rechnet der Kern einen vor der Migration
herabgesetzten Vertrag mit seinen Ursprungsparametern — also so, als
waere nie herabgesetzt worden. Am Ablauf zahlte er die urspruengliche
Summe aus: im Beispiel 100.000 statt 69.531, ein knappes Drittel zu
viel, und zwar an den Kunden.

**Es blockiert heute.** Die Migrationssuite weist den Wert am
Folgestichtag eines herabgesetzten Vertrags als Pruefluecke aus
(`dk_stichtag_2_nach_red_monat_<m>`), statt ihn falsch zu rechnen. Der
Bestands-Scope duldet aber keine Pruefluecke: `abnahmebericht` verlangt
"eine vollstaendig gepruefte Migrationssuite ohne Pruefluecken"
(:1307-1312). Nachgerechnet an einem einzigen Vertrag mit einer
Herabsetzung zwischen den Stichtagen faellt `vollstaendig_geprueft` auf
`False` — **A-M4 ist damit nicht erreichbar**. Der zweite Baldrian-Fall
traegt vier solche Vorfaelle.

**Es trifft mehr als die Herabsetzung.** Dieselbe Enge blockiert jede
technische Aenderung eines Altbestands: Zuzahlung, Teilrueckkauf,
Beitragsdynamik ohne Summenaenderung, Verlaengerung. Auch die
beitragsfrei gestellten und die dynamisch erhoehten Vertraege sind
betroffen — bei 40 PEX- und 35 RED-Faellen des Bestands ist die
gelieferte Summe nicht mehr die Ursprungssumme, bei 90 ERH-Faellen
enthaelt sie die Scheiben. Einmal an der richtigen Stelle geloest, ist
das alles geloest.

## 3 Loesungsskizze

Ein migrierter Vertrag traegt seine Zahlungspfade und wird auf dem
`Zustandsmodell` bewertet — so, wie die Korrekturschicht es schon tut.
Nicht ein Beitragsfeld im Modellpunkt, nicht eine Zweiteilung in
Scheiben: beides sind Flicken am Produkt-Interface, waehrend das
Rueckgrat die Sache ohnehin kann.

**Die Effizienzfrage traegt die heutige Bauform nicht mehr.** Der
Spalten-Cache von `ZustandsBarwerte` bringt Faktor 14,5 — aber die
absoluten Zahlen sind klein, und ein Spektrum-Pfad ist sogar SCHNELLER,
weil er eine Rekursion ueber die Vertragslaufzeit rechnet statt drei
Einheitsspalten ueber den ganzen Altersbereich (gemessen 2026-08-28 an
den 500 Vertraegen des Vorfuehrbestands, je eine Stichtagsbewertung):

| Weg | je Vertrag |
|---|---:|
| Skalare mit Spalten-Cache | 0,04 ms |
| Skalare ohne Cache | 0,60 ms |
| eigener Zahlungspfad je Vertrag | **0,03 ms** |

Hochgerechnet auf 500.000 Vertraege: 16,5 Sekunden einkernig, eine
Sekunde auf sechzehn Kernen. Die Bauform muss also nicht aus
Geschwindigkeitsgruenden bleiben.

**Die naive Form geht NICHT** (vermessen 2026-08-28). Der Nachbau ueber
Zahlungspfade ist bit-exakt moeglich — alle fuenf KLV-Referenzdateien
liessen sich allein mit ``Zustandsmodell.barwert_verlauf``
reproduzieren. Aber nur mit **getrennten Einheits-Paessen und Faktoren
AUSSERHALB der Rekursion**. Sobald Todesfall und Ablauf in EINEN Aufruf
wandern oder die Versicherungssumme in den Zahlungsvektor gezogen wird,
weichen die Werte in der letzten Stelle ab, und die bit-exakte Abnahme
faellt. Die Summationsreihenfolge ist Teil dessen, was die
eingefrorenen Referenzwerte festhalten.

Fuer die Umstellung heisst das: Der Standardvertrag behaelt die heutige
arithmetische Gestalt, sonst ist die Abnahme nicht zu haben. Die
Allgemeinheit kommt daneben, fuer Vertraege mit geaendertem Verlauf —
fuer die es ohnehin keine eingefrorene Referenz gibt.

**Drei weitere Fallen aus derselben Vermessung**, jede eine, an der ein
Nachbau still falsch wird:

* **Es gibt keine Netto-Reserve im Code.** ``kVx_bpfl``/``kDRx_bpfl``
  ist die GEZILLMERTE Deckungsrueckstellung, ``kVx_MRV`` dieselbe
  Groesse mit auf ``zillmer_dauer`` gestreckter
  Abschlusskostentilgung — die Bilanz- und Rueckkaufsgroesse. Wer die
  Netto-Reserve als Vergleich nimmt, liegt in Jahr 3 um 1.834 daneben.
  Genau daran ist der Schnellversuch gescheitert.
* **Der Beitrag in der Reserve ist ein SATZ, das Zillmerglied ein
  BETRAG.** In ``kVx_bpfl`` steht der gezillmerte Nettobeitragssatz
  ``Pxt`` (je Einheit Versicherungssumme), im Zillmerglied von
  ``kVx_MRV`` dagegen der absolute ``BJB``. Derselbe Methodenrumpf
  wechselt die Masseinheit.
* **``VS_bfr`` springt bei ``a = t``.** Drei Zweige: null nach Ablauf,
  ``kVx_MRV / kVx_bfr`` waehrend der Beitragszahlung, und danach die
  volle Versicherungssumme — im Referenzvertrag ein Sprung um 1,1
  Prozent gegenueber dem, was die Formel ergaebe.

**Was die Skizze NICHT leistet, und was sie ausdruecklich NICHT
vorschlaegt.**

Sie schlaegt NICHT vor, `ZustandsBarwerte` sofort zu entfernen. Bis
ADR-013 hatte die Schicht eine zweite Aufgabe neben der Effizienz: Sie
stellte das `Barwerte`-Interface fuer den Kommutations-Kreuz-Check
bereit. Dieser Anspruch ist am 2026-08-28 geschnitten — die
Ueberleitung ist ausser Betrieb, die Einhaengestelle
`KLV(mp, barwerte=...)` entfernt. Damit ist die Schicht eine reine
Effizienzschicht, und die traegt sich nach der Messung oben nicht mehr.

Sie faellt trotzdem nicht mit dieser Skizze, sondern MIT der
Umstellung: Solange die KLV Einheitsbarwerte abfragt, wird sie
gebraucht. Erst wenn der Standardvertrag seine arithmetische Gestalt in
der neuen Form erreicht, ist sie leer.

Vorgeschlagen ist deshalb ein ZWEITER Pfad neben dem skalaren:

* der skalare Pfad bleibt vorerst fuer Standardvertraege und haelt
  deren bit-exakte Gestalt;
* der Spektrum-Pfad bewertet Vertraege, deren Verlauf geaendert wurde;
* **im Ueberschneidungsbereich muessen beide denselben Wert liefern** —
  ein Standardvertrag ueber Spektren bewertet muss die skalare Reserve
  treffen, und zwar bit-exakt gegen die eingefrorenen Referenzwerte.

Diese Deckungsgleichheit ist der erste Meilenstein und zugleich die
Sperre: Ohne sie darf der zweite Pfad nicht produktiv werden. Sie ist
erreichbar — siehe die Vermessung unten —, aber nur unter Erhalt der
arithmetischen Gestalt.

Sie loest ausserdem die Kostenfrage nicht auf, sondern macht sie
sichtbar. Ein Zahlungspfad muss die Kosten enthalten, und ob der
herabgesetzte Vertrag gamma1 auf der neuen Gesamtsumme traegt oder der
fortgefuehrte Teil auf seiner und der umgewandelte gamma3 auf seiner,
steht im Tarifwerk. Der Unterschied ist, dass man es im Pfadmodell
HINSCHREIBT, statt dass es sich als Nebenwirkung einer Kodierung
ergibt — und er ist nicht klein: rund 115 im zehnten Jahr des
Referenzvertrags, dieselbe Groessenordnung wie die ganze
Verfahrensdifferenz.

Nichts sagt sie zur Rumpfjahr-Konvention (siehe offene-punkte.md), zur
BU-Seite und zur Darstellung eines geaenderten Vertrags im
Bestandsbericht und in den Kennzahlen.

## 4 Einordnung

**Aufwand** gross, und die Schaetzung steht auf duennem Grund. Ein
erster Versuch, die klassische Reserve ueber einen Zahlungspfad
nachzubauen, ist am 2026-08-28 gescheitert — an drei Stellen zugleich:
Beitragssatz gegen Absolutbetrag verwechselt, Off-by-one am Ablauf, und
gegen die GEZILLMERTE Reserve verglichen statt gegen die Netto-Reserve.
Das ist die Lehre des Versuchs und gehoert in die Schaetzung: Die
Rekursion ist der einfache Teil. Die Arbeit sind die Konventionen —
Zillmerung, Kostenpfade, Rundungsreihenfolge, unterjaehrige Mischung.
Wer diese Umstellung angeht, plant den Nachweis der
Deckungsgleichheit als eigenes Arbeitspaket, nicht als Abschlusstest.

**Abhaengigkeiten**: unabhaengig von der Rumpfjahr-Konvention.
`ZustandsBarwerte` und der Kommutations-Kreuz-Check bleiben unberuehrt.
Betroffen sind Migrationszugang, Korrekturschicht, Migrationssuite und
der aktuarielle Test, sobald ein Bestand geaenderte Vertraege enthaelt —
also sofort.

**Wer entscheidet**: das Aktuariat ueber die Kostenpfade; die
Architektur ueber den zweiten Bewertungspfad. Die Richtung ist am
2026-08-28 besprochen und bejaht.

**Woran man merkt, dass es faellig wird**: Es ist faellig. A-M4 des
zweiten Baldrian-Falls ist ohne diese Umstellung nicht erreichbar, und
der Verlaufstest A-M2 meldet fuer die 25 herabgesetzten Vertraege der
Stichprobe ein Residuum in der Groessenordnung von zehn Prozent des
Deckungskapitals und mehr.
