<#
.SYNOPSIS
Richtet die Arbeitsumgebung der Vorfuehrung auf einem Windows-Rechner ein.

.DESCRIPTION
Prueft bzw. schaltet WSL 2 ein, importiert das Abbild der Arbeitsumgebung
(deploy/workshop/abbild_bauen.sh) als EIGENE WSL-Distribution, faehrt die
Selbstpruefung und legt eine Verknuepfung auf den Schreibtisch.

Zwei Aufrufe sind noetig, wenn WSL auf dem Rechner noch fehlt:
  1. in einer PowerShell "Als Administrator": schaltet WSL ein, danach
     den Rechner neu starten;
  2. in einer gewoehnlichen PowerShell (ohne Administrator): importiert.
Ist WSL schon da, genuegt der zweite.

Nichts wird ersetzt: Gibt es die Distribution schon, haelt das Skript an
und nennt den Ausweg. -Ersetzen entfernt sie SAMT allem, was darin liegt
(Faelle, Schluessel, eigene Arbeit).

Das Skript ist reines ASCII: Windows PowerShell 5.1 liest eine Datei ohne
BOM nicht als UTF-8.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Abbild D:\plv-arbeitsumgebung-v1.tar.gz

.EXAMPLE
powershell -ExecutionPolicy Bypass -File einrichten.ps1 -AbbildUrl https://<adresse>/plv-arbeitsumgebung-v1.tar.gz -Pruefsumme <sha256>
#>
[CmdletBinding()]
param(
    # Das Abbild als lokale Datei (tar.gz). Liegt daneben <datei>.sha256,
    # wird sie als Pruefsumme gelesen.
    [string]$Abbild,
    # Das Abbild aus dem Netz; verlangt -Pruefsumme.
    [string]$AbbildUrl,
    # SHA-256 des Abbilds (hexadezimal).
    [string]$Pruefsumme,
    # Name der WSL-Distribution.
    [string]$Name = "PLV-Arbeitsumgebung",
    # Wo Windows die Platte der Distribution ablegt.
    [string]$Ziel = (Join-Path $env:LOCALAPPDATA "PLV-Arbeitsumgebung"),
    # Eine bestehende Distribution gleichen Namens samt Inhalt entfernen.
    [switch]$Ersetzen,
    [switch]$OhneVerknuepfung
)

$ErrorActionPreference = "Stop"

function Halt([string]$Text, [int]$Code = 2) {
    Write-Host "HALT: $Text" -ForegroundColor Red
    exit $Code
}

function Schritt([string]$Text) {
    Write-Host ""
    Write-Host "== $Text" -ForegroundColor Cyan
}

function Test-Distribution([string]$Gesucht) {
    # Die Registrierung statt `wsl -l`: dessen Ausgabe ist UTF-16 und laesst
    # sich in PowerShell 5.1 nicht verlaesslich vergleichen.
    $pfad = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss"
    if (-not (Test-Path $pfad)) { return $false }
    foreach ($eintrag in Get-ChildItem $pfad) {
        $werte = Get-ItemProperty $eintrag.PSPath
        if ($werte.DistributionName -eq $Gesucht) { return $true }
    }
    return $false
}

$wsl = Join-Path $env:SystemRoot "System32\wsl.exe"
$istAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

# --- 1. Windows und WSL -----------------------------------------------------
Schritt "Windows und WSL pruefen"
$build = [Environment]::OSVersion.Version.Build
if ($build -lt 19041) {
    Halt "Windows 10 ab Version 2004 (Build 19041) oder Windows 11 ist noetig; gefunden: Build $build"
}
if (-not (Test-Path $wsl)) {
    Halt "wsl.exe fehlt unter $wsl - dieses Windows traegt kein WSL"
}

# Ueber cmd und nur der Exit-Code: Windows PowerShell 5.1 macht aus der
# umgeleiteten Fehlerausgabe eines nativen Programms einen abbrechenden
# Fehler, auch wenn das Programm selbst erfolgreich war.
# Bereit ist WSL, wenn eine der beiden Auskuenfte gelingt: --version kennt nur
# das vollstaendig installierte WSL, --status auch ein aelteres.
& cmd.exe /c "$wsl --version >nul 2>&1"
$wslBereit = ($LASTEXITCODE -eq 0)
if (-not $wslBereit) {
    & cmd.exe /c "$wsl --status >nul 2>&1"
    $wslBereit = ($LASTEXITCODE -eq 0)
}

if (-not $wslBereit) {
    if (-not $istAdmin) {
        Halt ("WSL ist auf diesem Rechner noch nicht eingeschaltet. Dieses Skript einmal in einer " +
              "PowerShell 'Als Administrator' aufrufen (es schaltet WSL ein), den Rechner neu starten " +
              "und es danach in einer gewoehnlichen PowerShell erneut aufrufen.") 3
    }
    Write-Host "WSL wird eingeschaltet (braucht Netz, kann einige Minuten dauern) ..."
    & $wsl --install --no-distribution
    if ($LASTEXITCODE -ne 0) {
        Write-Host "wsl --install scheiterte (Exit $LASTEXITCODE). Ersatzweg von Hand, als Administrator:"
        Write-Host "  dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart"
        Write-Host "  dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart"
        Write-Host "  danach neu starten und: wsl --update"
        exit 3
    }
    Write-Host ""
    Write-Host "WSL ist eingeschaltet. Den Rechner jetzt NEU STARTEN und dieses Skript danach" -ForegroundColor Yellow
    Write-Host "in einer gewoehnlichen PowerShell (ohne Administrator) erneut aufrufen." -ForegroundColor Yellow
    exit 3
}

if ($istAdmin) {
    Halt ("WSL ist bereit. Den Import bitte in einer gewoehnlichen PowerShell (ohne Administrator) " +
          "aufrufen: Eine als Administrator importierte Umgebung gehoert dem Administratorkonto.") 3
}

# Ohne Virtualisierung startet keine WSL-2-Distribution. Laeuft schon ein
# Hypervisor, ist die Frage beantwortet (und die Firmware-Angabe dann nicht
# aussagekraeftig).
$system = Get-CimInstance Win32_ComputerSystem
if (-not $system.HypervisorPresent) {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($cpu.VirtualizationFirmwareEnabled -eq $false) {
        Halt "Die Virtualisierung ist in der Firmware (BIOS/UEFI) abgeschaltet - dort einschalten (Intel VT-x bzw. AMD-V/SVM), dann erneut aufrufen"
    }
}
Write-Host "Windows Build $build, WSL bereit."

# --- 2. Das Abbild ----------------------------------------------------------
Schritt "Abbild bereitstellen"
if ($AbbildUrl) {
    if (-not $Pruefsumme) {
        Halt "-AbbildUrl verlangt -Pruefsumme: Ein aus dem Netz geholtes Abbild wird nie ungeprueft importiert"
    }
    $dateiname = [IO.Path]::GetFileName(([Uri]$AbbildUrl).AbsolutePath)
    $Abbild = Join-Path $env:TEMP $dateiname
    Write-Host "Lade $AbbildUrl ..."
    & (Join-Path $env:SystemRoot "System32\curl.exe") -L --fail -o $Abbild $AbbildUrl
    if ($LASTEXITCODE -ne 0) { Halt "Das Abbild liess sich nicht laden (curl Exit $LASTEXITCODE)" }
}
if (-not $Abbild) { Halt "-Abbild <datei.tar.gz> oder -AbbildUrl <adresse> angeben" }
if (-not (Test-Path $Abbild)) { Halt "Das Abbild $Abbild liegt nicht" }
$Abbild = (Resolve-Path $Abbild).Path

if (-not $Pruefsumme -and (Test-Path "$Abbild.sha256")) {
    $Pruefsumme = ((Get-Content "$Abbild.sha256" -TotalCount 1) -split "\s+")[0]
    Write-Host "Pruefsumme aus $Abbild.sha256 gelesen."
}
if ($Pruefsumme) {
    $ist = (Get-FileHash -Algorithm SHA256 -Path $Abbild).Hash.ToLower()
    if ($ist -ne $Pruefsumme.Trim().ToLower()) {
        Halt "Die Pruefsumme des Abbilds weicht ab. Erwartet $Pruefsumme, gefunden $ist - die Datei ist beschaedigt oder eine andere"
    }
    Write-Host "Pruefsumme stimmt: $ist"
} else {
    Write-Host "Hinweis: keine Pruefsumme genannt - das Abbild wird ungeprueft importiert." -ForegroundColor Yellow
}

# --- 3. Importieren ---------------------------------------------------------
Schritt "Distribution $Name importieren"
if (Test-Distribution $Name) {
    if (-not $Ersetzen) {
        Halt ("Die Distribution $Name gibt es schon. Starten: wsl -d $Name. Neu einrichten nur mit -Ersetzen - " +
              "das entfernt sie SAMT allem, was darin liegt (Faelle, Schluessel, eigene Arbeit).")
    }
    Write-Host "Entferne die bestehende Distribution $Name (-Ersetzen) ..." -ForegroundColor Yellow
    & $wsl --unregister $Name
    if ($LASTEXITCODE -ne 0) { Halt "Die bestehende Distribution liess sich nicht entfernen (Exit $LASTEXITCODE)" }
}
if (-not (Test-Path $Ziel)) { New-Item -ItemType Directory -Path $Ziel | Out-Null }
# Die Platte der Distribution waechst mit der Arbeit; unter 10 GB frei wird
# nicht begonnen.
$laufwerk = Get-PSDrive -Name ((Resolve-Path $Ziel).Drive.Name)
if ($laufwerk.Free -lt 10GB) {
    Halt ("Auf Laufwerk " + $laufwerk.Name + ": sind nur " + [math]::Round($laufwerk.Free / 1GB, 1) +
          " GB frei; die Umgebung braucht mindestens 10 GB (anderes Ziel: -Ziel <verzeichnis>)")
}
& $wsl --import $Name $Ziel $Abbild --version 2
if ($LASTEXITCODE -ne 0) {
    Halt "Der Import scheiterte (Exit $LASTEXITCODE). Meldet Windows einen Fehler zur Virtualisierung: in der Firmware einschalten und 'wsl --update' fahren."
}

# --- 4. Selbstpruefung ------------------------------------------------------
Schritt "Selbstpruefung in der Umgebung"
& $wsl -d $Name -- bash -lc "plv-einrichten pruefen"
$pruefung = $LASTEXITCODE

# --- 5. Verknuepfung --------------------------------------------------------
if (-not $OhneVerknuepfung) {
    $shell = New-Object -ComObject WScript.Shell
    $datei = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Name.lnk"
    $verknuepfung = $shell.CreateShortcut($datei)
    $verknuepfung.TargetPath = $wsl
    $verknuepfung.Arguments = "-d $Name --cd ~"
    $verknuepfung.Description = "Arbeitsumgebung der Vorfuehrung (WSL)"
    $verknuepfung.Save()
    Write-Host ""
    Write-Host "Verknuepfung angelegt: $datei"
}

Write-Host ""
if ($pruefung -eq 0) {
    Write-Host "Eingerichtet. Starten: Verknuepfung '$Name' oder  wsl -d $Name" -ForegroundColor Green
    exit 0
}
Write-Host "Importiert, aber die Selbstpruefung ist NICHT bestanden (Exit $pruefung) - die Ausgabe oben nennt den Punkt." -ForegroundColor Red
exit 1
