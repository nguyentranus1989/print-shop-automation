@echo off
:: Run printflow-agent directly (not as a Windows service).
:: Good for testing and development — shows live console output.
::
:: Usage:
::   run-agent.bat                  — real mode, port 8080
::   run-agent.bat --mock           — mock mode (no printer required)
::   run-agent.bat --mock --port 8081
::   run-agent.bat --printer-type dtg

cd /d "%~dp0\.."

set AGENT_EXE=dist\printflow-agent\printflow-agent.exe

if not exist "%AGENT_EXE%" (
    echo [run-agent] ERROR: %AGENT_EXE% not found.
    echo [run-agent] Run scripts\build-agent.bat first.
    exit /b 1
)

echo [run-agent] Starting PrintFlow Agent...
echo [run-agent] Press Ctrl+C to stop.
echo.

"%AGENT_EXE%" %*
