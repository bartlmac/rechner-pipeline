# Merge-Plan Richtung Fall-Lauf 2

Koordination der offenen Branch-Zusammenfuehrungen (Stand 2026-09-01).
Gemeinsame Arbeitsgrundlage fuer die beteiligten Sessions und den
Maintainer; wer einen Schritt abschliesst, hakt ihn hier ab (Datum +
Kuerzel). Versioniert, damit jeder Worktree denselben Stand sieht —
Regie-Notizen zum Vorfuehrfall liegen bewusst NICHT hier, sondern im
lokalen Regie-Bereich (oeffentliches Repo).

## Lage (erhoben 2026-09-01)

Gemeinsamer Boden: main 5e36810 (= origin/main). Kein Branch ist
behind main.

| Branch | Commits ahead | gepusht | Inhalt |
|---|---|---|---|
| feat/bestandsfuehrung (PR #10) | 9+ | ja | Bestandsfuehrungs-Strang in externer Review-Runde (T16); Nacharbeit laeuft |
| fallbericht | 135 | nein | Fall-/Pipeline-Arbeit; ENTHAELT feat/bestandsfuehrung, feat/migrationszugang, lauf/baldrian-uebernahme |
| quellsystem | 9 eigene | nein | Quellsystem-Tooling + Baldrian-Lieferung 2; Merge nach fallbericht konfliktfrei geprobt |
| vorzeige-url | 13 eigene | nein | Vorzeigeseite; Kopplung tests/test_baldrian_e2e.py |
| feat/test-controlling-trennung | 1 | nein | ADR-010-Doku, haengt einzeln auf main |

Enthalten in fallbericht und nach dessen Merge loeschbar:
lauf/baldrian-uebernahme, feat/migrationszugang.

## Grundsaetze

- KRITISCH: fallbericht baut auf feat/bestandsfuehrung auf. Nacharbeit
  dort NUR als additive Commits — kein Rebase, kein Amend — sonst
  divergiert fallbericht von seiner eigenen Basis.
- Push macht der Maintainer. Volle Suite gruen vor jedem Merge-Commit.
- Der volle Vorfuehr-Lauf 2 ist der Integrationstest NACH Schritt 4;
  ein zusaetzlicher Testlauf nach weiteren Merges ist nicht noetig
  (Suite genuegt dort). Ein maschineller Trockenlauf der Lieferung 2
  durch die Zielpipeline ist gelaufen (gruen; Protokoll in der
  Regie-Notiz des Hauptbaums).

## Schritte

1. [ ] T16-Nacharbeit auf feat/bestandsfuehrung (Owner: merge-session;
   additive Commits). Scope-Entscheid des Maintainers 2026-09-01:
   Toepfe A+B werden umgesetzt, Topf C ist benannte Folgearbeit
   (Betriebsvertrag des atomaren Writers, zwei Mutationsanker,
   Gate-SemVer-Regel). Pruefpunkt: A+B gruen, C benannt; Suite gruen.
2. [ ] PR #10 -> main mergen (Owner: Maintainer). Pruefpunkt:
   origin/main traegt die Nacharbeit.
3. [ ] Nacharbeits-Commits nach fallbericht holen: merge
   feat/bestandsfuehrung (oder main) -> fallbericht (Owner:
   merge-session + dev-session gemeinsam). ERWARTETER KONFLIKT, ein
   Commit, eine Datei: gates/bestand_validate.py — der Engine-Umzug
   (pruefe_b1_eingaenge -> bestand/vorbedingungen.py, Schichtenkarte
   verbietet bestand -> gates) kollidiert mit den
   fallbericht-Umbenennungen im selben Block (pruefe_pb1_eingaenge,
   GATE P-B1.bestandspruefung). Aufloesungsregel: Umzugsdatei
   uebernehmen, die fallbericht-Namen in vorbedingungen.py ziehen,
   Block im Gate loeschen. Pruefpunkt: volle Suite auf fallbericht
   gruen; code_karte befundfrei.
4. [ ] quellsystem -> fallbericht mergen (Owner: merge-session).
   Konfliktfrei geprobt (2026-09-01; rein additiv: quellsystem/,
   lieferungen/baldrian-2/, 5 Testdateien, eine .gitignore-Zeile).
   Pruefpunkt: volle Suite gruen (Referenz: 1436 passed auf dem
   Probe-Stand). Danach Branch quellsystem loeschen; Worktree
   aufloesen oder fuer Quell-Nacharbeiten behalten (Maintainer).
5. Vorbereitung Lauf 2:
   a. [x] (2026-09-01, dev) Meldungs-Vorverdichtung liest Text-PDF:
      ADR-016, pypdf==6.16.2, Commit c5b7df1 auf fallbericht (Scan
      ohne Textlayer blockiert hart; OCR Backlog/extern). Team braucht
      nach Pull einmal `pip install -e ".[dev]"`.
   b. [x] (2026-09-01) Schluessel + Zeichnungsordnung: EIN neuer
      Schluessel genuegte (plv-va; mensch = vorhandener Schluessel des
      Maintainers; quelle-experte zeichnet keine Gates und braucht
      keinen). faelle/zeichnungsordnung.json traegt beide Fingerprints
      und laedt fehlerfrei durch gate_entscheid.
   c. Hinweis fuer den Lauf-2-Operator (keine Vorarbeit): Spec um
      monate_ta (Berechnung aus BEGINN/Stichtag; Berechnungskatalog
      ggf. erweitern) und dk_ta (= DECKKAP) ergaenzen, sonst entsteht
      keine verankerung.parquet.
6. [ ] Fall-Lauf 2 auf fallbericht fahren (Owner: dev-session;
   menschliche Gates nach Zeichnungsordnung). Pruefpunkt: A-M4-Kette
   steht.
7. [ ] vorzeige-url -> fallbericht (Owner: merge-session, mit der
   vorzeige-Session abstimmen; test_baldrian_e2e-Kopplung dort
   verifizieren). Pruefpunkt: Suite gruen, Vorzeigeseite rendert.
8. [ ] fallbericht -> main als PR (Owner: Maintainer; erst nach 2
   und 6). Pruefpunkt: PR enthaelt keine bestandsfuehrung-Commits mehr
   als eigene Aenderung (schon in main).
9. [ ] Aufraeumen: Branches lauf/baldrian-uebernahme,
   feat/migrationszugang loeschen; feat/test-controlling-trennung
   entscheiden (1 Doku-Commit: mergen oder verwerfen).
