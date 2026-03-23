@echo off
:: Build and package everything into a deploy-ready folder.
:: Output: dist\PrintFlow\ — copy this entire folder to the target machine.

cd /d "%~dp0\.."
set ROOT=%CD%
set DEPLOY=%ROOT%\dist\PrintFlow

echo [package] Building agent...
call scripts\build-agent.bat
if %ERRORLEVEL% neq 0 (
    echo [package] ERROR: Agent build failed.
    exit /b 1
)

echo.
echo [package] Building dashboard...
call scripts\build-dashboard.bat
if %ERRORLEVEL% neq 0 (
    echo [package] ERROR: Dashboard build failed.
    exit /b 1
)

echo.
echo [package] Assembling deployment folder...

:: Create deploy structure
if exist "%DEPLOY%" rmdir /s /q "%DEPLOY%"
mkdir "%DEPLOY%"
mkdir "%DEPLOY%\agent"
mkdir "%DEPLOY%\dashboard"

:: Copy agent
xcopy /E /Q "%ROOT%\dist\printflow-agent\*" "%DEPLOY%\agent\" >nul

:: Copy dashboard
xcopy /E /Q "%ROOT%\dist\printflow-dashboard\*" "%DEPLOY%\dashboard\" >nul

:: Copy config template for dashboard
copy "%ROOT%\.env.example" "%DEPLOY%\dashboard\.env" >nul

:: Copy scripts
copy "%ROOT%\scripts\setup-agent.bat" "%DEPLOY%\" >nul
copy "%ROOT%\scripts\install-service.bat" "%DEPLOY%\" >nul
copy "%ROOT%\scripts\uninstall-service.bat" "%DEPLOY%\" >nul
copy "%ROOT%\scripts\printer-test.py" "%DEPLOY%\" >nul

:: Write run-agent.bat (deploy version)
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo.
    echo :: Check for agent.toml — run setup if missing ^(skip for --mock^)
    echo echo %%* ^| findstr /i "\-\-mock" ^>nul
    echo if %%ERRORLEVEL%% neq 0 ^(
    echo     if not exist "agent\agent.toml" ^(
    echo         echo [run-agent] No config found — starting setup wizard...
    echo         echo.
    echo         call setup-agent.bat
    echo         if not exist "agent\agent.toml" ^(
    echo             echo [run-agent] Setup cancelled.
    echo             pause
    echo             exit /b 1
    echo         ^)
    echo     ^)
    echo ^)
    echo.
    echo echo [run-agent] Starting PrintFlow Agent...
    echo echo [run-agent] Press Ctrl+C to stop.
    echo echo.
    echo agent\printflow-agent.exe %%*
) > "%DEPLOY%\run-agent.bat"

:: Write run-dashboard.bat
(
    echo @echo off
    echo echo Starting PrintFlow Dashboard...
    echo dashboard\printflow-dashboard.exe %%*
) > "%DEPLOY%\run-dashboard.bat"

:: Write README
(
    echo ================================================================
    echo   PrintFlow — Quick Start Guide
    echo ================================================================
    echo.
    echo   STEP 1: Run the setup wizard
    echo     Double-click: run-agent.bat
    echo     It will ask for your PrintExp folder and auto-detect the rest.
    echo.
    echo   STEP 2: Start the dashboard
    echo     Double-click: run-dashboard.bat
    echo     Open: http://localhost:8000
    echo.
    echo   STEP 3: Install as Windows service ^(optional^)
    echo     Right-click install-service.bat → Run as Administrator
    echo     The agent will auto-start on boot.
    echo.
    echo   STEP 4: Register the printer in the dashboard
    echo     Open http://localhost:8000/printers and add the agent.
    echo.
    echo   PRINTER TEST ^(optional, needs Python 3.10+^):
    echo     python printer-test.py
    echo.
    echo ================================================================
) > "%DEPLOY%\README.txt"

echo.
echo [package] Done!
echo [package] Deploy folder: %DEPLOY%
echo.
echo [package] Contents:
dir /b "%DEPLOY%"
echo.

:: Show total size
for /f "tokens=3" %%a in ('dir /s "%DEPLOY%" ^| findstr "File(s)"') do echo [package] Total size: %%a bytes
echo.
pause
