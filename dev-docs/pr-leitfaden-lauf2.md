# Review-Leitfaden: PR fallbericht -> main (Baldrian-Uebernahme, Lauf 2)

Dieser Leitfaden ist die Lesehilfe fuer den einen grossen PR
(Merge-Plan Schritt 8, Entscheid 2026-09-02). Er sagt, was der PR
enthaelt, was davon schon wie geprueft ist, in welcher Reihenfolge man
liest, und wo die schaerfsten Augen hingehoeren. Der Kopfteil taugt
als PR-Beschreibung; ab "Leseweg" beginnt die Arbeitsanleitung.

## Was dieser PR ist

Der komplette zweite Baldrian-Migrationslauf als ein Strang: die
Ausweitung des aktuariellen Tests auf drei Abnahmen, die
Kern-Mathematik der Korrekturschicht und der Herabsetzung, der
Fall-Datenraum der zweiten Lieferung (Serien als Regelfall), die 23
Korrekturen aus dem Lauf selbst, die Nacharbeit (adversarialer
Review mit Fixes, E2E-Fixture, Abschlussdokumentation) und die
Vorzeigeseite samt Auftritts-Werkzeugen (Merge-Plan Schritt 7).

Kennzahlen: 208 Commits auf Basis 33e9dec (Merge PR #10), 301
Dateien, +74,0k/-3,0k Zeilen — gezaehlt EINSCHLIESSLICH dieses
Leitfaden-Stands; wer nachrechnet (git log main..fallbericht),
muss auf dieselbe Zahl kommen. Endzustand: Suite 1544 gruen (0
Skips), Kern 3.4.0, Fall vollstaendig gezeichnet (fuenf Gates auf
Systemstand 4b1abf0; A-M4 834/834, Schichtbeleg-Residuensumme
-0,14 EUR).

Warum EIN PR statt des urspruenglichen Drei-Schnitts: Die 23
Lauf-Korrekturen liegen quer durch alle drei Gebiete (Kern-Verfahren,
QA-Engines, Gates, Bestand); ein chronologischer Schnitt truege fast
die ganze Kette im letzten PR und zerrisse kausale Zusammenhaenge —
die Toleranz-Skalierung etwa zieht sich durch drei Schichten. Die
Begruendung samt verworfener Alternative steht im Merge-Plan
(dev-docs/merge-plan-lauf2.md, Schritt 8).

## Was schon geprueft ist

Damit Review-Zeit dorthin geht, wo sie Neues findet:

- **Lauf-Verifikation**: Jede der 23 Korrekturen ist durch den Lauf
  selbst verifiziert — fuenf volle Abnahme-Kaskaden (je
  Systemstand-Wechsel neu), am Ende 2508 Einzelpruefungen ueber 834
  Vertraege ohne Befund und eine praktisch leere Korrekturschicht
  (max. Einzelabweichung 0,02 EUR).
- **Adversarialer Vorab-Review der 23er-Kette** (Muster T16/T18,
  2026-09-02): fuenf thematische Reviewer, je Befund zwei
  unabhaengige Skeptiker. 22 Rohbefunde — 11 bestaetigt und gefixt,
  2 strittige zusaetzlich als dev bestaetigt und gefixt, 4 als
  offene Punkte dokumentiert, 2 verworfen. Kein Befund beruehrt die
  gezeichneten Ergebnisse. Status je Befund samt Herleitung:
  dev-docs/review-lauf2-befunde.md.
- **Externe Runden T14/T16** deckten die Bestandsfuehrung — die ist
  bereits in main (PR #10) und hier NICHT Gegenstand.
- **Zwei E2E-Fixturen** frieren beide Laufe als Regressionstests ein
  (tests/test_baldrian_e2e.py, tests/test_baldrian2_e2e.py): die
  Ketten rechnen bei jedem Suite-Lauf gegen die unabhaengig
  gelieferten Erwartungswerte.

## Leseweg

Erst das Ergebnis, dann der Weg, dann der Code:

1. **docs/faelle/baldrian-lauf2.md** — der fachliche
   Abschlussbericht: was uebernommen wurde, die sieben
   Feststellungen zum Quell-Tarifwerk, die Methodik, die Behandlung
   der Datenluecke ohne Punktschaetzung.
2. **dev-docs/lauf2-auswertung.md** — die Systemsicht:
   Vorher/Nachher in beiden Dimensionen (Kern/Bestand und
   KI/Betrieb), die neuen Faehigkeiten, die Betriebs-Lehren.
3. **dev-docs/review-lauf2-befunde.md** — was der Vorab-Review fand
   und was daraus wurde; die vier bewusst offen gelassenen Punkte
   stehen begruendet in dev-docs/offene-punkte.md.
4. **Die Commits in sechs Lesestufen** (unten) — die
   Commit-Botschaften sind die Gliederung: jede nennt das WARUM vor
   dem WAS, Reviews folgen ihnen schneller als dem Diff.

## Die sechs Lesestufen

Die Stufen folgen der Chronologie des Branches; die Grenzen sind
dieselben, an denen der historische Drei-Schnitt geprueft wurde.

### Stufe 1 — Aktuarieller Test in drei Abnahmen (33e9dec..7e6184a, 31 Commits)

A-M1/A-M2/A-M3 als getrennte Abnahmen mit eigenen Profilen,
Gate-Namen und Ledger-Contract (ADR-010/012), Doku-Umbau.
Schwerpunkt: qa/aktuarieller_test.py, gates/aktuartest_lauf.py.
Prueffrage: Ist der Ledger-Contract (ein JSON, Exit-Codes,
.gate.json) an jedem Gate gleich gelebt?

### Stufe 2 — Kern-Mathematik (7e6184a..1c43737, 40 Commits)

Korrekturschicht (Verankerung, Formfunktion, Rumpfjahr),
Zahlungspfade, Herabsetzung als fortgefuehrter geteilter Vertrag, die
vier Produzenten-Kommandos. Schwerpunkt: kern/korrekturschicht.py,
kern/beitragsreduktion.py, kern/rechenkern.py. Das ist die Stufe fuer
die tiefste aktuarielle Pruefung — hier lohnt Nachrechnen einzelner
Formeln mehr als Breite. Prueffrage: Traegt die Terminalbedingung der
Schicht (Zahlungsjahre bis n-1, Wert am Ablauf null) auch die
Randfaelle, und bleiben die Charakterisierungs-Referenzwerte des
Kerns unangetastet?

### Stufe 3 — Fall-Datenraum der zweiten Lieferung (1c43737..0983554, 78 Commits)

Uebernahme-Producer, Serien-Datenraum, Tarifzellen/Merkmale,
quellsystem-Tooling (KOPIE des Kommutationskerns, bewusst ohne
Import-Beziehung zum Zielkern), vorzeige-Werkzeuge, Skills und Doku.
Breiteste, aber flachste Stufe — vieles ist Werkzeug und Doku.
Prueffrage: Haelt die Schichtenkarte (python -m
rechner_pipeline.ontologie.code_karte befundfrei; kommutationskern
nur von qa/ konsumiert, quellsystem/ ohne Zielkern-Import)?

### Stufe 4 — Die 23 Lauf-Korrekturen (0983554..4b1abf0, 29 Commits)

Das Herzstueck: Korrekturen, die der Lauf erzwungen hat, jede mit
begruendeter Botschaft und im Lauf verifiziert. Thematische Bloecke
(die Nummern folgen der Chronik in dev-docs/lauf2-auswertung.md):

- **Kern-Verfahren**: Scheiben-gamma1 als Lieferungseigenschaft
  (fc01663, Kern 3.2.0), Stornoabzug je Baustein (2b35155, Kern
  3.3.0), Teilkuendigung als drittes Herabsetzungs-Verfahren
  (bd41f56).
- **Schicht und Verankerung**: Terminalbedingung am Ablauf (e4230e9),
  Zustandsbau des Verankerungs-Producers (7325e87), Basis-Wahl
  vx_mrv (fd359f1), Schichtbeleg-Producer (46cb6a9).
- **Serien-Ableitungen**: Rundungsphantom-Wache (5dc5133),
  Kandidaten-Bestimmung ueber Beitrags-/Ankergleichung (1ecd315),
  Anker-Diskriminierung und Anteils-Unerheblichkeit (8c5698c),
  Serien-Zustandsableitung (f9af1cc).
- **AT-Engine**: Kandidaten-Korridore (2c4e0b2), Antrags-Verwurf
  (a1ce4aa, 2c6ad48), quell_komponenten (abd31ca).
- **Suite und Gates**: Schicht im Controlling (900d990),
  Jahrestags-Konvention (7325e87), Teilkuendigungs-GeVo (a5b86e7),
  komponentenskalierte Toleranzen bis in die Gate-Nachrechnung
  (71213a6, 1bb4e3d), Datei-Form-Embedding der Spec (4b1abf0).

Prueffragen: Sind die Vorgaben aller neuen Flags wirklich das
Lauf-1-/PLV-Verhalten (bitgenau — die Suite behauptet es, der Diff
muss es zeigen)? Ist jede Toleranz-Aufweitung aus der Lieferung
begruendet (je fuer sich gerundete Komponente) und nirgends ein
bequemes Pauschalmass?

### Stufe 5 — Nacharbeit (4b1abf0.. ohne den Vorzeige-Ast, 21 Commits)

Abschlussbericht und Auswertung (5983417), die 13
Review-Nacharbeits-Commits (009464d..af2718a, je Commit ein Befund
mit Referenz auf die Befundliste), E2E-Fixture des zweiten Laufs
(822ce75), Merge-Plan-Staende, dieser Leitfaden samt Nachtraegen —
und die Versionierung der vier Auskunftsschreiben der Lieferung
(ce89ad6). Zu letzteren die Antwort auf die naheliegende
Reviewer-Frage, warum Dokumente der abgebenden Gesellschaft im Repo
liegen: Die Lieferungs-Ablage lieferungen/ ist der versionierte
Lieferungs-Nachweis des (simulierten) Falls — wie schon bei der
ersten Lieferung — und die Quelle der E2E-Fixture-Schnitte; die
eingecheckten Fassungen sind per diff identisch mit den im
Fall-Eingang registrierten. Prueffrage: Deckt jeder Review-Fix
seinen Befund mit einem Test ab, der die naheliegende Mutation
faengt (Mutationsfaenger sind in den Tests benannt)?

### Stufe 6 — Vorzeigeseite und Auftritts-Werkzeuge (Merge 9c1f36a, 13+1 Commits)

Der zuletzt eingemergte Seitenast (vorzeige-url, Schritt 7): der
Pfefferminzia-Auftritt als erzeugte Seite (vorzeige-seite/-Quellen,
Fiktions-Banderole erzwungen), die Werkzeuge falldaten/auftritt/
drift/vorzeigeseite in werkzeuge/ (Drift-Prinzip: Darstellungen
werden generiert oder importiert, nie abgetippt; Veroeffentlichen
bleibt menschlich) und zwei aktualisierte Testdateien. WICHTIG fuer
die Review-Last: Diese Commits liefen NICHT durch den adversarialen
Vorab-Review — das Risiko ist begrenzt (kein Kern, keine Gates,
keine Rechenwege; Werkzeug- und Seiten-Code), der Merge wurde
konfliktfrei mit voller Suite auf dem Ergebnis verifiziert (1544,
inklusive der Datei-Kopplung ueber umbaubudget.json), und der Stand
ist funktional abgenommen: Die komplette Auftritts-Kette baute mit
Exit 0 (34 gerenderte Seiten, 0 tote Links, Landkarte/Techstack/
ADRs frisch aus dem Repo erzeugt; Rendering-Pruefung der
vorzeige-Session, Details im Merge-Plan Schritt 7). Prueffragen:
Blockt die Regie-Sperre der Veroeffentlichungswerkzeuge alle
Spielleiter-Bereiche (bekannte Luecke: regie/ fehlt noch in der
Sperrliste — dokumentierter Merkposten, Fix folgt VOR der naechsten
Veroeffentlichung nach dem main-Merge)? Und erzeugt der Auftritt
wirklich alles aus Repo-Quellen statt aus gepflegten Kopien?

## Wo die schaerfsten Augen hingehoeren

In absteigender Prioritaet — Risiko mal Neuheit:

1. **kern/beitragsreduktion.py** — drei Verfahren, davon
   TEILKUENDIGUNG neu samt 3.4.0-Ausweitung in den beitragsfreien
   Nachlauf; die Wachen an allen drei Eingaengen.
2. **bestand/migrationszugang.py** — Serien-Rekonstruktion,
   Kandidaten-Bestimmung, PEX-Einpunkt-Inversion. Fuer letztere das
   Aequivalenz-Argument in Commit 7c8dfb2 nachvollziehen: Die
   Umwandlungsfaktoren der Bausteine sind NICHT gleich, tragfaehig
   ist die Homogenitaet in der beitragsfreien Gesamtsumme — der
   Zonen-Beleg-Test rechnet beides vor.
3. **qa/migrationssuite.py** — RED-Zweige (drei Verfahren,
   Folge-GeVo-Regeln, Kettung), Jahrestags-Konvention,
   Komponentenskalierung.
4. **kern/korrekturschicht.py** — Terminalbedingung und
   Formbasis-Trennung (Stuetzstellen bis n, Zahlungsjahre bis n-1).
5. **gates/abnahmebericht.py** — die unabhaengige Nachrechnung des
   Gates (Grenze: der komponenten-Zaehler kommt aus dem Suite-Report
   selbst; als offener Punkt S7 dokumentiert).

## Was NICHT Gegenstand dieses PRs ist

- **Bestandsfuehrung** — in main ueber PR #10; Pruefpunkt des
  Merge-Plans: kein bestandsfuehrung-Commit erscheint hier als
  eigene Aenderung (nur ueber die Merge-Commits ef2cb1b u. a.).
- **T18-Korrekturen** — eigener Korrektur-PR gegen main
  (Merge-Plan Schritt 6b, Maintainer-Entscheid steht aus).
- **Vier offene Review-Punkte** (S2 Verankerungs-Verfahren als
  Fachentscheid, S3 Provenienz-Haertung, S4 Schicht ueber
  Teilkuendigung, S7 Zaehler-Obergrenze) und der Nacharbeits-Backlog
  (AT-Schicht-Asymmetrie, Kaskaden-Rezept,
  Neuzeichnungs-Verhaeltnismaessigkeit, Extraktions-Skill-Luecken) —
  bewusst dokumentiert in dev-docs/offene-punkte.md, nicht hier
  nachgeschoben.

## Nachpruefbarkeit

Behauptungen dieses Leitfadens selbst pruefen, nicht glauben:

- Volle Suite: `.venv/bin/python -m pytest` (1544 erwartet; in
  Worktrees weniger — zwei Pruefungen brauchen den Hauptbaum bzw.
  Docker, siehe Merkposten im Merge-Plan Schritt 7).
- Beide Ketten am Stueck: `.venv/bin/python -m pytest
  tests/test_baldrian_e2e.py tests/test_baldrian2_e2e.py`.
- Kern-Versionslog: src/rechner_pipeline/kern/__init__.py (3.1.0 ->
  3.4.0, je Version die fachliche Begruendung; Vorgabe-Rechenwerte
  unveraendert).
- Architektur-Gates: `python -m rechner_pipeline.ontologie.code_karte`
  (Schichten-Allowlist) und `python -m
  rechner_pipeline.ontologie.code_index --tests tests` (driftfrei).
- Wirkungsbereich eines beliebigen Commits: `git show <sha> --stat`
  plus `git diff <sha>^ <sha> --name-only | python -m
  rechner_pipeline.ontologie.impact`.
