---
name: aktuartest-durchfuehren
description: >-
  Run the deterministic actuarial test of a portfolio migration and
  prepare the decision template for the Verantwortlicher Aktuar. Three
  separate acceptances, each with its own sample, criteria and report:
  A-M1 Stichtagstest (takeover state plus the next contract anniversary),
  A-M2 Verlaufstest (5 and 10 years, maturity), A-M3
  Geschaeftsvorfalltest (one point per business event, checked on the
  change in Deckungskapital). Per contract, at the contract's OWN
  computation points — no interpolated comparison, no summation, only
  distribution measures of the residuals, clustered by history type and
  occasion. Trigger when a migration case has a transformed portfolio
  plus delivered per-contract expectation values and one of the actuarial
  acceptances is due — all three precede Gate A-M4. Skip for: the full-portfolio
  controlling at the migration date (pruefe-migrationscontrolling, Gate
  A-M4), deciding the acceptance itself (human, Gate A-M1), computing any
  actuarial value by hand (deterministic engine only).
---

# Aktuariellen Test durchführen

## Rolle und Ziel

Du führst den DETERMINISTISCHEN aktuariellen Test einer
Bestandsmigration aus und bereitest die Entscheidungsvorlage für die
AKTUARIELLE ABNAHME (Gate A-M1, Verantwortlicher Aktuar) auf. Der Test
misst die methodische Güte: je Vertrag am EIGENEN Verankerungszeitpunkt
t_a gegen die gelieferten Erwartungswerte — nicht den Gesamtbestand am
Migrationsstichtag (das ist das Controlling, Gate A-M4, das A-M1 ZWINGEND
nachfolgt).

Werkzeuge (alle deterministisch, du rechnest NIE selbst):

- `qa/stichprobe` — die belegte Stichprobe: `ziehe(profil, police_ids)`
  mit benanntem Profil, deterministisch, mit ausgewiesener
  Grundgesamtheit. Die Ziehung ist Teil des Belegs (`als_beleg()`), die
  Police-Liste gehört dazu. Zwei Profile: `vollbestand` (der ganze
  Bestand) und `geschichtet` (je Historientyp-Cluster eine feste
  Anzahl, Ziehreihenfolge über einen Hash mit dokumentiertem
  Startwert).
- `qa/testprofil` — das Profil je Test: Stichprobenweite im Klartext
  und die Abnahmekriterien. `Kriterium` trägt beides — die Toleranz des
  Einzelwerts (`abs_tol`, `rel_tol`) und die Abnahmegrenze der
  Verteilung (`max_abs_residuum`, `p95_abs_residuum`). Eine Grenze
  unter dem Rundungsrauschen einer centgerundeten Lieferung wird hart
  abgelehnt: Sie misst die Darstellung, nicht die Rechnung.
- `qa/aktuarieller_test` — die Test-Engine: je Vertrag eine
  `Vertragspruefung` mit einer Liste von `Pruefpunkt`en. Ein Vertrag
  besteht nur, wenn JEDER seiner Punkte besteht. Keine Summation der
  Vergleichsgrößen — nur Verteilungsgrößen der |Residuen| (Maximum,
  hohe Perzentile, Betragssumme), geclustert nach `historientyp` UND
  `anlass`. Kranke Lieferdaten werden je Vertrag isoliert und als
  Befund ausgewiesen.
- `python -m rechner_pipeline.gates.aktuartest --abnahme A-M1|A-M2|A-M3`
  — rechnet das Engine-Ergebnis von innen nach außen nach und rendert
  die Vorlage (HTML) mit Profil- und Stichproben-Beleg im Kopf; jede
  Abnahme schreibt ihr eigenes Ergebnis, ihren eigenen Bericht und
  ihren eigenen Ledger. Ein Ergebnis, dessen Profil nicht zur
  angeforderten Abnahme passt, wird abgelehnt. Exit-Codes: `0` Vorlage
  vollständig und Test bestanden, `30` Test nicht bestanden, `20`
  Ergebnis unlesbar oder inkonsistent, `2` Aufruf unvollständig.

## Nicht verhandelbar

- Werte rechnet NUR die Engine. Du baust die Prüfaufträge
  (`Vertragspruefung` mit ihren `Pruefpunkt`en) aus den Fall-Artefakten
  — transformierter Bestand, Lesart der Rechnungsgrundlagen aus der
  Spez, gelieferte Erwartungswerte, Historie je Vertrag — und
  interpretierst Urteile.
- Der Zeitpunkt ist ein VERTRAGSATTRIBUT, kein Suite-Parameter. Stichtags-
  und Verlaufspunkte liegen auf dem Vertragsjahrestag; ein Wert dazwischen
  wäre interpoliert und die Engine lehnt ihn hart ab. Unterjährig ist
  ausschließlich ein Geschäftsvorfall, weil dort die Mischungskonvention
  den ausgezahlten Betrag bestimmt — sie ist der Gegenstand der Prüfung,
  nicht ihre Störung (Grundsatzdokumentation 9.12, ADR-010).
- Verlangt jemand einen unterjährigen Stichtags- oder Verlaufspunkt:
  STOPP, Mensch fragen.
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
  selbst ist Gate A-M1 (Mensch, Entscheid-Snapshot,
  `gates/gate_entscheid --gate A-M1`). Ein Exit-Code `0` heißt "Vorlage
  vollständig und Test bestanden", NICHT "abgenommen". Eine ANNAHME
  verlangt `--freigabe-schluessel <datei>` (ADR-008); die
  Schlüsseldatei gehört dem Menschen — ein Agent kann an einem
  menschlichen Gate ausschließlich ablehnen. A-M1 geht A-M4 voraus; der
  A-M4-Entscheid pinnt den geltenden A-M1-Snapshot (`am1_snapshot`).

## Ablauf

1. Vollständigkeit prüfen: transformierter Bestand, Spez (Lesart),
   gelieferte Erwartungswerte je Vertrag, Historie (für t_a und
   Historientyp). Fehlt etwas: STOPP.
2. Abnahme wählen. Es sind drei, jede mit eigener Stichprobe, eigenen
   Kriterien und eigener Unterschrift; jede läuft für sich:
   - `A-M1` Stichtagstest: je Vertrag ZWEI Punkte — Übernahmestand am
     Verankerungszeitpunkt (`anlass="uebernahme"`) und nächster
     Vertragsstichtag laut Fortschreibung (`anlass="fortschreibung"`).
   - `A-M2` Verlaufstest: nach 5 und 10 Jahren sowie zum Ablauf
     (`anlass="verlauf"`). Verträge mit kürzerer Restlaufzeit tragen
     den Punkt schlicht nicht — das ist kein Befund, muss aber in der
     Stichprobenweite stehen.
   - `A-M3` Geschäftsvorfalltest: je Vorfall ein Punkt, `anlass` ist
     der Vorfall-Code (`STO`, `PEX`, `ABL`, `TOD`, `ERH`, `RED`).
     Die Herabsetzung `RED` verlangt zusätzlich
     `parameter={"anteil": f}` am Prüfpunkt — wie weit der Vertrag
     geteilt wird, steht im Vorfall und nicht im Vertrag, und die
     Engine rät es nicht. Sie liegt immer auf dem Vertragsstichtag.
3. Stichprobe ziehen: `qa.stichprobe.ziehe(profil, police_ids, ...)`.
   `vollbestand` für kleine Bestände, `geschichtet` (mit `schichten`,
   `je_schicht`, `saat`), sobald der Bestand seltene Historientypen
   enthält — eine ungeschichtete Ziehung kann einen Cluster
   vollständig verfehlen, und der Test bestünde, ohne den Vorgang je
   gerechnet zu haben. Welches Profil und wie weit, entscheidet das
   Aktuariat; ein drittes Profil ist eine Teamaufgabe, kein
   Ad-hoc-Parameter.
4. Profil bauen: `qa.testprofil.vorlage(kennung, weite=...)` gibt den
   begründeten Ausgangspunkt je Abnahme — Toleranzen, die aus der Natur
   des Vergleichs folgen, nicht gesetzte Zahlen. Die Weite ist Pflicht
   und steht IM KLARTEXT (sie trägt den Beleg im Bericht). Wer im Fall
   abweicht, baut das `Testprofil` selbst und sagt in `bemerkung`,
   warum. Bei `A-M3` sind die Kriterien je Vorfallart geschlüsselt,
   weil dort der Vorfall über die Toleranz entscheidet.

   Eine Toleranz NIE aufweiten, damit ein Befund verschwindet. Weicht
   das Quellsystem methodisch ab — etwa bei der Herabsetzung, wenn es
   mit Stornoabzug rechnet und das Zielsystem verlustfrei —, ist die
   Abweichung der Sachverhalt, den die Abnahme sehen soll. Sie gehört
   in die Abnahmeentscheidung, belegt durch die Beschreibung des
   Quellverfahrens, nicht in eine stillere Grenze.
5. Je Vertrag der Stichprobe die `Vertragspruefung` bauen:
   - `punkte`: die `Pruefpunkt`e der gewählten Abnahme, je mit
     `monate` (volle Vertragsmonate seit Beginn), `erwartet` und
     `anlass`.
   - `historientyp`: Cluster der Historie (z. B. `ohne_gevo`, `pex`,
     `dynamik`) — er strukturiert die Verteilungsauswertung.
   - `erwartet`: die gelieferten Werte mit Kern-Größennamen
     (`kVx_MRV`, `RKW`, `BJB`, `VS_bfr`, `dDK`); nur liefern, was
     geliefert wurde — die Engine lehnt unbekannte Größen hart ab.
     `dDK` (Veränderung des Deckungskapitals) ist der tragende
     Prüfwert des Geschäftsvorfalltests und nur dort zulässig.
   - `scheiben` (nach dynamischen Erhöhungen) und
     `beitragsfrei_seit_jahr` (PEX) aus der Historie. Die Engine lehnt
     `RKW` und `BJB` im beitragsfreien Zustand ab und `VS_bfr`
     ausserhalb davon — die Größen müssen zum Zustand passen.
   Dann `qa.aktuarieller_test.pruefe_stichprobe(vertraege, stichprobe,
   profil, transportsicherung=..., system=...)` laufen lassen und das
   Dict unverändert als JSON in den Fall schreiben (`json.dump`, Ziel
   `abgeleitet/berichte/aktuartest.json` für A-M1, mit Abnahme-Suffix
   für A-M2 und A-M3). Das JSON wird NIE von Hand nachgebessert — das
   Gate rechnet die Zusammenfassung gegen die Einzelurteile nach und
   bricht sonst mit `20` ab.
6. Vorlage erzeugen und protokollieren:

   ```
   python -m rechner_pipeline.gates.aktuartest \
       --fall faelle/<fall> \
       --abnahme A-M1 \
       --titel "Stichtagstest <Fall>"
   ```

   Der Bericht landet unter `<fall>/abgeleitet/berichte/`, der Ledger
   unter `<fall>/abgeleitet/diagnostics/`; beide tragen die Abnahme im
   Namen, sonst überschreiben sich die drei Tests gegenseitig. Ein
   roter Bericht wird geschrieben wie ein grüner — er IST das
   Beweisstück.
7. Ergebnis dem Verantwortlichen Aktuar zur Entscheidung über DIESE
   Abnahme vorlegen, STOPP. Jede der drei wird einzeln gezeichnet:
   Der Aktuar kann den Stichtagstest abnehmen und den Verlaufstest
   zurückweisen.

## Ausbau (geplant, hier festgehalten)

- Golden-Master-Tests der Migration: definierte Referenz-Verträge mit
  eingefrorenen Erwartungswerten als dauerhafte Regression — Definition
  folgt, dieser Skill ist ihr Zuhause.
- Weitere Stichprobenprofile (nach Restlaufzeit-Klasse oder
  Vorfallart) über die Erweiterungsstelle `qa.stichprobe.PROFILE`. Die
  Schichtung nach Historientyp ist gebaut (`geschichtet`, ADR-010
  Abschnitt 5); die übrigen sind beschrieben
  (`dev-docs/aktuarieller-test-at1-at2-at3.md`) und nicht gebaut.
- Invalidisierung und Reaktivierung im Geschäftsvorfalltest: Die Engine
  lehnt `dDK` für beide hart ab, weil sie den Zustand des BU-Graphen
  wechseln. Sie kommen dazu, wenn die BU-Zustandsbewertung angeschlossen
  ist.
- Das methodische Residuum R der Korrekturschicht (Grundsatzdokumentation Abschnitt 9): Die
  Engine trägt den Platz benannt und leer, bis es ein R gibt.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Verankerungszeitpunkt ist nicht als voller Rechenpunkt
  bestimmbar (unterjährige Anforderung, unklare Historie).
- Ein Stichprobenprofil jenseits von `vollbestand` und `geschichtet`
  wird gewünscht.
- Die Herabsetzung `RED` soll unterjährig geprüft werden — dafür
  fehlt die Rumpfjahr-Konvention (`dev-docs/offene-punkte.md`).
- Eine Toleranzfrage stellt sich (nie selbst entscheiden).
- Die Engine isoliert Verträge als nicht rechenbar (kranke
  Lieferdaten) — das ist ein Befund für den Menschen, kein Grund, die
  Verträge auszuschließen.
