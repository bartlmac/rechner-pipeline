# Bestandsführung

Eigene und übernommene Verträge laufen bei uns in einem Bestand. Zu
jedem Monatsersten steht ein Abschluss, und zu jedem Abschluss ein
Bericht. Stand {{datum:betrieb.stand}}.

Wer sehen will, wie das täglich aussieht: [Bestand heute](../plv/)
ist die Betriebssicht unseres Bestandsführungssystems — Neugeschäft der
Woche und die letzten Buchungen mit Wirkungstag und Buchungstag. Die
Seite wird vom System selbst erzeugt und sieht deshalb anders aus als
die übrigen.

## Bestand heute {: #bestand-heute }

Zum jüngsten Monatsabschluss.

{{svg:bestand_vergleich_tief}}

Aus Übernahmen stammen {{zahl:betrieb.bestand.uebernommen_in_force}} dieser
Verträge. Eingetreten sind seinerzeit mehr; seither sind einzelne
abgelaufen, storniert oder durch Tod beendet worden, wie im eigenen
Geschäft auch. Wie viele zum Übernahmestichtag eintraten, steht unter
[Zugänge aus Übernahmen](#zugaenge-aus-uebernahmen).

## Wie der Bestand geführt wird {: #fuehrung }

Der Bestand ist ein geführter Zustand mit Journal. Jeder
Geschäftsvorfall trägt zwei Daten: den Wirkungstag, zu dem er gilt, und
den Buchungstag, an dem wir ihn erfasst haben. Jeder Betrag kommt aus
dem Rechenkern, keiner aus einer Lieferung.

Ein Tageslauf führt jeden Kalendertag — Neugeschäft, Fortschreibung,
Journal. Bevor der neue Stand übernommen wird, prüft eine Wache, ob er
zu den Büchern passt; meldet sie einen Befund, wird er nicht übernommen.
Zum Monatsersten wird ein Abschluss festgeschrieben: der in-force-Bestand
dieses Tages mit Deckungskapital, Rückkaufswert und Jahresbeitrag je
Vertrag.

Übernommene Bestände treten zum Übernahmestichtag als Zugang ein und
laufen danach im selben Strom weiter wie das eigene Geschäft. Ein
eigener und ein übernommener Vertrag unterscheiden sich in unseren
Büchern nur durch die Tarifgeneration, nach der sie bewertet werden.

## Zugänge und Leistungen {: #zugaenge-und-leistungen }

Je Kennzahl die Anzahl und der Betrag — letztes Jahr, aktuelles Jahr,
aktueller Monat. Die Beträge sind Bewegungsgrößen des Zeitraums; den
Beitrag des Bestands am Stichtag nennt die Startseite unter
[Unser Bestand](../#unser-bestand).

{{html:geschaeftsentwicklung}}

Über die ganze Zeit gerechnet, für eigene wie für übernommene Verträge,
seit {{datum:betrieb.gefuehrt_seit}}:

{{tabelle:buchungen_je_art}}

## Zugänge aus Übernahmen {: #zugaenge-aus-uebernahmen }

{{tabelle:uebernahmen_im_stand}}

Was die Übernahme Baldrian in den Büchern bedeutet — die gelieferten
Größen der abgebenden Gesellschaft:

| | |
|---|---:|
| Übernommenes Deckungskapital ({{datum:abnahmen.controlling.stichtag_1}}) | {{euro:bestand.abzuege.0.deckkap.summe}} € |
| Laufender Jahresbeitrag | {{euro:bestand.abzuege.0.jbrutto.summe}} € |
| Versicherungssumme der Lieferung | {{euro:bestand.abzuege.0.erlsumme.summe}} € |
| Verträge | {{zahl:bestand.anzahl}} |

Wie eine Übernahme abläuft und woran sie sich messen lassen muss, steht
unter [Bestandsmigrationen](../migrationen/).

## Monatsberichte {: #monatsberichte }

Jeder Monatserste wird festgeschrieben. Gezeigt werden die letzten zwölf
Monatsberichte mit dem Bestand am Stichtag und den Geschäftsvorfällen des
Monats, den sie schließen, dazu der Jahresbericht zum Jahresende.

{{tabelle:abschluesse}}
