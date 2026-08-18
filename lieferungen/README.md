# Lieferungen

Frachtgut der Showcase-Migrationen: je Verzeichnis die Lieferung eines
fiktiven abgebenden Unternehmens, mit der jeder eine Migration selbst
durchführen kann. Alles synthetisch, ohne realen Kundenbezug — und die
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

**Durchführung:** siehe `ONBOARDING.md`, Abschnitt 3 („Run the
showcase migration").
