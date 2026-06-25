# CR-004 — Containerisierter Run (kanonische Linux-Laufzeit)

- **Status:** Vorschlag (Entscheidung offen)
- **Datum:** 2026-05-29
- **Branch-Kontext:** `feat/anthropic-provider`
- **Betroffen:** neues `Dockerfile` (+ optional `compose`/Run-Wrapper); berührt
  keine Pipeline-Logik
- **Abstimmung:** mit Bartek/Alexander (Infra)

## 1. Kontext / Motivation

Das Team arbeitet auf Win/macOS/Linux; durch das Excel-freie Default-Backend
(openpyxl + oletools, pure-Python) ist der **Run** jetzt plattformneutral. Ein
**Container für den Run** (nicht zwingend für die Entwicklung) macht daraus eine
**eine** kanonische Linux-Laufzeit: identische Python-Version, gepinnte Deps,
reproduzierbar — egal auf welchem Host. Das war **vorher unmöglich** (Excel/COM
liefen nicht im Linux-Container).

## 2. Vorschlag

Ein schlankes Linux-Image, das die Pipeline (Excel-freier Pfad) ausführt; der
Host bleibt unberührt. Entwicklung weiterhin nativ (venv) erlaubt.

**`Dockerfile` (Skizze):**

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY pipeline.py agentic_pipeline.py ./
# Kein COM/pywin32 (Marker greift auf Linux nicht); openpyxl+oletools reichen.
RUN pip install --no-cache-dir -e ".[export,llm,anthropic]"
ENTRYPOINT ["python", "pipeline.py"]
```

**Run (Excel-frei, Secret als read-only-Mount, kein Key im Image):**

```bash
docker run --rm \
  -v "$PWD/examples:/app/examples:ro" \
  -v "$PWD/out:/app/info_from_excel" \
  -v "$PWD/out_generated:/app/generated" \
  -v "$HOME/.secrets/anthropic-api-key:/run/secrets/anthropic:ro" \
  -e ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic \
  rechner-pipeline --provider anthropic
```

- **Workbook** read-only gemountet, **Outputs** (`info_from_excel/`,
  `generated/`) als Volumes → Ergebnisse landen auf dem Host.
- **Secret** read-only gemountet, über die bestehende `*_FILE`-Konvention
  (vgl. [[feedback-secrets-file-pointer]]) — **niemals** ins Image gebacken.

## 3. Sicherheits-Synergie (relevant)

Der Container ist ein **OS-Sandbox** und ergänzt das bisherige Modell:

- Die **Compare-Stufe** (führt generierten Code aus) kann im Container mit
  **`--network none`** und read-only-Mounts laufen → echter OS-seitiger Schutz
  gegen Netz/Schreiben, **idiom-agnostisch** (anders als statisches Gate +
  `fs_confine`-Monkeypatch, die je Lese-Idiom nachziehen müssen).
- Denkbar: **zweistufig** — Orchestrator-Schritt mit Netz (nur für den
  Anthropic-Call), Ausführung des generierten Codes in einem separaten
  `--network none`-Schritt. `fs_confine` + statisches Gate bleiben als
  Defense-in-depth.

## 4. Bewusste Grenzen

- **COM-Backend (`--export-backend com`) läuft NICHT im Container** (kein
  Excel). Bleibt nativer Windows-Pfad (z. B. Golden-Master-Erzeugung) — der
  Container deckt den Excel-freien Default ab.
- Container ersetzt **nicht** die Entwicklung (dort weiter venv); Ziel ist der
  reproduzierbare **Run** (und ggf. die CI-Basis, vgl. CR-003).

## 5. Offene Fragen

1. **Deps pinnen:** zusätzlich zur `pyproject`-Range ein `requirements.lock`
   (Hashes) für volle Reproduzierbarkeit im Image?
2. **Netz-Policy:** Orchestrator braucht Egress zu Anthropic; generierter Code
   nicht → ein Image mit zwei Run-Modi oder zwei Images?
3. **Distribution:** Image nur lokal bauen oder in eine Registry/GHCR pushen
   (dann Build-Job in CR-003-CI)?
4. **Agentic-Variante** (`langgraph`) mit ins Image (`[agentic]`) oder schlank
   halten?
5. **Synergie mit CR-003:** dasselbe Image als CI-Runner-Basis nutzen?

## 6. Empfehlung

Annehmen, schlank starten: ein `Dockerfile` für den Excel-freien Run + ein
dokumentierter `docker run` (Mounts wie oben). Mittelfristig die
Sicherheits-Synergie nutzen (Compare-Stufe `--network none`) und das Image als
CI-Basis (CR-003) wiederverwenden. COM bleibt nativer Windows-Escape-Hatch.
