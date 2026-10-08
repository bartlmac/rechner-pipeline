# Prinzipien P1 bis P10 der Migrations-Pipeline

Die Grundsätze, nach denen die Migrations-Pipeline gebaut ist, beschlossen
am 2026-08-14. Ein Prinzip ändert sich nur durch eine Entscheidung des
Maintainers, festgehalten in einem ADR. Code, Tests und ADRs verweisen mit
der Nummer auf sie.

**P1 — Herkunft je Aussage.** Jede Aussage in der A-Box trägt ihre Quelle
(Datei, SHA-256, Fundstelle), den erzeugenden Akteur (Modell, Skill,
Git-Stand), einen Zeitstempel und eine Konfidenz. Ohne lückenlose
Rückverfolgbarkeit kann kein Verantwortlicher Aktuar abnehmen.

**P2 — Ein Widerspruch ist ein Objekt, kein Fehler.** Widersprechen sich
Quellen, und das ist der Normalfall, entsteht eine Diskrepanz mit beiden
Lesarten und ihren Belegen. Nichts wird still überschrieben, und kein
Modell entscheidet per Mehrheit. Aufgelöst wird ausdrücklich, von einem
benannten Menschen. Agenten dürfen nur vorläufig auflösen, und eine
vorläufige Auflösung blockiert jede Annahme.

**P3 — Unsicherheit ist ausdrücklich.** `nicht_belegt` (gesucht, nicht
gefunden), `mehrdeutig` und `widerspruechlich` sind unterscheidbare
Zustände, und alle drei sind unterscheidbar von `fehlt_in_extraktion` (nie
gesucht). Der letzte ist der gefährliche, weil er still ist.

**P4 — Vorschlag und Rechnung sind getrennt.** Agenten extrahieren,
schlagen vor und klassifizieren. Sie rechnen nicht, vergleichen nicht und
entscheiden nicht über Vollständigkeit oder Konflikte. Vergleich,
Validierung, Abdeckung, Struktururteil und Abnahme sind deterministischer
Code.

**P5 — Regeln sind ausführbar.** Die Regeln der T-Box (Pflichtfelder,
Wertebereiche, Konsistenz) sind Code, der gegen jede A-Box läuft, nicht
Prosa.

**P6 — Abdeckung statt Plausibilität.** Gemessen wird, welcher Anteil des
Pflichtumfangs der T-Box je Tarif belegt ist und woher. Der gefährliche
Fehler ist nicht die falsche Extraktion, sondern die fehlende, die niemand
bemerkt. Was sich nicht prüfen lässt, wird ausgewiesen, nie still
übersprungen.

**P7 — Beide Richtungen.** Aus der A-Box lässt sich eine lesbare
Fachspezifikation erzeugen: das Dokument, das der Fachbereich bei der
Abnahme liest. Erzeugt ist besser als von Hand geschrieben.

**P8 — Testfälle hängen an Knoten der Ontologie.** Golden-Master- und
Abnahmefälle hängen an Klassen und Instanzen der A-Box, nicht an
Codezeilen. Eine Änderung der T-Box zeigt so ihre Lücke in der
Testabdeckung. In v0.1 ist das erst grob eingelöst
([Migrations-Pipeline v0.1](migrations-pipeline-v01.md), Abschnitt 8).

**P9 — Gates erzeugen unveränderliche Belege.** Jedes menschliche Gate
schreibt einen Snapshot, der über seinen Inhalt adressiert ist: Hashes der
Artefakte, Systemstand, Entscheider, Rolle und Begründung. Snapshots
verketten ihre Vorgänger. Eine Annahme rechnet ihre Vorbedingungen nach:
Die vorausgehenden Gates sind grün und an denselben Stand gebunden. Eine
menschliche Annahme ist mit einem Schlüssel signiert, der außerhalb des
Falls liegt (ADR-008). Welche Belege ein Gate verlangt, bestimmt der Scope
des Falls (ADR-009, ADR-010). Die Migrationsabnahme `A-M4` rechnet ihre
Belege neu, statt ihnen zu glauben.

**P10 — Kontext ist Gegenstand der Architektur.** Agenten übergeben
einander Arbeit über gespeicherte Artefakte, nie über den Verlauf eines
Gesprächs. Kein Agent bekommt Rohmaterial, wenn es eine strukturierte
Ableitung gibt; Rohquellen werden deterministisch vorverdichtet, bevor ein
Modell sie sieht.
