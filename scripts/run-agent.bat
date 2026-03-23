@echo off
:: Run printflow-agent directly (not as a Windows service).
:: Good for testing and development — shows live console output.
:: On first run, launches setup wizard if no agent.toml exists.
::
:: Usage:
::   run-agent.bat                  — real mode, port 8080
::   run-agent.bat --mock           — mock mode (no printer required)
::   run-agent.bat --mock --port 8081
::   run-agent.bat --printer-type dtg

cd /d "%~dp0\.."

:: Detect exe location (deploy folder vs dev build)
if exist "agent\printflow-agent.exe" (
    set AGENT_EXE=agent\printflow-agent.exe
    set AGENT_DIR=agent
) else if exist "dist\printflow-agent\printflow-agent.exe" (
    set AGENT_EXE=dist\printflow-agent\printflow-agent.exe
    set AGENT_DIR=dist\printflow-agent
) else (
    echo [run-agent] ERROR: printflow-agent.exe not found.
    echo [run-agent] Expected in agent\ or dist\printflow-agent\
    pause
    exit /b 1
)

:: Check for agent.toml — run setup if missing (skip for --mock)
echo %* | findstr /i "\-\-mock" >nul
if %ERRORLEVEL% neq 0 (
    if not exist "%AGENT_DIR%\agent.toml" (
        echo [run-agent] No agent.toml found — starting setup wizard...
        echo.
        call scripts\setup-agent.bat 2>nul || call setup-agent.bat 2>nul
        if not exist "%AGENT_DIR%\agent.toml" (
            echo [run-agent] Setup did not create agent.toml. Cannot start.
            pause
            exit /b 1
        )
    )
)

echo [run-agent] Starting PrintFlow Agent...
echo [run-agent] Press Ctrl+C to stop.
echo.

"%AGENT_EXE%" %*
