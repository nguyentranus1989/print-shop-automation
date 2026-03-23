@echo off
setlocal EnableDelayedExpansion
:: Install printflow-agent as a Windows service using NSSM.
:: Downloads NSSM from nssm.cc if not already present.
::
:: Must be run as Administrator.

:: -----------------------------------------------------------------------
:: 1. Elevation check
:: -----------------------------------------------------------------------
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [install-service] ERROR: This script must be run as Administrator.
    echo [install-service] Right-click the .bat file and choose "Run as administrator".
    pause
    exit /b 1
)

cd /d "%~dp0\.."
set ROOT=%CD%

:: -----------------------------------------------------------------------
:: 2. Verify the agent .exe exists
:: -----------------------------------------------------------------------
set AGENT_EXE=%ROOT%\dist\printflow-agent\printflow-agent.exe
if not exist "%AGENT_EXE%" (
    echo [install-service] ERROR: %AGENT_EXE% not found.
    echo [install-service] Run scripts\build-agent.bat first, then re-run this script.
    pause
    exit /b 1
)

:: -----------------------------------------------------------------------
:: 3. Locate or download NSSM
:: -----------------------------------------------------------------------
set NSSM_DIR=%ROOT%\tools\nssm
set NSSM_EXE=%NSSM_DIR%\nssm.exe

if not exist "%NSSM_EXE%" (
    echo [install-service] NSSM not found at %NSSM_EXE%.
    echo [install-service] Downloading NSSM 2.24 from nssm.cc ...

    if not exist "%NSSM_DIR%" mkdir "%NSSM_DIR%"

    :: Download NSSM zip using PowerShell (available on all Win10/11)
    set NSSM_ZIP=%TEMP%\nssm-2.24.zip
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile '%NSSM_ZIP%'"

    if %ERRORLEVEL% neq 0 (
        echo [install-service] ERROR: Failed to download NSSM. Check internet connection.
        pause
        exit /b 1
    )

    :: Extract the win64 executable
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path '%NSSM_ZIP%' -DestinationPath '%TEMP%\nssm-extract' -Force; Copy-Item '%TEMP%\nssm-extract\nssm-2.24\win64\nssm.exe' -Destination '%NSSM_EXE%'"

    if not exist "%NSSM_EXE%" (
        echo [install-service] ERROR: Failed to extract nssm.exe.
        pause
        exit /b 1
    )
    echo [install-service] NSSM downloaded to %NSSM_EXE%
)

echo [install-service] Using NSSM: %NSSM_EXE%

:: -----------------------------------------------------------------------
:: 4. Gather user input
:: -----------------------------------------------------------------------
echo.
echo --- PrintFlow Agent Service Setup ---
echo.

set /p SVC_NAME="Service name [PrintFlowAgent]: "
if "!SVC_NAME!"=="" set SVC_NAME=PrintFlowAgent

set /p AGENT_PORT="Agent HTTP port [8080]: "
if "!AGENT_PORT!"=="" set AGENT_PORT=8080

set /p PRINTER_TYPE="Printer type (auto/dtg/dtf/uv) [auto]: "
if "!PRINTER_TYPE!"=="" set PRINTER_TYPE=auto

set /p INSTALL_DIR="Install directory [%ROOT%\dist\printflow-agent]: "
if "!INSTALL_DIR!"=="" set INSTALL_DIR=%ROOT%\dist\printflow-agent

:: -----------------------------------------------------------------------
:: 5. Write agent.toml into the install directory
:: -----------------------------------------------------------------------
set TOML_FILE=%INSTALL_DIR%\agent.toml

echo [install-service] Writing config: %TOML_FILE%

(
    echo [agent]
    echo name = "!SVC_NAME!"
    echo poll_interval_seconds = 5
    echo.
    echo [printer]
    echo type = "!PRINTER_TYPE!"
    echo.
    echo [printexp]
    echo exe_path = "C:\\PrintExp_5.7.7.1.12_MULTIWS\\PrintExp.exe"
    echo tcp_port = 9100
    echo memory_offset = 0x016CDB
    echo.
    echo [network]
    echo port = !AGENT_PORT!
    echo dashboard_url = "http://localhost:8000"
    echo.
    echo [files]
    echo nas_path = "\\\\nas\\prn-files"
    echo temp_path = "C:\\Hstemp"
) > "%TOML_FILE%"

echo [install-service] Config written.

:: -----------------------------------------------------------------------
:: 6. Remove existing service if present (clean install)
:: -----------------------------------------------------------------------
"%NSSM_EXE%" status "!SVC_NAME!" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [install-service] Removing existing service "!SVC_NAME!"...
    "%NSSM_EXE%" stop "!SVC_NAME!" >nul 2>&1
    "%NSSM_EXE%" remove "!SVC_NAME!" confirm
)

:: -----------------------------------------------------------------------
:: 7. Install service via NSSM
:: -----------------------------------------------------------------------
echo [install-service] Installing service "!SVC_NAME!"...

"%NSSM_EXE%" install "!SVC_NAME!" "%INSTALL_DIR%\printflow-agent.exe"
"%NSSM_EXE%" set "!SVC_NAME!" AppParameters "--port !AGENT_PORT! --config ""%TOML_FILE%"" --printer-type !PRINTER_TYPE!"
"%NSSM_EXE%" set "!SVC_NAME!" AppDirectory "%INSTALL_DIR%"
"%NSSM_EXE%" set "!SVC_NAME!" DisplayName "PrintFlow Agent (!SVC_NAME!)"
"%NSSM_EXE%" set "!SVC_NAME!" Description "PrintFlow printer agent — HTTP API for dashboard integration"
"%NSSM_EXE%" set "!SVC_NAME!" Start SERVICE_AUTO_START
"%NSSM_EXE%" set "!SVC_NAME!" AppStdout "%INSTALL_DIR%\logs\service-stdout.log"
"%NSSM_EXE%" set "!SVC_NAME!" AppStderr "%INSTALL_DIR%\logs\service-stderr.log"
"%NSSM_EXE%" set "!SVC_NAME!" AppRotateFiles 1
"%NSSM_EXE%" set "!SVC_NAME!" AppRotateBytes 10485760

:: Create logs directory
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

:: -----------------------------------------------------------------------
:: 8. Start the service
:: -----------------------------------------------------------------------
echo [install-service] Starting service "!SVC_NAME!"...
"%NSSM_EXE%" start "!SVC_NAME!"

:: -----------------------------------------------------------------------
:: 9. Show status
:: -----------------------------------------------------------------------
echo.
echo [install-service] Service status:
"%NSSM_EXE%" status "!SVC_NAME!"

echo.
echo [install-service] Done.
echo [install-service] Health check: curl http://localhost:!AGENT_PORT!/health
echo [install-service] Logs: %INSTALL_DIR%\logs\
echo.
pause
endlocal
