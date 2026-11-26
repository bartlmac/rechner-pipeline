# Einstieg für Entwickler

Dieses Dokument richtet ein, zeigt einen ersten Lauf und nennt die Regeln für
die Arbeit am Code. Was das System tut, steht im [README](README.md), die
Begriffe erklärt das [Glossar](docs/architektur/glossar.md). Wie eine
Migration fachlich abläuft, zeigt die
[Vorzeigeseite](https://bartlmac.github.io/plv-fiktion/).

## 1. Einrichten

Die Referenzumgebung ist Linux mit CPython 3.11 und genau den Versionen aus
den Pin-Dateien. Die CI und das Image der Laufzeit entstehen aus denselben
Pin-Dateien. Auf andere Betriebssysteme wird der Code nicht angepasst; dort
läuft die Suite im Entwicklungs-Container.

Das Image der Laufzeit (`ghcr.io/bartlmac/rechner-pipeline-plv`, gebaut,
wenn ein Push auf `main` den Code, `requirements.txt` oder `plv/betrieb/`
ändert) ist kein Entwicklungswerkzeug. Es enthält nur das
Paket und führt den Tageslauf einer bestehenden Ablage aus
([plv/betrieb/README.md](plv/betrieb/README.md)). Zum Entwickeln, Testen und
Nachfahren eines Falls braucht es den Klon mit einer eigenen Umgebung, wie
unten beschrieben.

**Linux:**
```
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps
```

Die Beispiele ab Abschnitt 3 schreiben `python`. Gemeint ist der Interpreter
dieser Umgebung: vorher `source .venv/bin/activate` ausführen oder
`.venv/bin/python` einsetzen.

Installiert wird nur über die Pin-Dateien. Sie enthalten die direkten
Abhängigkeiten und deren transitive Hülle, `tests/test_abhaengigkeiten.py`
hält sie geschlossen. Ein `pip install -e ".[dev]"` allein würde die
transitiven Pakete frisch auflösen. Weil die Suite Warnungen als Fehler
behandelt, könnte dann eine neue Warnung in einer fremden Bibliothek die
Suite rot färben, ohne dass sich hier etwas geändert hat.

**Windows:** Docker Desktop mit WSL 2. Welche Distribution unter WSL 2 läuft,
zeigt `wsl -l -v` in der Spalte VERSION. Gibt es keine, legt
`wsl --install -d Ubuntu` eine an. Der Klon gehört in das
Linux-Dateisystem (das WSL-Home, nicht `/mnt/c`), denn die Suite prüft
Dateirechte, die ein NTFS-Laufwerk nicht trägt.

**Windows und macOS mit Docker:** Das Entwicklungs-Image einmal bauen und die
Suite darin fahren. Der Arbeitsbaum ist eingehängt, nach einer Änderung am
Code ist kein neuer Bau nötig, nach einer Änderung der Pin-Dateien schon.
Ohne weitere Angabe fährt der Container die Suite seriell.
```
docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev .
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev            # volle Suite
docker run --rm -it -v "$PWD":/workspace rechner-pipeline-dev bash   # Shell
```
VS Code öffnet dasselbe Image über die Erweiterung Dev Containers
(`.devcontainer/`). Erprobt ist dieser Weg auf Windows 11 mit WSL 2 und auf
macOS (arm64). Beide ergaben dieselbe Prüfsumme der Paketquellen wie Linux;
die Zeilenenden sind über `.gitattributes` festgelegt.

**Eine neue Plattform melden.** Wer auf einer Plattform rechnet, die hier
noch nicht genannt ist, meldet das als Issue
([CONTRIBUTING.md](CONTRIBUTING.md)), mit dem Ergebnis der Suite und dem
Stand des Codes:
```
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev \
  python -c "import json; from pathlib import Path; from rechner_pipeline.gates._provenienz import systemstand; print(json.dumps(systemstand(Path('/workspace')), indent=2))"
```
`quellcode_sha256` ist die Prüfsumme der Paketquellen unter
`src/rechner_pipeline/`. `dirty` muss `nein` lauten, sonst trägt der
Arbeitsbaum nicht committete Änderungen, und der Wert ist nicht
vergleichbar.

## 2. Die Suite

```
.venv/bin/python -m pytest -n auto --dist loadfile
```

Die Suite läuft parallel; jede Testdatei läuft ganz in einem Prozess
([ADR-019](docs/architektur/adr-019-parallele-testsuite.md)). Mit zwölf
Prozessen dauert sie etwa sieben Minuten, seriell ein Vielfaches davon. Bei
knappem Arbeitsspeicher weniger Prozesse wählen, etwa `-n 4`. Die CI fährt
sie bei jedem Push auf `main` und bei jedem Pull Request
(`.github/workflows/tests.yml`).

Zu einem Ergebnis gehören drei Angaben: die Zeile mit `passed` und `failed`,
die Zeile des Baumwächters und der Exit-Code. Der Baumwächter
(`tests/baumwaechter.py`) liest während des Laufs den Zustand des
Arbeitsbaums. Schreibt ein Test in den Baum, endet die Suite mit Exit 1,
auch wenn alle Tests bestanden haben.

In einem frischen Klon werden drei Tests übersprungen: zwei, weil die
Regie-Dateien unter `simulation/` nicht im Repository liegen, und einer,
weil das Paket `markdown` nicht zu den gepinnten Abhängigkeiten gehört.
Ohne Docker kommt ein vierter hinzu (die Doku-Engine). Das ist erwartet.

## 3. Ein erster Lauf

**Einen abgeschlossenen Fall nachfahren.** Ohne Agenten und in etwa 45
Minuten entsteht aus dem Stand des Repositorys eine Laufzeit der PLV mit
dem übernommenen Bestand:
```
werkzeuge/welt/laufzeit_aufstellen.sh ~/plv-welt pakete/baldrian-klv-tg2015-fall3
```
Mit `--bis <haltepunkt>` hält der Lauf an einer Stelle, an der man selbst
liest und zeichnet; derselbe Aufruf ohne `--bis` (oder mit einem späteren
Haltepunkt) fährt danach weiter. Die Haltepunkte nennt
[pakete/README.md](pakete/README.md). Der Fall liegt danach im Klon unter
`faelle/`; ein zweites Nachfahren braucht einen frischen Klon, oder der
Fall wird vorher nach `faelle/archiv/` verschoben (README, Schnellstart). Erprobt ist das
Nachfahren unter Linux, aus einem Klon mit `.venv`, im Entwicklungs-Container
bisher nicht. Einzelheiten stehen in
[werkzeuge/welt/README.md](werkzeuge/welt/README.md).

`main` trägt den Stand nach Fall 3, der Rechenkern kennt den übernommenen
Tarif also bereits. Den Stand vor dem Fall trägt der Tag `fall3-vor-ebenen`:
der Stand vor Fall 3 in der Ordnung nach ADR-028 (der Originalstand trägt den
Tag `fall3-vor`). Die Skripte unter `werkzeuge/welt/` gibt es dort noch
nicht, sie nehmen den Codebaum aber über die Variable `BAUM` entgegen. Wer
den Fall live mit Agenten auf dem alten Stand führen will, legt einen
zweiten Klon auf `fall3-vor-ebenen` an und ruft die Skripte aus `main` mit
`BAUM=<zweiter Klon>` auf (mit `PYTHON=<Interpreter>`, wenn der zweite Klon
keine eigene `.venv` hat). Eine eigene Anleitung dafür gibt es noch nicht.

**Einen Fall anlegen.** Eine Datei kommt nur durch Registrieren in einen
Fall:
```
python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 --scope tarif
python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
    --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm
python -m rechner_pipeline.fall status --fall faelle/klv-tg2012
```
`status` vergleicht das Register mit den Dateien. Fehlt eine registrierte
Datei, weicht ihr Inhalt von der Prüfsumme ab oder liegt eine Datei ohne
Eintrag in `eingang/`, meldet es einen Fehler.

Auch die Vorverdichtung einer Quelle (Gate `P-Q1`) läuft ohne Agenten:
```
python -m rechner_pipeline.gates.extract --repo-root . \
    --input faelle/klv-tg2012/eingang/Tarifrechner_KLV_TG2012.xlsm \
    --out-dir faelle/klv-tg2012/abgeleitet/vorverdichtung/xlsm-TG2012 --adapter excel
```
Danach beginnen die Schritte der Agenten: Sie lesen die vorverdichteten
Quellen und schlagen Aussagen vor. Ohne Agenten-Werkzeug (Claude Code oder
Codex im Wurzelverzeichnis) geht es hier nicht weiter: Der nächste Schritt,
`gates.abox_merge`, findet keine Fragmente und endet mit Exit 20. Mit einem
Agenten-Werkzeug führt der Skill `migrationsfall-durchfuehren` durch den
Fall. Wie ein Fall vollständig geführt wird,
mit Welt, Fallauftrag und allen Gates, beschreibt
[docs/architektur/ablauf-eines-falls.md](docs/architektur/ablauf-eines-falls.md).
Die Kommandos dazu stehen in [werkzeuge/welt/README.md](werkzeuge/welt/README.md)
und in den Bedienfolgen von
[ADR-025](docs/architektur/adr-025-erstabnahme-des-zielsystems.md) und
[ADR-026](docs/architektur/adr-026-lebenslauf-eines-falls.md).

### Offenes Modell mit einem Harness

Ein Harness ist das Werkzeug, das ein Sprachmodell aufruft und ihm je nach
Einstellung Dateien und Werkzeuge bereitstellt. Herdr kann mehrere
Agentensitzungen koordinieren; für den hier beschriebenen Verbindungstest ist
es nicht erforderlich. Der konkrete Einsatz in einem Migrationslauf wird noch in
[Issue #71](https://github.com/bartlmac/rechner-pipeline/issues/71)
ausgearbeitet. Ein offenes Modell kann auf
einem eigenen Inferenzserver laufen; der Modellname allein sagt weder, wo die
Daten verarbeitet werden, noch ob das Modell für eine Aufgabe geeignet ist.
Die Agenten schlagen vor; fachliche Widersprüche und Abnahmen entscheiden
Menschen. Die deterministischen Gates rufen kein Modell auf.

**Lokaler Modellserver.** Das Beispiel verwendet Qwen3.8-27B als
GGUF-Datei in der Quantisierung Q4_K_M. llama.cpp und das Modell benötigen
ausreichend Arbeitsspeicher beziehungsweise GPU-Speicher; der Bedarf hängt
auch von Kontextgröße und GPU-Auslagerung ab. Nach der
[llama.cpp-Installation](https://github.com/ggml-org/llama.cpp#install)
startet ein Terminal den Server so:

```bash
llama serve -hf ggml-org/Qwen3.8-27B-GGUF:Q4_K_M \
  --alias qwen3.8-27b --host 127.0.0.1 --port 8080 \
  --ctx-size 32768 --jinja
```

Beim ersten Start lädt llama.cpp das Modell herunter; danach rechnet der
Server lokal. Das Terminal bleibt geöffnet. Der Alias ist die Modell-ID für
die folgenden Harness-Konfigurationen. Der Aufruf bindet nur an den lokalen
Rechner und aktiviert keine Authentifizierung. Hat der bereits laufende
Server einen Schlüssel, wird dieser stattdessen wie unten beschrieben über
`LOKAL_MODELL_KEY` bereitgestellt. Port und Kontextgröße müssen bei Server
und Harness zusammenpassen. GPU-Auslagerung und größere Kontexte hängen von
der Hardware ab; ein laufender Server belegt den Port bereits.

**Geprüfter Verbindungstest:** Pi 0.80.6 mit einem lokalen,
OpenAI-kompatiblen llama.cpp-Server und dem dort als `qwen3.8-27b`
angebotenen Modell. Voraussetzung sind ein installiertes `pi` und ein bereits
gestarteter Server mit geladenem Modell. Falls der Server Authentifizierung
verlangt, wird auch dessen Zugangsschlüssel benötigt; andernfalls genügt für
die Pi-Konfiguration ein beliebiger Platzhalter. Der Server muss auf
`127.0.0.1:8080` erreichbar sein; Modell-ID und Adresse sind gegebenenfalls an
die eigene Installation anzupassen. Pi und der Modellserver werden getrennt
vom Python-Paket installiert und betrieben.

Für den Test ein eigenes Pi-Konfigurationsverzeichnis wählen. Die Datei
`models.json` darin enthält beispielsweise (die Modell-ID muss der vom
Server angebotenen ID entsprechen):

```json
{
  "providers": {
    "lokal": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "$LOKAL_MODELL_KEY",
      "authHeader": true,
      "models": [{
        "id": "qwen3.8-27b",
        "name": "Lokales Modell",
        "reasoning": false,
        "input": ["text"],
        "contextWindow": 32768,
        "maxTokens": 1024,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
      }]
    }
  }
}
```

`contextWindow` und `maxTokens` müssen zum Server und Modell passen. Den
Schlüssel außerhalb des Repositorys als Umgebungsvariable `LOKAL_MODELL_KEY`
bereitstellen; er gehört nicht in die Datei oder in einen Fall. Anschließend
aus dem Repository-Wurzelverzeichnis, mit dem Pfad zum eigenen
Konfigurationsverzeichnis:

```bash
PI_CODING_AGENT_DIR=/pfad/zur/pi-konfiguration pi --offline --no-session \
  --no-extensions --no-skills --no-context-files --no-tools \
  --provider lokal --model qwen3.8-27b --thinking off \
  -p 'Antworte ausschließlich mit OK.'
```

Bei erfolgreicher Verbindung antwortete der geprüfte Server mit `OK`.
Der Test schaltet Werkzeuge, Skills, Kontextdateien und Sitzungsablage ab;
er prüft nur die Modellverbindung. Für den oben ohne Schlüssel gestarteten
Server kann `LOKAL_MODELL_KEY` ein beliebiger Platzhalter sein.

**OpenCode:** Der folgende Weg wurde mit OpenCode 2.2.7 und dem lokalen
llama.cpp-Server mit `qwen3.8-27b` geprüft. OpenCode wird separat
[installiert](https://opencode.ai/docs/). In der persönlichen Konfiguration
`~/.config/opencode/opencode.json` den Provider ergänzen; eine bestehende
Datei dabei zusammenführen, nicht überschreiben:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "llamacpp/qwen3.8-27b",
  "providers": {
    "llamacpp": {
      "name": "Lokales llama.cpp",
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "http://127.0.0.1:8080/v1",
        "apiKey": "{env:LOKAL_MODELL_KEY}"
      },
      "models": {
        "qwen3.8-27b": {
          "modelID": "qwen3.8-27b",
          "capabilities": {"tools": true, "input": ["text"], "output": ["text"]},
          "limit": {"context": 32768, "output": 1024}
        }
      }
    }
  }
}
```

Der Schlüsselwert wird beim Start aus der Umgebung gelesen; er gehört nicht
in die Konfigurationsdatei. Bei dem oben ohne Authentifizierung gestarteten
Server kann die Zeile `apiKey` entfallen. Bei einem geschützten Server muss
`LOKAL_MODELL_KEY` dessen Schlüssel enthalten. Bei anderer Modell-ID oder
anderen Servergrenzen die Konfiguration anpassen. Dann im
Repository-Wurzelverzeichnis OpenCode starten und das Modell testen:

```bash
opencode run -m llamacpp/qwen3.8-27b 'Antworte ausschließlich mit OK.'
```

Der Probelauf lieferte `OK`; ein weiterer las über das Lesewerkzeug eine
Testdatei und gab ihren Inhalt aus. OpenCode kann je nach Konfiguration
Werkzeuge nutzen und Sitzungen speichern. Interaktiv startet `opencode` im
Repository; das Modell kann dort ebenfalls ausgewählt werden. Der Test belegt
noch keine Extraktion und keinen Migrationsfall.

Für einen Fall müssen Harness, Modell und deren Berechtigungen gesondert
erprobt werden. Insbesondere ist zu prüfen, ob die Repository-Skills und
Rollen tatsächlich geladen werden. Ein lokaler Server macht ein Harness
nicht automatisch sicher: Dateizugriff, Werkzeugfreigaben und der Umgang mit
Fall- und Schlüsseldaten hängen von seiner Konfiguration ab. Schlüssel bleiben
außerhalb des Falls und stehen Agenten für menschliche Zeichnungen nicht zur
Verfügung ([ADR-018](docs/architektur/adr-018-rollenmodell-und-schluesselklassen.md)).

## 4. Am Code arbeiten

**Wo Code hingehört.** Welches Paket welches importieren darf, legt die
Schichtenkarte fest
([ADR-001](docs/architektur/adr-001-repo-zielstruktur.md),
[ADR-017](docs/architektur/adr-017-vier-ebenen.md)). Jedes Modul und jeder
Test nennt im Docstring seinen [Knoten](docs/architektur/glossar.md#knoten),
zum Beispiel `Knoten: klv/tg2015`. Vier Werkzeuge prüfen und zeigen das:
```
python -m rechner_pipeline.ontologie.code_index --tests tests   # Knoten, Module, Tests
python -m rechner_pipeline.ontologie.code_karte                 # Schichtregeln
git diff --name-only | python -m rechner_pipeline.ontologie.impact
python -m rechner_pipeline.ontologie.landkarte --out runs/landkarte.html
```
`impact` nennt die Tests, die eine Änderung betrifft. Das hilft beim Bauen,
ersetzt aber nicht die volle Suite. Die Diagramme in
`docs/architektur/landkarte.md` sind aus dem Code erzeugt, und ein Test hält
sie gegen ihn.

**Kern und Tarifwerk.** Fall 3 hat den Stand des Rechenkerns (Code,
Referenzwerte, Grundsatzdokumentation) und des Tarifwerks (die Dateien unter
`plv/tarifplaene/` und die eigenen Generationen der Bestands-Configs)
abgenommen und über Prüfsummen gebunden. `tests/test_pakete.py` hält fest,
dass der Baum diesen Stand trägt, sonst ließe sich Fall 3 aus `main` nicht
mehr nachfahren. Eine Änderung daran ist eine Änderung des Zielsystems. Sie
braucht eine Abnahme (`A-K2` für den Kern, `A-T1` für das Tarifwerk) und ein
neues Paket.

**Regeln.**

- **Deterministisch:** In `src/` läuft kein Subprozess (bis auf die eine
  Ausnahme im nächsten Punkt), es gibt kein Netz und keine dynamische
  Ausführung. Gleiche Eingaben ergeben gleiche
  Ausgaben, serialisiert wird sortiert.
- **Die eine Ausnahme:** Es gibt genau eine Subprozess-Ausnahme.
  `gates/_provenienz._git_lesen` führt lesende Git-Kommandos aus einer
  festen Liste aus, um festzuhalten, auf welchem Stand ein Beleg oder ein
  Entscheid entsteht. Jeder weitere Subprozess färbt
  `tests/test_fachspez_und_p9.py::test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt`
  rot.
- **Kein Sprachmodell im Code:** Agenten arbeiten über ihre Werkzeuge, nie
  über einen Aufruf aus `src/`.
- **Fehler halten an:** Unklarheit ist ein benannter Zustand
  (`nicht_belegt`, `mehrdeutig`, `widerspruechlich`) oder ein Fehler, dessen
  Meldung den Ausweg nennt. Nichts wird still überschrieben oder durch einen
  Ersatzwert gefüllt.
- **Agenten entscheiden keine Widersprüche:** Eine vorläufige Auflösung trägt
  `vorlaeufig=true` und blockiert jede menschliche Abnahme.
- **Volle Suite vor jedem Commit.** Neue Abhängigkeiten kommen nur über ein
  ADR und exakt gepinnt. Beiträge kommen als Pull Request, vor größeren
  Änderungen bitte ein Issue ([CONTRIBUTING.md](CONTRIBUTING.md)).

**Laufdaten.** `runs/` ist zum Wegwerfen da, dort darf jeder löschen. Was
erhalten bleiben soll, gehört in einen Fall (`faelle/<fall>/`, wo `eingang/`
und `entscheide/` unantastbar sind) oder in einen festgeschriebenen
Abschluss, der sich selbst schreibgeschützt ablegt. Vor dem Aufräumen unter
`runs/` prüfen, ob dort echte Laufdaten liegen.

## 5. Weiterlesen

| Thema | Dokument |
|---|---|
| Was die Gates prüfen und warum sie Versionen tragen | [docs/architektur/gate-vertrag-und-versionen.md](docs/architektur/gate-vertrag-und-versionen.md) |
| Wer welches Gate zeichnet | [ADR-012](docs/architektur/adr-012-gate-namensordnung.md), [ADR-018](docs/architektur/adr-018-rollenmodell-und-schluesselklassen.md) |
| Schlüsseldateien, Rotation, Signatur | [ADR-008](docs/architektur/adr-008-signierte-p9-freigaben.md), [ADR-021](docs/architektur/adr-021-belegrollen-und-freigabe-in-models.md) |
| Fall-Scope und die Pflichtbelege der Migrationsabnahme | [ADR-009](docs/architektur/adr-009-fall-scope-und-gate-dag.md) |
| Tarifregeln eines übernommenen Tarifs, Herabsetzungsanteile | [ADR-024](docs/architektur/adr-024-tbox-020-tarifwerk-gevo-zustandsextrakt.md), [ADR-023](docs/architektur/adr-023-herabsetzung-und-teilkuendigung.md) |
| Einen Bestand erzeugen und berichten | [docs/simulation/bestandserzeugung.md](docs/simulation/bestandserzeugung.md) |
| Die Laufzeit im Tagesbetrieb | [plv/betrieb/README.md](plv/betrieb/README.md), [docs/simulation/tagesbetrieb.md](docs/simulation/tagesbetrieb.md) |
| Agenten im Repository | [AGENTS.md](AGENTS.md), [docs/architektur/skill-architektur.md](docs/architektur/skill-architektur.md) |
