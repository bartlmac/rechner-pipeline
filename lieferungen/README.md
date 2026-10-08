# Lieferungen

Die Lieferungen der vorgeführten Migrationen: je Verzeichnis die
Lieferung eines erfundenen abgebenden Unternehmens, mit der jeder eine
Migration selbst durchführen kann. Die Lieferungen enthalten keine echten
Vertrags-, Kunden- oder Bestandsdaten; Unternehmen und Bestände sind frei
erfunden. Sie enthalten gewollt Fehler und Eigenheiten, und genau die soll
die Pipeline finden.

Kein Eingangskanal: kein Code liest dieses Verzeichnis implizit. In
einen Migrationsfall gelangt eine Lieferung ausschließlich über die
ausdrückliche Registrierung (`python -m rechner_pipeline.fall
registrieren ...`) — dort beginnt die Provenienzkette.

## baldrian/

Die Lieferung der **Baldrian Leben** zur Übernahme ihres
KLV-Bestands (Tarifgeneration TG2015), Migrationsstichtag 01.01.2026:
der Tarifrechner, die Tarifmeldung und die Bestandsdaten-Lieferung
(Abzug zum Migrations- und zum Folgestichtag plus
Geschäftsvorfall-Protokoll des Zwischenjahres).

Ein Drittel der Verträge trägt eine **Vorgeschichte** — Erhöhungen,
Beitragsfreistellungen und Herabsetzungen vor dem Migrationsstichtag.
Ihre Wirkung steckt im gelieferten Stand, ihre Beträge kommen nicht mit.
Geliefert wird nur `baldrian_gevo_metadaten.csv`: Police, Art und Datum,
ohne Beträge. Ohne diese Liste ist der Verankerungszeitpunkt nicht
bestimmbar und die aktuarielle Abnahme nicht durchführbar; die Beträge
dagegen bleiben beim abgebenden Unternehmen, weil das Zielsystem neu
rechnet und keine fremde Historie liest.

Die **aktuarielle Notiz zur Beitragsabsetzung** liegt bei, gehört aber
nicht zur ursprünglichen Lieferung: Die Tarifmeldung beschreibt das
Verfahren der Herabsetzung nicht, und das ist kein Versehen — der
Vorgang ist in den Bedingungen als Möglichkeit eröffnet, ohne zugesagtes
Ergebnis. Die Notiz wird deshalb erst registriert, wenn die Lücke
aufgefallen und nachgefragt worden ist. Wer sie von Anfang an in den
Fall nimmt, überspringt genau den Vorgang, den dieser Showcase zeigt.

Dasselbe gilt für **zwei weitere Nachlieferungen**, die erst auf
Rückfrage entstanden sind. Sie liegen bei, gehören aber ebenso wenig zur
ursprünglichen Lieferung:

* Die **aktuarielle Notiz zum Stornoabschlag** (2026/05) beantwortet die
  Frage, nach welcher Regel der Abschlag eines bereits herabgesetzten
  Vertrages gebildet wird — mit der Auskunft, dass es diese Regel nicht
  gibt: Die Absetzung war der Werthöhe nach nie zugesagt, die damalige
  Berechnung ist nicht mehr rekonstruierbar. Für die betroffenen
  Verträge ist der gelieferte Rückkaufswert damit kein herleitbarer
  Erwartungswert. Das ist eine realistische Auskunft, keine Panne:
  Abgebende Unternehmen können ihre Altbestandsrechnungen oft nicht
  vollständig herleiten. Ob ein Verfahren das aushält, statt es zu
  übertünchen, entscheidet sich an solchen Stellen.
* Die **Nachlieferung zu den Absetzungen** trägt eine einzige Zeile: den
  fortgeführten Beitragsanteil einer Police, deren
  Beitragszahlungsdauer am Migrationsstichtag bereits abgelaufen war.
  Bei allen übrigen Absetzungen ist dieser Anteil aus dem gelieferten
  Stand rückrechenbar; bei dieser einen fällt die Beitragsgleichung weg.
  Geliefert wird also, was wirklich nicht ableitbar ist — nicht mehr.

Beide Nachlieferungen sind Dokumente, nicht Zusagen per Zuruf: Die
menschlichen Gates binden registrierte Eingänge über ihre Prüfsummen,
und eine Auskunft, die nur im Gesprächsprotokoll steht, lässt sich dort
nicht pinnen.

Die **Erwartungswerte für den aktuariellen Test** liegen in vier
Dateien: die Werte am Übernahmestichtag und am Folgejahrestag, die Werte
im Verlauf (fünf und zehn Jahre nach der Übernahme sowie zum Ablauf),
die Werte je Geschäftsvorfall, und der Beleg der vereinbarten
Stichprobe. Baldrian rechnet nicht den ganzen Bestand nach, sondern die
hundert Verträge einer nach Historientyp geschichteten Stichprobe plus
alle zweiundvierzig Verträge mit Vorfall im Migrationsjahr — die
Stichprobe ist deshalb Teil der Lieferung und nicht Sache des
übernehmenden Unternehmens.

Eine Abkürzung des Vorführfalls sei hier ausdrücklich genannt: Diese
vier Dateien tragen bereits die Struktur der Prüfaufträge des
aktuariellen Tests (Zeitpunkt, Anlass, erwartete Größen). Ein echtes
abgebendes Unternehmen lieferte Werte in seinem eigenen Format, und die
Übersetzung in Prüfaufträge wäre selbst ein Arbeitsschritt. Die
Abkürzung spart diesen Schritt; sie ändert nichts an den Werten.

**Durchführung:** Lauf 1 wurde von Hand und mit Agenten geführt. Ob er auf
dem heutigen Stand durchläuft, ist nicht gemessen; der heute gepflegte Weg
ist Fall 3 (`docs/faelle/README.md`).

## baldrian-2/

Die zweite, umfangreichere Lieferung derselben Gesellschaft für den
zweiten Migrationslauf (Abschlussbericht `docs/faelle/baldrian-lauf2.md`):
Tarifrechner, Mitteilung und Bedingungen, Bestandsabzüge zu beiden
Stichtagen, Vorgeschichts-Metadaten, Geschäftsvorfall-Protokoll, die vier
Erwartungswert-Dateien und vier Auskunftsschreiben, die erst auf Rückfrage
entstanden sind — was wozu gehört, sagt `LIEFERSCHEIN.md`. Wie der Lauf
auf dem Systemstand wiederholt wird, auf dem er gezeichnet wurde —
einschließlich des eigenen Bestands der übernehmenden Gesellschaft, der
nicht aus der Lieferung stammt, sondern erzeugt wird:
`docs/faelle/baldrian-lauf2-wiederholen.md`.

### Fall 3 nutzt dieselbe Lieferung

Für Fall 3 gibt es keine eigene Lieferung und kein Verzeichnis
`baldrian-3`. Fall 3 hat die Übernahme von vorn neu geführt, und zwar auf
genau dieser Lieferung: Registriert wurden der Lieferschein und die elf
Dateien, die er nennt. Die vier Auskunftsschreiben in diesem Verzeichnis
gehören zum zweiten Lauf; in Fall 3 wurden sie nicht verwendet.

Was die Gesellschaft in Fall 3 auf Rückfrage nachgeliefert hat, liegt mit
dem festgehaltenen Fall unter
`pakete/baldrian-klv-tg2015-fall3/nachlieferung/`: fünf Auskünfte, die
Herabsetzungsanteile einzelner Policen, drei Erwartungswert-Dateien eines
zweiten Lieferlaufs und die Festlegung der übernehmenden Gesellschaft zum
Tarifplan der Migration. Die Auskünfte 1 bis 4 tragen dieselben Nummern wie
die Auskunftsschreiben hier, haben aber einen anderen Inhalt: Es sind die
Antworten auf die Rückfragen von Fall 3.

Dort und nicht hier liegen sie, weil das Paket sie über seine Prüfsummen
bindet. Wie Fall 3 nachgefahren wird: `deploy/welt/README.md`.
