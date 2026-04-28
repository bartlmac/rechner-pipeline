# KI-Lab JTG26 — Setup-Anleitung (Windows)

Stand: 2026-04-28

## Onepager — was die Helfer am Stand sehen müssen

Die drei Demo-Laptops sind **vorab eingerichtet**. Vor Ort nur:

1. Anmelden am Windows-Benutzer (Zugangsdaten am Laptop).
2. ChatGPT-Business im Browser einloggen (Zugangsdaten von Christopher Kling).
3. VS Code starten, Repo-Verzeichnis öffnen.
4. Bei Problemen: **Bartek oder Arno ansprechen** — wir sind ganztägig am Stand.

> Setup nicht selbst neu durchspielen. Das macht Bartek/Arno, falls nötig.

---

## Setup von Null (nur für Bartek/Arno)

### Standardweg — `setup.bat` doppelklicken

Voraussetzungen am Windows-11-Laptop:

- Microsoft Store „App Installer" installiert (für `winget`)
- Internet-Verbindung
- Aktueller Benutzer

Ablauf:

1. `setup.bat` und `setupdav.ps1` ins selbe Verzeichnis legen.
2. **Doppelklick auf `setup.bat`**.
3. Wenn UAC-Prompt für `winget`-Pakete kommt → bestätigen.
4. Am Ende erscheint „Setup erfolgreich abgeschlossen" — Fenster mit Enter schließen.
5. Excel **einmal öffnen** und schließen, damit die Trust-Center-Einstellungen wirksam werden.

### Fallback ohne `setup.bat`

Wenn nur `setupdav.ps1` zur Verfügung steht (z. B. weil das Repo nur `.ps1` hat):

```powershell
# Einmalig pro Benutzer:
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# Dann das Skript starten:
.\setupdav.ps1
```

Alternativ einmalig per Bypass (ohne ExecutionPolicy persistent zu ändern):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setupdav.ps1
```

---

## Was das Skript macht (Kurzübersicht)

| Schritt | Inhalt |
|---|---|
| 1 | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` (persistiert) |
| 2 | Python-App-Aliase entfernen (`python.exe` / `python3.exe` Reparse-Points unter `WindowsApps`) |
| 3 | `winget` prüfen |
| 4 | Python 3.13 (winget, `PrependPath=1`) |
| 5 | VS Code (winget) |
| 6 | `git` + `gh` (winget) |
| 7 | `pip`, `setuptools`, `wheel` aktualisieren |
| 8 | Python-Pakete: `xlwings`, `openpyxl`, `pandas`, `pytest`, `oletools`, `openai`, `pywin32`, `langgraph` |
| 9 | VS Code Python Extension (`ms-python.python`) |
| 10 | Excel Trust-Center: `AccessVBOM=1`, `VBAWarnings=1` (HKCU 16.0) |
| 11 | Repos clonen nach `%USERPROFILE%\ki-lab\repos\` (+ `pip install -r requirements.txt` nur für `rechner-pipeline`) |
| 12 | `.env` aus `.env.example` für `rechner-pipeline` (OPENAI-Key wird **nicht** automatisch gesetzt) |

Keine Admin-Rechte nötig — alles läuft im User-Scope.

---

## Repos und Use-Case-Mapping

Alle Repos sind public und werden vom Skript nach `%USERPROFILE%\ki-lab\repos\` geklont.

| Repo | Use Case | Rolle im KI-Lab |
|---|---|---|
| `portxlpy-seminar-2026-02-eaa` | (1) handwerklich, (2) industriell | **Vorzeige** — gelöste Use Cases als Demo, funktionierende Skripts und Tests |
| `portxlpy-seminar-2026-02-eaa-ex-cr` | (1) handwerklich | **Übung** Arno (Crafted) — leerer Platz für echte Aufgaben mit Besuchern |
| `portxlpy-seminar-2026-02-eaa-ex-is` | (2) industriell | **Übung** Bartek (Industrial) — leerer Platz für echte Aufgaben |
| `rechner-pipeline` | (3) agentisch | **Showcase** — `langgraph`-Pipeline, niemand außer Bartek ändert hier etwas |

Use Case (4) „funny case" — Excel direkt ins ChatGPT-Web hochladen — braucht **kein** Repo, nur den Browser mit ChatGPT-Business-Login.

### OPENAI_API_KEY für `rechner-pipeline`

Use Case (3) läuft am Stand **nur** auf den Laptops von Bartek und Arno. Helfer-Laptops bekommen keinen Key — die leere `.env` lässt Pipeline-Aufrufe dort sauber mit „OPENAI_API_KEY is not set" abbrechen.

Auf **Bartek- und Arno-Laptop** einmalig nach Setup:

```powershell
cd "$env:USERPROFILE\ki-lab\repos\rechner-pipeline"

# 1. Key eintragen
notepad .env
#   -> OPENAI_API_KEY=sk-... speichern

# 2. ACL setzen — nur der aktuelle User darf lesen
.\setup\set-env-acl.ps1
```

Hintergrund / Schutzmodell: `api-key-konzept.md`. **Plus**: OpenAI-Dashboard Hard Limit auf 50 EUR setzen (zweite Schutzebene).

`.env` ist in `.gitignore` — landet nie im Repo.

### Smoke-Test nach Setup

```powershell
cd "$env:USERPROFILE\ki-lab\repos\portxlpy-seminar-2026-02-eaa"
pytest
```

---

## Manuelle Befehlsreferenz (Cheat-Sheet)

Falls etwas händisch nachgezogen werden muss.

### ExecutionPolicy

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
# Kontrolle:
Get-ExecutionPolicy -List
```

### App-Aliase deaktivieren

GUI-Weg: **Einstellungen → Apps → Erweiterte App-Einstellungen → App-Ausführungsaliase** → `App-Installer python.exe` und `python3.exe` deaktivieren.

Per Skript:

```powershell
Remove-Item "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"  -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe" -Force -ErrorAction SilentlyContinue
```

### Python-Installation prüfen

```powershell
python --version
where.exe python
```

### Python-Pakete

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install xlwings openpyxl pandas pytest oletools openai pywin32 langgraph
```

Für `rechner-pipeline` zusätzlich:

```powershell
python -m pip install -r "$env:USERPROFILE\ki-lab\repos\rechner-pipeline\requirements.txt"
```

### Repos manuell clonen

```powershell
$base = "$env:USERPROFILE\ki-lab\repos"
New-Item -ItemType Directory -Path $base -Force | Out-Null
cd $base
git clone https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa.git
git clone https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa-ex-cr.git
git clone https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa-ex-is.git
git clone https://github.com/bartlmac/rechner-pipeline.git
```

### git / gh

```powershell
winget install -e --id Git.Git
winget install -e --id GitHub.cli
gh auth login   # nur wenn nötig — Strategie steht noch nicht
```

### VS Code Python Extension

```powershell
code --install-extension ms-python.python --force
```

### Excel Trust-Center

```powershell
$sec = "HKCU:\Software\Microsoft\Office\16.0\Excel\Security"
New-Item -Path $sec -Force | Out-Null
Set-ItemProperty -Path $sec -Name "AccessVBOM"  -Value 1 -Type DWord   # xlwings: VBA-Zugriff
Set-ItemProperty -Path $sec -Name "VBAWarnings" -Value 1 -Type DWord   # Makros aktivieren
```

GUI-Kontrolle: Excel → Datei → Optionen → Trust Center → Trust-Center-Einstellungen → **Makroeinstellungen** und **Externe Inhalte**.

---

## Offen

- **Spielregie 15-Min-Slot** — Helfer-Onepager je Use Case (1)–(4) (morgen 29.04.)
- **GitHub-Auth-Strategie** ist mit den vier öffentlichen Repos hinfällig (Clone ohne Login). Falls Helfer doch `gh` brauchen: `gh auth login` mit Bartek-Account — oder auf Helfer-Maschinen nicht einloggen.
