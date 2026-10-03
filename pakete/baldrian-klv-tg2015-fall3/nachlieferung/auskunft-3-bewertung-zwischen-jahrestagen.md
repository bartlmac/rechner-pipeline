# Auskunftsschreiben Nr. 3 — Bewertung zwischen den Vertragsjahrestagen

Betreff: Bestandsuebertragung KLV TG2015 an die Pfefferminzia Lebensversicherung — Auskunft zur Rueckfrage 07; Stand zur Rueckfrage 08

## Frage der PLV

Wie bewertet die Bestandsfuehrung das Deckungskapital zwischen zwei Vertragsjahrestagen; gibt es eine Ausgleichsgroesse bei einem Unterschied zwischen Rechenwerk und gefuehrtem Wert; gibt es ein festes Fenster; gilt das Verfahren fuer beitragsfreie und abgelaufene Vertraege; sind die Erwartungswerte nach diesem Verfahren gerechnet.

## Antwort

1. **Bewertung zwischen den Jahrestagen.** Die Bestandsfuehrung bewertet am Vertragsjahrestag und nicht dazwischen. Die Fuehrung verarbeitet je Kalenderjahr einen Lauf; Vorfaelle werden je Vertrag zum Vertragsjahrestag gebucht, und zwar mit dem Wert dieses Jahrestags, auf einem exakten Rechenpunkt des Tarifwerks. Eine unterjaehrige Bewertung, auch eine lineare Interpolation, kennt das Rechenwerk nicht. Das gilt fuer Deckungskapital und Rueckkaufswert gleich, denn beide werden am selben Rechenpunkt ermittelt. Betraege werden beim Buchen auf den Cent gerundet; die Rechenkette bleibt ungerundet (Tarifplan Abschnitt 5).
2. **Ausgleichsgroesse.** Eine solche Groesse gibt es nicht. Der gefuehrte Wert ist der Wert nach Rechenwerk; ein Unterschied zwischen beiden besteht in der Bestandsfuehrung nicht und wird deshalb nicht ausgeglichen.
3. **Fenster.** Kein Fenster. Das gilt fuer alle Bestandsgruppen und Risikoklassen gleich.
4. **Beitragsfreie und abgelaufene Vertraege.** Das Verfahren gilt unveraendert. Beitragsfrei gestellte Vertraege werden je Baustein mit der fest gefuehrten beitragsfreien Summe am Jahrestag bewertet (AVB Ziffer 5); nach Ablauf der Beitragszahlungsdauer ist der Jahresbeitrag 0,00 (Tarifplan Abschnitt 6), die Bewertung bleibt am Jahrestag.

**Schriftlichkeit.** Schriftlich festgelegt ist in den Unterlagen der Quelle: das Deckungskapital ist die letzte Standmitteilung zum letzten Vertragsjahrestag, die Bestandsfuehrung bewertet am Vertragsjahrestag und interpoliert nicht (Mitteilung 143, Fassung Januar 2015, Abschnitt 6). Alles Weitere ist im Rechenwerk der Bestandsfuehrung ausgefuehrt; eine gesonderte Dienstanweisung liegt uns nicht vor, und seit wann das Verfahren so gefuehrt wird, koennen wir nicht angeben.

**Beispiel aus der Lieferung.** Police 7000386 (Beginn 01.10.2015, beitragspflichtig bis 2025, Bestandsabzug 01.01.2026): gelieferter DECKKAP 150413,06 EUR ist der Wert zum letzten Vertragsjahrestag 01.10.2025 (120 Monate seit Beginn); in `baldrian_erwartungswerte_stichtag.json` steht dazu der Punkt `uebernahme` (120 Monate): kVx_MRV 150413,06, RKW 150363,06. Der Punkt `fortschreibung` (132 Monate, Jahrestag 01.10.2026) lautet kVx_MRV 152085,07, RKW 152035,07. Zwischen diesen Jahrestagen wird kein Wert gefuehrt.

**Erwartungswerte.** Die gelieferten Erwartungswerte (Stichtag, Verlauf, Geschaeftsvorfaelle) sind nach diesem Verfahren gerechnet; sie kommen aus derselben Strecke wie der Bestandsabzug.

## Zu Rueckfrage 08

Die Erwartungswerte fuer die acht Policen koennen wir mit diesem Schreiben nicht zusagen; die Rueckfrage liegt der Leitung der Bestandsfuehrung zur Entscheidung vor. Wir melden uns mit einem gesonderten Schreiben.

## Grundlagen

- Mitteilung 143, Fassung Januar 2015, Abschnitte 5 und 6.
- AVB, Fassung Januar 2015, Ziffer 5.
- Rechenwerk der Bestandsfuehrung (Jahres-Batch, Buchung am Vertragsjahrestag; Bewertung am Rechenpunkt des Tarifwerks).
- Lieferung: `baldrian_bestandsabzug_2026-01-01.csv`, `baldrian_erwartungswerte_stichtag.json`.

Datum: 2026-10-02

Baldrian Lebensversicherung a. G., Bestandsfuehrung
