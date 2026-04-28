# ================================
# .env ACL setzen
# ================================
# Setzt die NTFS-Berechtigungen auf rechner-pipeline\.env so, dass NUR
# der aktuelle Windows-Benutzer lesen und schreiben darf - Vererbung wird
# entfernt, alle anderen lokalen User (auch Helfer-Accounts) verlieren
# damit den Lese-Zugriff.
#
# Anwendung:
#   - Auf Bartek- und Arno-Laptop einmalig ausfuehren, nachdem .env mit
#     dem OPENAI_API_KEY befuellt wurde.
#   - Auf Helfer-Laptops nicht noetig (.env bleibt leer).
#
# Hinweis: Lokaler Admin kann den Schutz umgehen (Owner aendern). Das ist
# fuer das KI-Lab-Setting akzeptabel - siehe api-key-konzept.md.

$ErrorActionPreference = "Stop"

# Pfad zur .env relativ zum Skript-Verzeichnis (setup/) eine Ebene hoch.
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile  = Join-Path $repoRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "FEHLER: $envFile nicht gefunden." -ForegroundColor Red
    Write-Host "Zuerst .env anlegen (z. B. Copy-Item .env.example .env) und OPENAI_API_KEY eintragen."
    exit 1
}

$user = "$env:USERDOMAIN\$env:USERNAME"
Write-Host "Setze ACL auf $envFile fuer $user (R,W) - Vererbung entfernen..." -ForegroundColor Cyan

# /inheritance:r entfernt vererbte Berechtigungen.
# /grant:r ersetzt bestehende explizite Eintraege fuer den User.
icacls $envFile /inheritance:r /grant:r "${user}:(R,W)" | Out-Null

Write-Host ""
Write-Host "Aktuelle ACL:" -ForegroundColor Cyan
icacls $envFile

Write-Host ""
Write-Host "Fertig. Pruefe oben, dass NUR $user als Berechtigter aufgefuehrt ist." -ForegroundColor Green
