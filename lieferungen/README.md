# Lieferungen

Frachtgut der Showcase-Migrationen: je Verzeichnis die Lieferung eines
fiktiven abgebenden Unternehmens, mit der jeder eine Migration selbst
durchführen kann. Die Lieferungen enthalten keine echten Vertrags-,
Kunden- oder Bestandsdaten; Unternehmen und Bestände sind frei erfunden
— und die
Lieferungen können (gewollt) Fehler und Eigenheiten enthalten: genau
die soll die Pipeline finden.

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
Beitragsfreistellungen und Herabsetzungen VOR dem Migrationsstichtag.
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

**Durchführung:** siehe `ONBOARDING.md`, Abschnitt 3 („Run the
showcase migration").
