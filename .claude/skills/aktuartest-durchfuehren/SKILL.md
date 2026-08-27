---
name: aktuartest-durchfuehren
description: >-
  Run the deterministic actuarial test of a portfolio migration and
  prepare the decision template for the Verantwortlicher Aktuar:
  per-contract comparison at each contract's OWN anchor date t_a (at the
  exact computation point, no interpolation, no summation — only
  distribution measures of the residuals, clustered by history type) on a
  documented sample, rendered by the aktuartest gate as the G-A template.
  Trigger when a migration case has a transformed portfolio plus
  delivered per-contract expectation values and the actuarial acceptance
  (Gate G-A) is due — it precedes Gate G-2. Skip for: the full-portfolio
  controlling at the migration date (pruefe-migrationscontrolling, Gate
  G-2), deciding the acceptance itself (human, Gate G-A), computing any
  actuarial value by hand (deterministic engine only).
---

# Aktuariellen Test durchführen

## Rolle und Ziel

Du führst den DETERMINISTISCHEN aktuariellen Test einer
Bestandsmigration aus und bereitest die Entscheidungsvorlage für die
AKTUARIELLE ABNAHME (Gate G-A, Verantwortlicher Aktuar) auf. Der Test
misst die methodische Güte: je Vertrag am EIGENEN Verankerungszeitpunkt
t_a gegen die gelieferten Erwartungswerte — nicht den Gesamtbestand am
Migrationsstichtag (das ist das Controlling, Gate G-2, das G-A ZWINGEND
nachfolgt).

Werkzeuge (alle deterministisch, du rechnest NIE selbst):

- `qa/stichprobe` — die belegte Stichprobe: `ziehe(profil, police_ids)`
  mit benanntem Profil (v0 kennt genau `vollbestand`), deterministisch,
  mit ausgewiesener Grundgesamtheit. Die Ziehung ist Teil des Belegs
  (`als_beleg()`), die Police-Liste gehört dazu.
- `qa/aktuarieller_test` — die Test-Engine: je Vertrag ein
  `VerankerungsPruefung`-Auftrag, Vergleich am Rechenpunkt (ein
  unterjähriges `monate_ta` ist ein harter Fehler, keine
  Interpolation), keine Summation der Vergleichsgrößen — nur
  Verteilungsgrößen der |Residuen| (Maximum, hohe Perzentile,
  Betragssumme der Abweichungen), geclustert nach `historientyp`.
  Kranke Lieferdaten werden je Vertrag isoliert und als Befund
  ausgewiesen.
- `python -m rechner_pipeline.gates.aktuartest` — rechnet das
  Engine-Ergebnis von innen nach außen nach und rendert die
  G-A-Vorlage (HTML) mit Stichproben-Beleg im Kopf; schreibt
  `aktuartest.gate.json` in die Diagnostics. Exit-Codes: `0` Vorlage
  vollständig und Test bestanden, `30` Test nicht bestanden, `20`
  Ergebnis unlesbar oder inkonsistent, `2` Aufruf unvollständig.

## Nicht verhandelbar

- Werte rechnet NUR die Engine. Du baust die Prüfaufträge
  (`VerankerungsPruefung`) aus den Fall-Artefakten — transformierter
  Bestand, Lesart der Rechnungsgrundlagen aus der Spez, gelieferte
  Erwartungswerte, Historie je Vertrag — und interpretierst Urteile.
- `monate_ta` ist ein VERTRAGSATTRIBUT (der letzte exakte Rechenpunkt
  des Vertrags, volle Jahre), kein Suite-Parameter. Verlangt jemand
  einen unterjährigen Vergleichszeitpunkt: STOPP, Mensch fragen — die
  Engine lehnt ihn hart ab, und das ist Absicht (Grundsatzdokumentation 9.12).
- Toleranzen kommen aus `qa` (REL_TOL/ABS_TOL) und werden NIE
  aufgeweicht, um "grün zu werden".
- Die Stichprobe wird GEZOGEN und belegt, nie von Hand
  zusammengestellt. "Vollständig" heißt hier: die Stichprobe wurde
  abgearbeitet (`stichprobe_vollstaendig`) — die Nichtprüfung der
  Nicht-Stichprobe ist kein Befund, sondern die Definition.
- Mitgelieferte Prüfsummen sind TRANSPORTSICHERUNG: Sie gehen als
  `transportsicherung=` an die Engine, werden im Bericht getrennt
  ausgewiesen und fließen nie in das fachliche Urteil ein.
- Jeder Fehlschlag und jeder Befund geht an den Menschen. Du
  korrigierst keine Erwartungswerte und keine Lieferung.
- Der Bericht ist die Entscheidungsvorlage; die aktuarielle Abnahme
  selbst ist Gate G-A (Mensch, Entscheid-Snapshot,
  `gates/gate_entscheid --gate G-A`). Ein Exit-Code `0` heißt "Vorlage
  vollständig und Test bestanden", NICHT "abgenommen". Eine ANNAHME
  verlangt `--freigabe-schluessel <datei>` (ADR-008); die
  Schlüsseldatei gehört dem Menschen — ein Agent kann an einem
  menschlichen Gate ausschließlich ablehnen. G-A geht G-2 voraus; der
  G-2-Entscheid pinnt den geltenden G-A-Snapshot (`ga_snapshot`).

## Ablauf

1. Vollständigkeit prüfen: transformierter Bestand, Spez (Lesart),
   gelieferte Erwartungswerte je Vertrag, Historie (für t_a und
   Historientyp). Fehlt etwas: STOPP.
2. Stichprobe ziehen: `qa.stichprobe.ziehe("vollbestand",
   police_ids)` über die Policennummern des transformierten Bestands.
   Ein anderes Profil existiert in v0 nicht — der Wunsch danach ist
   eine Teamaufgabe (ADR-010 Abschnitt 5), kein Ad-hoc-Parameter.
3. Je Vertrag der Stichprobe den Prüfauftrag bauen:
   - `monate_ta`: volle Vertragsmonate am Verankerungszeitpunkt
     (letzter exakter Rechenpunkt, Vielfaches von 12; aus
     `bestand.fuehrung.months_between` und dem Vertragsbeginn).
   - `historientyp`: Cluster der Historie (z. B. `ohne_gevo`, `pex`,
     `dynamik`) — er strukturiert die Verteilungsauswertung.
   - `erwartet`: die gelieferten Werte mit Kern-Größennamen
     (`kVx_MRV`, `RKW`, `BJB`, `VS_bfr`); nur liefern, was geliefert
     wurde — die Engine lehnt unbekannte Größen hart ab.
   - `scheiben` (nach dynamischen Erhöhungen) und
     `beitragsfrei_seit_jahr` (PEX) aus der Historie.
   Dann `qa.aktuarieller_test.pruefe_stichprobe(vertraege, stichprobe,
   transportsicherung=..., system=...)` laufen lassen und das Dict
   unverändert als JSON in den Fall schreiben (`json.dump`, Ziel
   `abgeleitet/berichte/aktuartest.json`). Das JSON wird NIE von Hand
   nachgebessert — das Gate rechnet die Zusammenfassung gegen die
   Einzelurteile nach und bricht sonst mit `20` ab.
4. Vorlage erzeugen und protokollieren:

   ```
   python -m rechner_pipeline.gates.aktuartest \
       --fall faelle/<fall> \
       --titel "Aktuarieller Test <Fall>"
   ```

   Der Bericht landet unter `<fall>/abgeleitet/berichte/
   aktuartest.html`, der Ledger unter `<fall>/abgeleitet/diagnostics/`.
   Ein roter Bericht wird geschrieben wie ein grüner — er IST das
   Beweisstück.
5. Ergebnis dem Verantwortlichen Aktuar zur G-A-Entscheidung
   vorlegen, STOPP.

## Ausbau (geplant, hier verankern)

- Golden-Master-Tests der Migration: definierte Referenz-Verträge mit
  eingefrorenen Erwartungswerten als dauerhafte Regression — Definition
  folgt, dieser Skill ist ihr Zuhause.
- Weitere Stichprobenprofile (geschichtet, risikoorientiert) über die
  Erweiterungsstelle `qa.stichprobe.PROFILE` — je Profil eine
  Teamentscheidung mit ADR-010-Nachzug.
- Das methodische Residuum R der Korrekturschicht (Grundsatzdokumentation Abschnitt 9): Die
  Engine trägt den Platz benannt und leer, bis es ein R gibt.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Verankerungszeitpunkt ist nicht als voller Rechenpunkt
  bestimmbar (unterjährige Anforderung, unklare Historie).
- Ein anderes Stichprobenprofil als `vollbestand` wird gewünscht.
- Eine Toleranzfrage stellt sich (nie selbst entscheiden).
- Die Engine isoliert Verträge als nicht rechenbar (kranke
  Lieferdaten) — das ist ein Befund für den Menschen, kein Grund, die
  Verträge auszuschließen.
