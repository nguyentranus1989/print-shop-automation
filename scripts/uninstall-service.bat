@echo off
setlocal EnableDelayedExpansion
:: Uninstall the PrintFlow Agent Windows service.
:: Optionally deletes the dist/ files.
::
:: Must be run as Administrator.

:: -----------------------------------------------------------------------
:: 1. Elevation check
:: -----------------------------------------------------------------------
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [uninstall-service] ERROR: This script must be run as Administrator.
    echo [uninstall-service] Right-click the .bat file and choose "Run as administrator".
    pause
    exit /b 1
)

cd /d "%~dp0\.."
set ROOT=%CD%
set NSSM_EXE=%ROOT%\tools\nssm\nssm.exe

:: -----------------------------------------------------------------------
:: 2. Get service name
:: -----------------------------------------------------------------------
echo.
set /p SVC_NAME="Service name to remove [PrintFlowAgent]: "
if "!SVC_NAME!"=="" set SVC_NAME=PrintFlowAgent

:: -----------------------------------------------------------------------
:: 3. Verify NSSM
:: -----------------------------------------------------------------------
if not exist "%NSSM_EXE%" (
    echo [uninstall-service] WARNING: NSSM not found at %NSSM_EXE%.
    echo [uninstall-service] Attempting to use sc.exe as fallback...
    set USE_SC=1
) else (
    set USE_SC=0
)

:: -----------------------------------------------------------------------
:: 4. Stop and remove the service
:: -----------------------------------------------------------------------
echo [uninstall-service] Stopping service "!SVC_NAME!"...

if "!USE_SC!"=="1" (
    sc stop "!SVC_NAME!" >nul 2>&1
    sc delete "!SVC_NAME!"
) else (
    "%NSSM_EXE%" stop "!SVC_NAME!" >nul 2>&1
    "%NSSM_EXE%" remove "!SVC_NAME!" confirm
)

if %ERRORLEVEL% neq 0 (
    echo [uninstall-service] WARNING: Service removal returned error %ERRORLEVEL%.
    echo [uninstall-service] It may have already been removed, or the name was wrong.
)

echo [uninstall-service] Service "!SVC_NAME!" removed.

:: -----------------------------------------------------------------------
:: 5. Optional: delete dist files
:: -----------------------------------------------------------------------
echo.
set /p DELETE_FILES="Delete dist\printflow-agent\ files? (y/N): "
if /i "!DELETE_FILES!"=="y" (
    set DIST_DIR=%ROOT%\dist\printflow-agent
    if exist "!DIST_DIR!" (
        echo [uninstall-service] Deleting !DIST_DIR! ...
        rmdir /s /q "!DIST_DIR!"
        echo [uninstall-service] Deleted.
    ) else (
        echo [uninstall-service] !DIST_DIR! not found — nothing to delete.
    )
) else (
    echo [uninstall-service] Keeping dist files.
)

echo.
echo [uninstall-service] Done.
pause
endlocal
