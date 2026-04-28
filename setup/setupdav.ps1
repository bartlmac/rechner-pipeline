# ================================
# KI-Lab Setup-Skript (Windows)
# JTG26 Berlin, 29.-30.04.2026
# ================================
#
# Aufruf:
#   - per Doppelklick auf setup.bat (empfohlen)
#   - oder manuell:
#       powershell -NoProfile -ExecutionPolicy Bypass -File setupdav.ps1
#
# Wenn weder .bat noch -ExecutionPolicy Bypass verwendet werden,
# vorher in einer PowerShell als aktueller Benutzer einmalig:
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
#
# Was das Skript tut:
#   1. ExecutionPolicy persistieren (CurrentUser = RemoteSigned)
#   2. Python-App-Aliase deaktivieren (python.exe / python3.exe Reparse-Points entfernen)
#   3. Python 3.13 + VS Code per winget installieren (falls fehlt)
#   4. git und gh per winget installieren
#   5. Python-Pakete: xlwings, openpyxl, pandas, pytest, oletools,
#      openai, pywin32, langgraph
#   6. VS Code Python Extension
#   7. Excel Trust-Center: Makros aktivieren (VBAWarnings=1) + VBA-Zugriff (AccessVBOM=1)
#   8. KI-Lab-Repos clonen nach %USERPROFILE%\ki-lab\repos\
#         - portxlpy-seminar-2026-02-eaa
#         - portxlpy-seminar-2026-02-eaa-ex-cr
#         - portxlpy-seminar-2026-02-eaa-ex-is
#         - rechner-pipeline
#      und je requirements.txt nachinstallieren (gepinnte Versionen).
#   9. .env aus .env.example fuer rechner-pipeline anlegen (Schluessel manuell eintragen)
#
# Keine Admin-Rechte noetig - alles laeuft unter dem aktuellen Benutzer.

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
}

Write-Host "=== KI-Lab Setup startet ===" -ForegroundColor Cyan

# --------------------------------
# 1. ExecutionPolicy persistieren
# --------------------------------
Write-Step "ExecutionPolicy auf RemoteSigned setzen (CurrentUser)"
try {
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    Write-Host "ExecutionPolicy gesetzt." -ForegroundColor Green
} catch {
    Write-Host "Hinweis: ExecutionPolicy konnte nicht persistiert werden ($_). Skript laeuft trotzdem weiter." -ForegroundColor Yellow
}

# --------------------------------
# 2. Python-App-Aliase deaktivieren
# --------------------------------
# Windows legt 0-Byte-Reparse-Points unter %LOCALAPPDATA%\Microsoft\WindowsApps an,
# die statt der echten python.exe den Microsoft Store oeffnen. Wir entfernen sie,
# damit das winget-installierte Python eindeutig in der Befehlszeile gewinnt.
Write-Step "Python-App-Ausfuehrungsaliase deaktivieren"
$winApps = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
foreach ($alias in @("python.exe","python3.exe")) {
    $aliasPath = Join-Path $winApps $alias
    if (Test-Path $aliasPath) {
        try {
            Remove-Item $aliasPath -Force -ErrorAction Stop
            Write-Host "  Entfernt: $aliasPath" -ForegroundColor Green
        } catch {
            Write-Host "  Konnte $aliasPath nicht entfernen ($_) - bitte manuell in 'Einstellungen -> Apps -> Erweiterte App-Ausfuehrungsaliase' deaktivieren." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Kein Alias unter $aliasPath - ok." -ForegroundColor Green
    }
}

# --------------------------------
# 3. winget vorhanden?
# --------------------------------
Write-Step "winget pruefen"
if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "FEHLER: winget ist nicht installiert!" -ForegroundColor Red
    Write-Host "Bitte 'App Installer' aus dem Microsoft Store installieren und erneut starten."
    exit 1
}
Write-Host "winget ok." -ForegroundColor Green

# --------------------------------
# 4. Python 3.13 installieren
# --------------------------------
Write-Step "Python 3 installieren"
$pythonOk = $false
try {
    $version = python --version 2>$null
    if ($version -match "Python 3") { $pythonOk = $true }
} catch {}

if (-not $pythonOk) {
    Write-Host "Installiere Python 3.13..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.13 --source winget --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --override "InstallAllUsers=0 PrependPath=1 Include_test=0"
} else {
    Write-Host "Python bereits installiert: $version" -ForegroundColor Green
}
Refresh-Path

# --------------------------------
# 5. VS Code installieren
# --------------------------------
Write-Step "VS Code installieren"
winget install -e --id Microsoft.VisualStudioCode --silent `
    --accept-package-agreements `
    --accept-source-agreements
Refresh-Path

# --------------------------------
# 6. git + gh installieren
# --------------------------------
Write-Step "git und gh installieren"
winget install -e --id Git.Git --silent `
    --accept-package-agreements `
    --accept-source-agreements
winget install -e --id GitHub.cli --silent `
    --accept-package-agreements `
    --accept-source-agreements
Refresh-Path

# --------------------------------
# 7. Pause, damit alle PATH-Aenderungen wirken
# --------------------------------
Start-Sleep -Seconds 5
Refresh-Path

if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "FEHLER: Python wurde nicht korrekt installiert oder ist nicht im PATH." -ForegroundColor Red
    exit 1
}

# --------------------------------
# 8. Pip aktualisieren + Build-Tools
# --------------------------------
Write-Step "pip aktualisieren"
python -m pip install --upgrade pip setuptools wheel

# --------------------------------
# 9. Python-Pakete installieren
# --------------------------------
Write-Step "Python-Pakete installieren"
# Bewusst ungepinnte Liste, nur was die Demos tatsaechlich brauchen:
#   - Seminar-Repos (handwerklich + industriell, Use Cases 1+2):
#       xlwings, openpyxl, pandas, pytest
#       oletools (importiert in vba_to_text.py - VBA-Extraktion Bartek-Industrial)
#   - rechner-pipeline (agentisch, Use Case 3):
#       openai, pywin32, langgraph
# junit2html / pytest-html aus den Seminar-requirements.txt sind nicht importiert
# und werden hier weggelassen (HTML-Report-Komfort, fuer KI-Lab nicht noetig).
python -m pip install `
    xlwings openpyxl pandas pytest oletools `
    openai pywin32 langgraph

# --------------------------------
# 10. VS Code Python Extension
# --------------------------------
Write-Step "VS Code Python Extension"
try {
    code --install-extension ms-python.python --force
} catch {
    Write-Host "Hinweis: VS Code Extension konnte nicht automatisch installiert werden ($_)." -ForegroundColor Yellow
    Write-Host "Manuell in VS Code: Strg+Shift+X -> 'Python' (Microsoft) installieren." -ForegroundColor Yellow
}

# --------------------------------
# 11. Excel Trust-Center
# --------------------------------
# Office-Version 16.0 deckt Office 2016, 2019, 2021, 365 ab.
# AccessVBOM=1 : "Zugriff auf das VBA-Projektobjektmodell vertrauen" (xlwings)
# VBAWarnings=1: alle Makros aktivieren ohne Nachfrage
#
# Hinweis: nur fuer die KI-Lab-Demo-Maschinen vertretbar - VBAWarnings=1
# senkt den Excel-Schutz fuer Makros aus beliebigen Quellen!
Write-Step "Excel Trust-Center setzen (Makros aktivieren + VBA-Zugriff)"
$excelSec = "HKCU:\Software\Microsoft\Office\16.0\Excel\Security"
try {
    if (-not (Test-Path $excelSec)) {
        New-Item -Path $excelSec -Force | Out-Null
    }
    Set-ItemProperty -Path $excelSec -Name "AccessVBOM"   -Value 1 -Type DWord
    Set-ItemProperty -Path $excelSec -Name "VBAWarnings"  -Value 1 -Type DWord
    Write-Host "Excel Trust-Center gesetzt: AccessVBOM=1, VBAWarnings=1" -ForegroundColor Green
} catch {
    Write-Host "Hinweis: Excel Trust-Center konnte nicht gesetzt werden ($_)." -ForegroundColor Yellow
    Write-Host "Manuell: Excel -> Datei -> Optionen -> Trust Center -> Trust Center-Einstellungen -> Makroeinstellungen:" -ForegroundColor Yellow
    Write-Host "  - 'Alle Makros aktivieren'" -ForegroundColor Yellow
    Write-Host "  - 'Zugriff auf das VBA-Projektobjektmodell vertrauen'" -ForegroundColor Yellow
}

# --------------------------------
# 12. KI-Lab-Repos clonen
# --------------------------------
Write-Step "KI-Lab-Repos clonen"

$repoBase = Join-Path $env:USERPROFILE "ki-lab\repos"
if (-not (Test-Path $repoBase)) {
    New-Item -ItemType Directory -Path $repoBase -Force | Out-Null
}
Write-Host "Zielverzeichnis: $repoBase" -ForegroundColor Cyan

# Reihenfolge bewusst:
#   1. Vorzeige-Repo (gel. Use Cases handwerklich + industriell)
#   2./3. Uebungs-Repos (Arno-CR / Bartek-IS, leerer Platz fuer echte Aufgaben)
#   4. rechner-pipeline (Showcase agentisch, langgraph)
$repos = @(
    @{ Name = "portxlpy-seminar-2026-02-eaa";       Url = "https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa.git" },
    @{ Name = "portxlpy-seminar-2026-02-eaa-ex-cr"; Url = "https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa-ex-cr.git" },
    @{ Name = "portxlpy-seminar-2026-02-eaa-ex-is"; Url = "https://github.com/bartlmac/portxlpy-seminar-2026-02-eaa-ex-is.git" },
    @{ Name = "rechner-pipeline";                   Url = "https://github.com/bartlmac/rechner-pipeline.git" }
)

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "FEHLER: git ist nicht im PATH - Clone uebersprungen." -ForegroundColor Red
} else {
    foreach ($r in $repos) {
        $target = Join-Path $repoBase $r.Name
        if (Test-Path $target) {
            Write-Host "  $($r.Name) bereits vorhanden - pull..." -ForegroundColor Yellow
            try {
                git -C $target pull --ff-only
            } catch {
                Write-Host "    Pull fehlgeschlagen ($_) - manueller Check noetig." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  Clone $($r.Name)..." -ForegroundColor Yellow
            try {
                git clone $r.Url $target
            } catch {
                Write-Host "    Clone fehlgeschlagen ($_)." -ForegroundColor Red
                continue
            }
        }
    }

    # requirements.txt nur fuer rechner-pipeline nachziehen (4 Pakete, sauber).
    # Seminar-Repos absichtlich nicht via -r installieren, da deren requirements.txt
    # gepinnte Versionen und nicht-genutzte Pakete (junit2html, pytest-html) enthalten -
    # die Basis aus Schritt 9 reicht.
    $rpReq = Join-Path $repoBase "rechner-pipeline\requirements.txt"
    if (Test-Path $rpReq) {
        Write-Host "    pip install -r rechner-pipeline\requirements.txt" -ForegroundColor Yellow
        try {
            python -m pip install -r $rpReq
        } catch {
            Write-Host "    pip install -r requirements.txt fehlgeschlagen ($_)." -ForegroundColor Yellow
        }
    }
}

# --------------------------------
# 13. .env-Vorlage fuer rechner-pipeline
# --------------------------------
# Use Case (3) "agentisch" laeuft am Stand nur auf den Laptops von Bartek
# und Arno. Helfer-Laptops bekommen keinen API-Key - die leere .env (ohne
# Wert) sorgt dafuer, dass Pipeline-Aufrufe dort sauber mit
# "OPENAI_API_KEY is not set" abbrechen.
Write-Step ".env fuer rechner-pipeline vorbereiten"
$rpEnv        = Join-Path $repoBase "rechner-pipeline\.env"
$rpEnvExample = Join-Path $repoBase "rechner-pipeline\.env.example"
if ((Test-Path $rpEnvExample) -and -not (Test-Path $rpEnv)) {
    Copy-Item $rpEnvExample $rpEnv
    Write-Host ".env angelegt: $rpEnv" -ForegroundColor Green
} elseif (Test-Path $rpEnv) {
    Write-Host ".env bereits vorhanden - nicht ueberschrieben." -ForegroundColor Green
} else {
    Write-Host "Hinweis: .env.example nicht gefunden in $rpEnvExample." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Nur auf Bartek- und Arno-Laptop (nicht auf Helfer-Laptops):" -ForegroundColor Yellow
Write-Host "  1. notepad `"$rpEnv`""
Write-Host "     -> OPENAI_API_KEY=sk-... eintragen, speichern"
Write-Host "  2. ACL setzen (nur der aktuelle User darf lesen):"
Write-Host "     `"$repoBase\rechner-pipeline\setup\set-env-acl.ps1`""
Write-Host "  Hintergrund: siehe api-key-konzept.md"

# --------------------------------
# Fertig
# --------------------------------
Write-Host ""
Write-Host "=== Setup erfolgreich abgeschlossen ===" -ForegroundColor Green
Write-Host "Naechste Schritte:" -ForegroundColor Cyan
Write-Host "  - Excel mindestens einmal oeffnen, damit das Trust-Center wirksam wird"
Write-Host "  - Bartek/Arno: OPENAI_API_KEY in $repoBase\rechner-pipeline\.env eintragen + set-env-acl.ps1"
Write-Host "  - Smoke-Test:"
Write-Host "      cd $repoBase\portxlpy-seminar-2026-02-eaa"
Write-Host "      pytest"
Write-Host "  - Alle Repos liegen unter: $repoBase"
