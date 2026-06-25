# Demo & Replay — kostenfreie, reproduzierbare Vorführung der Pipeline

Dieses Verzeichnis ist die **Demo-Schaltzentrale**. Es enthält vorbereitete
Modell-Ausgaben („Fixtures"), mit denen sich der **echte** agentische
Pipeline-Workflow inklusive Selbstkorrektur-Schleife **ohne API-Aufruf,
kostenfrei und jedes Mal identisch** vorführen lässt — ideal für Präsentationen.

## Überblick: was hier zusammenspielt

- **Replay-Provider** (`--provider replay`) — ruft kein Modell, sondern gibt
  vorbereitete Ausgaben aus einem Verzeichnis (`RP_REPLAY_DIR`) in Reihenfolge
  zurück. Der Rest der Pipeline (Validierung, Golden-Master, Log) läuft echt.
- **Fixtures** (`*_iteration.txt`) — eingefrorene Modell-Ausgaben (FILE-Blöcke
  mit erzeugtem Code), eine pro agentischer Iteration.
- **Workflow-Log** (`RP_WFLOG=1`) — menschen-lesbarer Verlauf je Iteration.
- **Fixture-Capture** — jeder **echte** Lauf sichert seine Modell-Ausgaben
  automatisch als wiederverwendbares Replay-Set weg (siehe unten).

## Schnellstart: die kostenfreie Demo

    RP_WFLOG=1 RP_REPLAY_DIR=demo_fixtures \
      python agentic_pipeline.py --provider replay --test-mode fixed --max_retries_main 2

Das durchläuft die Reparaturschleife sichtbar **2 -> 1 -> 0** und endet mit
„617 Werte geprüft — alle stimmen mit dem Excel-Original".

## Die Fixtures in diesem Verzeichnis

Die drei Dateien sind aus **einem echten Lauf abgeleitet**. `03_iteration.txt`
ist die vollständige, echte Ausgabe; in den ersten beiden wurden gezielt
Skalare im Golden-Master-Vertrag (`golden_master_outputs()`) **weggelassen**,
damit echte Abweichungen entstehen, die die Schleife real korrigiert:

- `01_iteration.txt` — Skalare `Bxt` und `Pxt` fehlen  -> 2 Abweichungen
- `02_iteration.txt` — Skalar `Pxt` fehlt               -> 1 Abweichung
- `03_iteration.txt` — vollständig                      -> 0 Abweichungen (bestanden)

Der Replay-Provider gibt sie in sortierter Reihenfolge zurück; jeder agentische
Durchlauf nimmt die nächste, die letzte wird wiederholt.

## Workflow-Log (`RP_WFLOG`)

`RP_WFLOG=1` schaltet den menschen-lesbaren Log ein (sonst läuft die Pipeline
technisch/still). Er zeigt je Iteration — ausschliesslich aus echten Lauf-Daten,
nichts hartkodiert:

- **Auslesen:** ausgelesene Artefakte (echte Namen) + ein paar echte
  Excel-Originalformeln aus den Sheet-CSVs.
- **Erzeugen:** Prompt-Größe + Korrektur-Kontext, Prompt-Anfang (erste ~280
  Zeichen), erzeugte Dateien mit Zeilenzahl, das Funktions-Inventar von
  `actuarial.py`, ein echter Code-Auszug der Rechenlogik, sowie ein **Diff von
  `golden_master_outputs()` gegenüber der Vor-Iteration** (zeigt die
  Selbstkorrektur in echtem Code).
- **Validieren:** eine **Soll/Ist-Tabelle** je Skalar (Excel-Soll vs.
  berechnet, Δ, Status), ein **Auszug der Verlaufs-/Tabellenwerte** (ebenfalls
  Soll/Ist) und die Golden-Master-Abweichungen.
- **Abschluss:** eine Zusammenfassungs-Karte (migrierte Werte, Iterationen,
  Konvergenz `2 -> 1 -> 0`, Laufzeit, bestanden/nicht bestanden).

Der `RP_WFLOG_MAX_ITEMS`-Cap begrenzt die Länge gelisteter Namen.

## Eigene Replay-Sets aus echten Läufen (Fixture-Capture)

Ein Fixture ist nichts anderes als eine **eingefrorene echte Modell-Ausgabe**.
Deshalb sichert jeder **echte** Lauf (`--provider anthropic` / `openai`) seine
Ausgabe **je Iteration** automatisch weg:

    runs/<zeitstempel>/fixtures/01_iteration.txt
    runs/<zeitstempel>/fixtures/02_iteration.txt
    ...

Dieses Verzeichnis ist direkt replay-fähig — einen bestimmten Lauf abspielen:

    RP_WFLOG=1 RP_REPLAY_DIR=runs/<zeitstempel>/fixtures \
      python agentic_pipeline.py --provider replay --test-mode fixed --max_retries_main 2

Oder ohne Zeitstempel-Tippen immer das **jüngste** echte Set abspielen:

    RP_WFLOG=1 RP_REPLAY_DIR="$(ls -dt runs/*/fixtures | head -1)" \
      python agentic_pipeline.py --provider replay --test-mode fixed --max_retries_main 2

Abgrenzung der Replay-Quellen:

- `RP_REPLAY_DIR=demo_fixtures` -> kuratierte Demo (skriptete 2->1->0-Story).
- `RP_REPLAY_DIR=runs/<stamp>/fixtures` -> exakte Wiedergabe eines **echten**
  Laufs (so viele Iterationen, wie er real brauchte).

Der Replay liest das Set nur, legt ein **neues** `runs/<neuer-stamp>/` an und
fasst das Quell-Set nicht an. So entsteht eine **echte** 2->1->0-Vorführung
(keine von Hand konstruierten Auslassungen), sofern das Modell im echten Lauf
tatsächlich erst unvollständig liefert und sich dann korrigiert.

Ein gutes Set lässt sich als dauerhafte Demo übernehmen:

    cp runs/<zeitstempel>/fixtures/*.txt  demo_fixtures/<sprechender-name>/
    # dann: RP_REPLAY_DIR=demo_fixtures/<sprechender-name>

Capture ist standardmäßig an und nur für echte Provider aktiv (bei `replay`
wäre die Ausgabe nur die Kopie der Eingabe). Abschalten: `RP_CAPTURE_FIXTURES=0`.

## Lauf-Artefakte: `runs/`

Damit das Repo-Root sauber bleibt, schreibt jeder Lauf alle Artefakte in ein
eigenes Verzeichnis (gitignored). **Echte Läufe** akkumulieren je Lauf unter
`runs/<zeitstempel>/`; **Demo/Replay-Läufe** landen alle im selben,
nicht akkumulierenden `runs/demo/` (wird überschrieben) — so bleiben die echten
Läufe sauber unterscheidbar und werden nicht von Vorführungen zugemüllt.

- `workflow_log.txt` — die Mitschrift des Logs (ohne erneuten Lauf ansehbar)
- `prompt_iteration_<n>.txt` — der vollständige Prompt je Iteration
- `main_prompt.txt` / `main_output.txt` — Prompt und rohe Modell-Ausgabe des
  Haupt-Schritts (zuletzt); `test_*.txt` analog für den Legacy-Test-Schritt
- `fixtures/` — das wegsicherte Replay-Set (**nur echte Läufe**)

Aufräumen jederzeit gefahrlos möglich (alles lokal, nicht im Git). Demos allein
entfernen, echte Läufe behalten:

    rm -r runs/demo            # nur die Demo-Mitschrift
    # echte Läufe behalten ihre runs/<stamp>/ mit fixtures/

## Umgebungsvariablen (Referenz)

| Variable | Wirkung |
|---|---|
| `RP_WFLOG=1` | Workflow-Log einschalten (Default: aus) |
| `RP_REPLAY_DIR=<dir>` | Quelle der Replay-Fixtures (Default: `demo_fixtures`) |
| `RP_RUN_DIR=<dir>` | Basis der Lauf-Verzeichnisse (Default: `runs`) |
| `RP_WFLOG_FILE=<datei>` | fester Pfad für die Mitschrift statt `runs/<stamp>/workflow_log.txt` |
| `RP_WFLOG_MAX_ITEMS=<n>` | Obergrenze gelisteter Namen im Log (Default: 12; Rest als `(+N)`) |
| `RP_WFLOG_TABLE_ROWS=<n>` | Zeilen im Verlaufswerte-Auszug (Default: 3; 0 = alle vorhandenen) |
| `RP_WFLOG_TABLE_COLS=<n>` | Spalten im Verlaufswerte-Auszug (Default: 3; 0 = alle vorhandenen) |
| `RP_CAPTURE_FIXTURES=0` | Fixture-Capture für echte Läufe abschalten |

## Einordnung (ehrlich, für die Präsentation)

Der **Workflow und der Vergleichsmechanismus sind echt** — gleiche Pipeline,
gleicher Golden-Master, real berechnete Prompts und Vergleichswerte. Beim
Replay ist nur die **Modell-Antwort** konserviert. Die mitgelieferten Fixtures
(`01`–`03`) sind eine *skriptete* Verbesserung (Zwischenstände wurden aus einer
echten Ausgabe abgeleitet). Für eine vollständig nicht-skriptete Selbstkorrektur
dient der Fixture-Capture aus echten Läufen.
