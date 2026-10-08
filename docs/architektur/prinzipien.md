# Prinzipien P1-P10 der Migrations-Pipeline

Die normative Grundlage des Systems (beschlossen in der
Architektur-Fragerunde 2026-08-14, hier team-sichtbar in Vollform).
Nicht verhandelbar; Änderungen sind ein A-O1-artiger Vorgang mit
dem Maintainer.

**P1 — Provenance auf Attributebene.** Jede Aussage in der A-Box
trägt Quelle (Datei + SHA-256 + Fundstelle), erzeugenden Akteur
(Modell + Skill + Git-Stand des Setups), Zeitstempel, Konfidenz. Ohne
lückenlose Rückverfolgbarkeit ist keine Abnahme durch einen
Verantwortlichen Aktuar möglich.

**P2 — Widerspruch ist ein Modellobjekt, kein Fehler.** Widersprechen
sich Quellen (Normalfall, nicht Ausnahme), entsteht eine Diskrepanz
mit beiden Lesarten und ihren Belegen. Kein stiller Overwrite, keine
Mehrheitsentscheidung durch ein Modell. Auflösung ist ein expliziter
Vorgang mit benanntem menschlichem Verantwortlichen; Agenten dürfen
ausschliesslich VORLAEUFIG auflösen (blockt jede Annahme).

**P3 — Unsicherheit ist explizit.** `nicht_belegt` (gesucht, nicht
gefunden), `mehrdeutig` und `widerspruechlich` sind unterscheidbare
Zustände — und unterscheidbar von `fehlt_in_extraktion` (nie
gesucht: der gefährliche stille Fall).

**P4 — Trennung probabilistisch / deterministisch.** LLM-Agenten
extrahieren, schlagen vor, klassifizieren. Sie rechnen nicht,
vergleichen nicht, entscheiden nicht über Vollständigkeit oder
Konflikte. Vergleich, Validierung, Coverage, Struktur-Urteil und
Abnahme sind deterministischer Code.

**P5 — Validierung als ausführbare Constraints.** Regeln der T-Box
(Pflichtfelder, Wertebereiche, Konsistenz) sind Code, der gegen jede
A-Box läuft — nicht Prosa.

**P6 — Coverage statt Plausibilität.** Messbar ist, welcher Anteil
des T-Box-Pflichtumfangs je Tarif belegt ist und woher. Der
gefährliche Fehler ist nicht die falsche Extraktion, sondern die
stillschweigend fehlende. Nicht Prüfbares wird AUSGEWIESEN, nie
still übersprungen.

**P7 — Bidirektionalität.** Aus der A-Box ist eine menschenlesbare
Fachspezifikation generierbar — das Dokument, das der Fachbereich im
Abnahmegate liest. Generiert schlägt handgeschrieben.

**P8 — Testfälle referenzieren Ontologieknoten.** Golden-Master- und
Abnahme-Fälle hängen an Klassen/Instanzen der A-Box, nicht an
Codezeilen; eine T-Box-Änderung zeigt ihre Testabdeckungslücke.
(Stand v0.1: nur grob eingelöst — siehe Pipeline-Dokument
Abschnitt 8.)

**P9 — Gates erzeugen unveränderliche Artefakte.** Jedes menschliche
Gate schreibt einen inhaltsadressierten Snapshot: Artefakt-Hashes,
Systemstand, Entscheider, Rolle, Begründung; Snapshots verketten
ihre Vorgänger. Die Annahme RECHNET ihre Vorbedingungen (Gates grün
und an denselben Stand gebunden). Gate P-K1 schreibt entsprechend einen
inhaltsadressierten Beleg je Generation. A-M4 verlangt genau die
Generationenmenge der aktuellen A-Box und gleicht A-Box- sowie Systemstand
jedes Belegs ab. Eine menschliche Annahme wird mit einem ausserhalb des Falls
verwahrten HMAC-Schlüssel autorisiert. P9 validiert beim Lesen Schema,
vollständigen kanonischen Hash, daraus abgeleiteten Dateinamen, Signatur und
den zyklenfreien Vorgängergraph mit genau einer Spitze (ADR-008).
Der Fall-Scope bestimmt die Pflichtbelege JE GATE (ADR-009 mit
ADR-010-Nachtrag): A-M4 verlangt in beiden Scopes P-Q3, A-Q1, die geltende
A-M1-Annahme (Rolle ``am1_snapshot`` — aktuarielle vor finanzieller
Abnahme) und P-K1; Bestandsfälle binden zusätzlich P-B1, vollständige
Suite und Abnahmebericht auf denselben Eingangs-, A-Box-, System- und
Zwei-Stichtagsstand. A-M1 verlangt im Bestands-Scope Testergebnis und
Bericht des aktuariellen Tests, im Tarif-Scope keine eigenen Rollen. A-M4 hasht ihre aktuellen Bytes und das von P-B1 benannte
Portfolio neu, führt die P-B1-Engines erneut aus und rendert den Abnahmebericht
zum Bytevergleich deterministisch neu (ADR-009).

**P10 — Kontext ist Architekturgegenstand.** Übergaben zwischen
Agenten laufen über persistierte Artefakte, nie über
Konversationsverlauf. Kein Agent erhält Rohmaterial, wenn ein
strukturiertes Derivat existiert; Rohquellen werden deterministisch
vorverdichtet, bevor ein Modell sie sieht.
