# Pruefplan des Maintainers vor dem Push (Lauf 2)

Kurzplan fuer die inhaltliche Pruefung VOR dem ersten Push des
fallbericht-Strangs (Entscheid 2026-09-02: erst pruefen, dann
veroeffentlichen — der Push macht das oeffentliche Repo sichtbar).
Abhaken hier; Befunde gehen an die dev-session (lokal fixen, Tests
und Suite wie gehabt, Leitfaden-Kennzahl am Ende nachziehen).

Geaenderter Entscheid zur Seite (2026-09-02, ersetzt "Inhalts-Nachzug
nach dem main-Merge"): Die Vorzeigeseite traegt VOR der Sichtung nur
noch Lauf-2-Inhalte — keine Mischung aus Lauf 1 und Lauf 2. Statische
(gepflegte) Stellen werden erfasst und soweit moeglich automatisiert
(generieren statt pflegen); Prosa-Schoenheit ist nachrangig, fuer
Fallbeschreibungen unerheblich.

## 1. [ ] Vorzeigeseite sichten (Anfang)

Voraussetzung: Inhalts-Nachzug der vorzeige-session ist durch
(Reihenfolge dort: regie/-Sperrlisten-Fix, dann Nachzug, dann
frischer Build). Sichtung headless ueber die Caddy-Route.

Quellen:
- Gebauter Auftritt (werkzeuge/auftritt.py, kompletter Baum;
  Bereitstellung meldet die vorzeige-session)
- Liste der statischen Stellen mit Automatisierungs-Vorschlag je
  Stelle (liefert die vorzeige-session mit dem Nachzug)

## 2. [ ] Lauf-Ergebnisse fachlich pruefen

Quellen (Bericht zuerst, dann Primaerbelege im Fall):
- docs/faelle/baldrian-lauf2.md — Abschlussbericht (Gate-Tabelle,
  sieben Feststellungen, Datenluecken-Behandlung, offener Punkt)
- faelle/baldrian-klv-tg2015-lauf2/abgeleitet/berichte/:
  aktuartest.json (A-M1), aktuartest-A-M2.json, aktuartest-A-M3.json,
  migrationssuite.json (A-M4-Grundlage), migrationsabnahme.html
- faelle/baldrian-klv-tg2015-lauf2/abgeleitet/schichten/
  verankerung_schichten.json — Schichtbeleg (834 getragen,
  Residuensumme -0,14 EUR, max 0,02)
- Zeichnungs-Snapshots unter faelle/baldrian-klv-tg2015-lauf2/
  entscheide/: A-Q1 fd793260, A-M1 fb1550c0, A-M2 411ac21c,
  A-M3 d260e621, A-M4 32682e95 (Rolle plv-aktuar via
  Zeichnungsordnung)
- A-Box-Journal (abgeleitet/abox/) fuer die vierzehn
  Diskrepanz-Einzelentscheide der Quellenauswertung

## 3. [ ] System- und Review-Sicht pruefen

Quellen:
- dev-docs/lauf2-auswertung.md — Vorher/Nachher beider Dimensionen,
  Betriebs-Lehren, Workshop-Rohstoff
- dev-docs/review-lauf2-befunde.md — 22 Befunde mit Status
- dev-docs/offene-punkte.md — bewusst Offenes (S2/S3/S4/S7, Backlog)

## 4. [ ] Fragen stellen, Befunde melden

An die dev-session, einzeln oder gesammelt; jede Zahl wird auf Zuruf
aus den Primaerbelegen nachgerechnet, nicht aus dem Gedaechtnis.

## 5. [ ] Abschluss

- dev zieht die Leitfaden-Kennzahlen auf den Endstand nach
  (selbst-inklusive Zaehlung, dev-docs/pr-leitfaden-lauf2.md)
- Push fallbericht + PR-Anlage (Kopfteil des Leitfadens als
  PR-Beschreibung)
