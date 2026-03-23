@echo off
:: PrintFlow Agent — Setup Wizard (launches GUI)
:: Finds and runs setup-agent-gui.ps1 from the same directory.

:: Find the PowerShell script (same folder as this bat)
set PS_SCRIPT=%~dp0setup-agent-gui.ps1

if not exist "%PS_SCRIPT%" (
    echo [setup] ERROR: setup-agent-gui.ps1 not found next to this bat file.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
exit /b %ERRORLEVEL%
