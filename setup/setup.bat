@echo off
REM ================================
REM Bootstrap fuer setupdav.ps1
REM ================================
REM Doppelklick startet das PowerShell-Setup-Skript ohne dass
REM ExecutionPolicy vorher manuell gesetzt werden muss.
REM
REM Voraussetzung: setupdav.ps1 liegt im selben Verzeichnis wie diese .bat.

setlocal
set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%setupdav.ps1"

if not exist "%PS1%" (
    echo FEHLER: setupdav.ps1 nicht gefunden in %SCRIPT_DIR%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "RC=%ERRORLEVEL%"

echo.
if %RC% NEQ 0 (
    echo Setup mit Fehler beendet ^(Exit-Code %RC%^).
) else (
    echo Setup beendet.
)
pause
exit /b %RC%
