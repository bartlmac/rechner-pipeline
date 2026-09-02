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
3. [x] Nacharbeits-Commits nach fallbericht holen: merge
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
   ERLEDIGT 2026-09-01, merge-session (Hauptbaum von der dev-session
   stillgehalten). Merge-Commit ef2cb1b, Eltern 3f33bfd + 33e9dec.
   Alle fuenf vorhergesagten Konflikte traten auf und wurden nach den
   hinterlegten Regeln aufgeloest; Suite 1421 passed (1408 auf dem
   Zweig + 13 aus der Nacharbeit), code_karte befunde [].
   Drei Dinge, die im Konfliktbild nicht standen und beim Aufloesen
   anfielen:
   - cli_abschluss.py kollidierte NICHT, importierte aber den alten
     Funktionsnamen. Beim Ziehen auf pruefe_pb1_eingaenge musste er mit,
     sonst waere es erst in der Suite aufgefallen.
   - Die beiden Fassungen der Engine wurden gegeneinander geprueft:
     sachlich identisch, Unterschiede ausschliesslich in den
     Umbenennungen. Der Umzug ist damit nachweislich verlustfrei.
   - Der CHANGELOG haette die Reviewrunde T14 zweimal beschrieben
     (einmal hier, einmal aus main mitgebracht). Der mitgebrachte
     Abschnitt steht jetzt auf T16 und verweist nach oben; die doppelte
     gamma1-Aussage ist entfernt, die Versionsbegruendung blieb, weil
     sie oben fehlte.
4. [x] quellsystem -> fallbericht gemergt (2026-09-01, dev-session;
   Merge-Commit a16a43d). Konfliktfrei wie geprobt, rein additiv;
   volle Suite auf dem Ergebnis 1453 passed, code_karte befundfrei.
   OFFEN (Maintainer): Branch quellsystem loeschen — geht erst, wenn
   der Worktree ~/git/rechner-pipeline-quellsystem aufgeloest oder
   umgehaengt ist (ein ausgecheckter Branch laesst sich nicht
   loeschen); Worktree behalten oder aufloesen ist Maintainer-Entscheid.
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
6. [x] Fall-Lauf 2 auf fallbericht fahren (Owner: Lauf-Sessions des
   Maintainers, Vier-Rollen-Regie; dev-session als Systembetreuung).
   Pruefpunkt: A-M4-Kette steht. ABGESCHLOSSEN 2026-09-02: alle fuenf
   Gates auf Systemstand 4b1abf0 gezeichnet (A-M4 834/834, Schicht
   -0,14 EUR); 23 Korrekturen final, Bilanz in
   docs/faelle/baldrian-lauf2.md und dev-docs/lauf2-auswertung.md. Korrektur-Zaehlung fuer den
   PR-Schnitt-Vorbehalt (Gebiet Kern/Gates) beginnt mit 1:
   Vorlauf-Fix der Zeichnungsordnungs-Allowlist (A-K1 war zeichenbar,
   aber keiner Rolle zuweisbar; gate_entscheid, vor Laufstart).
   Stand 2026-09-01, waehrend des Laufs: acht Korrekturen (Details in
   regie/drehbuch-lauf2.md), davon im Kern/Gates-Gebiet die
   Serien-Zustandsableitung f9af1cc, der Schichtbeleg-Producer
   46cb6a9, Schicht-Auslassungs-Ausweis acefbd8, Scheiben-gamma1
   fc01663 (Kern 3.2.0), Stornoabschlag je Baustein 2b35155
   (Kern 3.3.0) und der Kandidaten-Korridor 2c4e0b2 — der
   Schnitt-Vorbehalt von Schritt 8 ist damit sicher ausgeloest, die
   A/B/C-Grenzen sind nach Laufende neu zu bewerten.
6b. [ ] T18-Korrekturen (Owner: nach Maintainer-Entscheid;
   fruehestens nach Anstoss von Fall-Lauf 2 — so entschieden
   2026-09-01): eigener Korrektur-PR gegen main, Geschwister zu
   PR #10; danach main -> fallbericht nachziehen (klein). Der
   A/B/C-Schnitt von Schritt 8 ist NICHT betroffen. Inhalt und
   Konstruktionszwaenge: dev-docs/offene-punkte.md (T18) — vor
   Baubeginn entscheiden, ob das Laufmanifest optional-mit-Vorbehalt
   kommt oder die Lauf-2-Artefakte neu erzeugt werden.
7. [ ] vorzeige-url -> fallbericht (Owner: merge-session, mit der
   vorzeige-Session abstimmen; test_baldrian_e2e-Kopplung dort
   verifizieren). Pruefpunkt: Suite gruen, Vorzeigeseite rendert.
8. [ ] fallbericht -> main als EIN PR mit Review-Leitfaden (Owner:
   Maintainer). REVIDIERT 2026-09-02 (Maintainer-Entscheid nach
   Lauf-Ende): Der 2026-09-01 im Plan selbst angelegte Vorbehalt ist
   eingetreten — die 23 Lauf-Korrekturen liegen quer durch das A/B/C-
   Gebiet (Kern-Verfahren, QA-Engines, Gates, Bestand), ein
   chronologischer Drei-Schnitt truege fast die ganze Kette in PR C
   und zerrisse kausale Zusammenhaenge (Toleranz-Skalierung zieht
   sich durch drei Schichten). Die Review-Last traegt ein
   vorgeschalteter adversarialer Multi-Agent-Review der 23er-Kette
   (Muster T16/T18, Befunde vor dem PR gefixt); der menschliche
   PR-Review folgt dem Leitfaden: docs/faelle/baldrian-lauf2.md
   (fachlich) + dev-docs/lauf2-auswertung.md (System) + die 23
   begruendeten Commit-Botschaften als Gliederung. Pruefpunkt: kein
   bestandsfuehrung-Commit als eigene Aenderung (schon in main),
   Suite gruen, Review-Befunde geschlossen.
   STAND 2026-09-02: Der adversariale Review ist gelaufen (22
   Rohbefunde: 11 bestaetigt und gefixt, S1/S5 dev-bestaetigt und
   gefixt, S2/S3/S4/S7 als offene Punkte, 2 verworfen —
   dev-docs/review-lauf2-befunde.md traegt den Status je Befund);
   kein Befund beruehrt die gezeichneten Ergebnisse. Die E2E-Fixture
   des zweiten Laufs ist eingefroren (tests/test_baldrian2_e2e.py,
   822ce75). Suite 1534, Kern 3.4.0 — der PR ist schnittbereit,
   es fehlt nur noch Schritt 7 (vorzeige-url-Merge). Der
   Review-Leitfaden steht: dev-docs/pr-leitfaden-lauf2.md (Kopfteil
   = PR-Beschreibung, danach Leseweg, fuenf Lesestufen,
   Schwerpunkt-Dateien, Nachpruefbarkeit).
   HISTORISCH (Entscheid 2026-09-01, durch den Vorbehalt abgeloest):
   drei chronologische Schnitte A/B/C —
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
