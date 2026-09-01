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

1. [x] T16-Nacharbeit auf feat/bestandsfuehrung (Owner: merge-session;
   additive Commits). Scope-Entscheid des Maintainers 2026-09-01:
   Toepfe A+B werden umgesetzt, Topf C ist benannte Folgearbeit.
   Pruefpunkt: A+B gruen, C benannt; Suite gruen.
   ERLEDIGT 2026-09-01, merge-session. Drei additive Commits auf
   feat/bestandsfuehrung (7f00742 bleibt Vorfahr, fallbericht behaelt
   seine Basis):
   - bcc0657 Engine-Umzug nach bestand/vorbedingungen.py
   - f08a1a1 Topf A: T16-01/02, der Abschluss konsumiert das ganze
     Lauf-Bundle durch dieselbe Engine wie Gate B1; neu --bis
     (Fortschreibungs-Horizont). BREAKING.
   - 76d4bd5 Topf B: T16-03 Endlichkeit, T16-04 Genau-einmal-Publish
     (os.link), T16-05 Berichtswachposten an der CLI-Grenze, T16-06a
     Dateirechte, T16-07 Teil, T16-08 Teil (CHANGELOG/README),
     T16-09 Skill-Paritaet ueber Verzeichnisvergleich.
   Suite 969 passed (Basis 956). Jede Korrektur per Mutation
   gegengeprueft: neun Mutationen, alle von den vorgesehenen Tests
   rot gemeldet.
   Topf C bleibt offen und ist in der Commit-Botschaft von 76d4bd5
   sowie im CHANGELOG benannt: Betriebsvertrag des atomaren Writers
   (fsync, Temp-Reste nach SIGKILL, ENAMETOOLONG) und die
   repositoryweite Gate-SemVer-Regel. Die urspruenglich als Topf C
   gefuehrten "zwei Mutationsanker" sind erledigt bzw. gegenstandslos:
   der gamma1-Anker ist in 76d4bd5 gebaut (End-to-End ueber physisches
   Parquet und die CLI), und ein B1-Versionsanker ist kein Test --
   weil die nachgelagerten Pruefer die Version dynamisch lesen, kann
   keine Zusicherung entscheiden, ob eine Aenderung Major war. Das
   gehoert zur SemVer-Regel.
   OFFEN fuer den Maintainer: dev-docs/offene-punkte.md existiert auf
   feat/bestandsfuehrung nicht (kam erst mit 953c6e1). Die
   Backlog-Eintraege fuer Topf C werden deshalb bei Schritt 3 gesetzt,
   wenn die Nacharbeit auf fallbericht ankommt.
2. [x] PR #10 -> main mergen (Owner: Maintainer). Pruefpunkt:
   origin/main traegt die Nacharbeit.
   ERLEDIGT 2026-09-01, Maintainer (Merge vorbereitet: merge-session).
   Lokaler Merge-Commit 33e9dec nach der Hauskonvention von PR #9
   ("Merge PR #10: ..."), zwei Eltern 5e36810 + 76d4bd5, danach zwei
   Pushes in dieser Reihenfolge: erst feat/bestandsfuehrung, dann main.
   Die Reihenfolge war noetig, damit PR #10 die drei
   Nacharbeits-Commits ueberhaupt zeigt — bei umgekehrter Reihenfolge
   haette GitHub ihn als gemergt markiert, ohne sie je darzustellen,
   und die Antwort an die externe Review-Runde verweist genau darauf.
   Ergebnis: origin/main 33e9dec, PR #10 MERGED mit zwoelf sichtbaren
   Commits, volle Suite auf dem gemergten Stand 969 gruen.
   Kontrolliert: 7f00742 und 76d4bd5 beide in main, fallbericht haengt
   unveraendert an seiner Basis.
3. [ ] Nacharbeits-Commits nach fallbericht holen: merge
   feat/bestandsfuehrung (oder main) -> fallbericht (Owner:
   merge-session + dev-session gemeinsam). ERWARTETE KONFLIKTE:
   FUENF Dateien, je ein Block (Ausnahme Landkarte: zwei). Am
   2026-09-01 im Wegwerf-Worktree gegen fallbericht 26f35c8 gemessen,
   nicht geschaetzt — die fruehere Angabe "ein Commit, eine Datei" war
   zu optimistisch. Alle Konflikte sind mechanisch:
   - gates/bestand_validate.py — der Engine-Umzug
     (pruefe_b1_eingaenge -> bestand/vorbedingungen.py, Schichtenkarte
     verbietet bestand -> gates) gegen die fallbericht-Umbenennungen im
     selben Block. Aufloesung: Umzugsdatei uebernehmen, die
     fallbericht-Namen (pruefe_pb1_eingaenge, GATE
     P-B1.bestandspruefung) in vorbedingungen.py ziehen, Block im Gate
     loeschen.
   - bestand/abschluss.py — die beiden Seiten sind KOMPLEMENTAER, nicht
     konkurrierend: fallbericht setzt den Abschluss auf 0444, die
     Nacharbeit veroeffentlicht ihn exklusiv (os.link). Aufloesung:
     beides behalten, in dieser Reihenfolge — erst
     write_portfolio(..., exklusiv=True) im try/except FileExistsError,
     dann chmod(0o444) auf das Ergebnis. Wichtig: os.replace
     ueberschreibt eine 0444-Datei anstandslos (nachgemessen, Ergebnis
     0600); erst der exklusive Publish macht den Schreibschutz zu mehr
     als einer Geste.
   - tests/test_agent_workflow_docs.py — fallbericht pflegt die
     Handliste weiter, die Nacharbeit ersetzt sie durch einen
     Verzeichnisvergleich. Aufloesung: Seite der Nacharbeit nehmen; sie
     deckt die elf Paare auf fallbericht automatisch ab, genau dafuer
     wurde sie gebaut.
   - docs/architektur/landkarte.md — erzeugte Datei, beide Seiten
     aendern Kantengewichte. NICHT von Hand aufloesen, sondern nach dem
     Merge neu erzeugen (ontologie.landkarte, drei Mermaid-Bloecke:
     schichten, knoten, modul kern).
   - README.md — beide Seiten redigieren; Textmerge von Hand.
   Pruefpunkt: volle Suite auf fallbericht gruen; code_karte
   befundfrei; landkarte-Regression gruen.
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
8. [ ] fallbericht -> main als DREI gestapelte PRs (Owner: Maintainer;
   erst nach 2 und 6). Entscheid des Maintainers 2026-09-01: nicht ein
   PR, sondern drei chronologische Schnitte entlang der bestehenden
   Kette -- rein additiv, keine History wird umgeschrieben. Pruefpunkt
   je PR: kein bestandsfuehrung-Commit als eigene Aenderung (schon in
   main), Suite gruen.
   Ein thematisch sauberer Schnitt ist NICHT zu haben: die Themen liegen
   chronologisch verschraenkt (Korrekturterm 27.08., Rumpfjahr-
   Konvention 31.08., beides Kern). Sie zu trennen hiesse cherry-picken,
   und das wuerde fallbericht von seiner Basis abreissen.
   Schnittpunkte, alle am 2026-09-01 auf gruen geprueft (getrennte
   Worktrees, parallel, ohne die G-2-Kollision paralleler Laeufe im
   selben Baum):
   - PR A bis 7e6184a "aktuartest-durchfuehren auf die drei Abnahmen":
     aktuarieller Test in drei Abnahmen, Gate-Namen (ADR-010/012),
     Doku-Umbau. 31 Commits, 158 Dateien, +8.6k. Suite 1021.
   - PR B bis 1c43737 "die vier Produzenten-Kommandos": Korrekturschicht,
     Zahlungspfade, Herabsetzung, die vier Kommandos. 40 Commits,
     81 Dateien, +17.9k. Suite 1212.
   - PR C Rest bis fallbericht: Migrationsfall Baldrian (Uebernahme,
     Bestandsdarstellung, Werkzeuge) plus quellsystem, vorzeige-url und
     Lauf 2. 59+ Commits, 101 Dateien, +13.9k. Suite 1408 am Stand
     34336c4 (noch ohne die T16-Fixes aus Schritt 3).
   Begruendung fuer den Split: 150 Commits sind fuer einen Menschen kein
   Review. Die zwei externen Runden haben ihren Wert an einem
   9-Commit-PR bewiesen (sechzehn echte Befunde, zwei materiell). PR B
   ist aktuarielle Mathematik -- genau das, was der Verteiler beurteilen
   kann.
   VERWORFEN wurde, die PRs vor Lauf 2 zu ziehen. Gruende: dieser Plan
   erklaert Lauf 2 selbst zum Integrationstest nach Schritt 4, und
   Lauf 2 belastet nicht nur PR C, sondern ueber Stufe 2 und 3 auch die
   Gates aus A und die Kernmathematik aus B; "gemergt, dann repariert"
   ist genau das Muster, das die Reviewrunden T14/T16 erzeugt hat; und
   ein Review, das waehrend seiner Laufzeit unter sich veraendert wird,
   verbrennt geliehene Reviewer-Zeit.
   VORBEHALT: Korrekturen aus Lauf 2 landen am Kettenende, also in PR C
   -- auch wenn sie Code aus A oder B betreffen. Chronologische Schnitte
   koennen das nicht umsortieren. Faellt in Lauf 2 viel in A/B-Gebiet
   an, ist der Schnitt danach neu zu bewerten, statt ihn jetzt
   festzuzurren. Die PR-Branches werden deshalb erst nach Lauf 2
   angelegt.
9. [ ] Aufraeumen: Branches lauf/baldrian-uebernahme,
   feat/migrationszugang loeschen.
   feat/test-controlling-trennung: VERWERFEN, geprueft 2026-09-01. Der
   Branch traegt dieselben fuenf Dateien wie der aelteste
   fallbericht-Commit, aber in aelterer Fassung -- ADR-010 steht dort
   auf "Entwurf, Umsetzung offen" statt "angenommen und umgesetzt",
   qa/stichprobe.py ist 91 Zeilen und tests/test_stichprobe.py
   75 Zeilen aermer. fallbericht ist strikt weiter; es geht nichts
   verloren.
