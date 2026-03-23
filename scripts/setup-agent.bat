@echo off
setlocal EnableDelayedExpansion
:: PrintFlow Agent — First-Run Setup Wizard
:: Asks for PrintExp path, auto-detects printer type, writes agent.toml.

:: Resolve root — works from both scripts\ (dev) and deploy folder
cd /d "%~dp0"
if exist "agent\printflow-agent.exe" (
    set ROOT=%CD%
    set AGENT_DIR=%CD%\agent
    goto :root_found
)
:: Try parent (when called from scripts\ subfolder)
cd /d "%~dp0\.."
if exist "agent\printflow-agent.exe" (
    set ROOT=%CD%
    set AGENT_DIR=%CD%\agent
    goto :root_found
)
if exist "dist\printflow-agent\printflow-agent.exe" (
    set ROOT=%CD%
    set AGENT_DIR=%CD%\dist\printflow-agent
    goto :root_found
)
:: Fallback — write config in script's directory
set ROOT=%~dp0
set AGENT_DIR=%~dp0
:root_found

set TOML_FILE=%AGENT_DIR%\agent.toml

echo.
echo ================================================================
echo   PrintFlow Agent Setup
echo ================================================================
echo.

:: Check if config already exists
if exist "%TOML_FILE%" (
    echo   Existing config found: %TOML_FILE%
    echo.
    set /p OVERWRITE="   Overwrite? (y/N): "
    if /i not "!OVERWRITE!"=="y" (
        echo   Keeping existing config.
        goto :done
    )
    echo.
)

:: -----------------------------------------------------------------------
:: 1. Ask for PrintExp path
:: -----------------------------------------------------------------------
echo   [1/3] Where is PrintExp installed?
echo.
echo   Common locations:
echo     C:\PrintExp_5.7.7.1.12_MULTIWS
echo     C:\PrintExp
echo     D:\PrintExp
echo.

:ask_path
set /p PRINTEXP_DIR="   PrintExp folder: "

if "!PRINTEXP_DIR!"=="" (
    echo   ERROR: Path cannot be empty.
    goto :ask_path
)

:: Strip trailing backslash
if "!PRINTEXP_DIR:~-1!"=="\" set PRINTEXP_DIR=!PRINTEXP_DIR:~0,-1!

:: Check if folder exists
if not exist "!PRINTEXP_DIR!" (
    echo   ERROR: Folder not found: !PRINTEXP_DIR!
    echo   Please check the path and try again.
    echo.
    goto :ask_path
)

:: Find PrintExp.exe (32-bit or 64-bit)
set PRINTEXP_EXE=
if exist "!PRINTEXP_DIR!\PrintExp.exe" (
    set PRINTEXP_EXE=!PRINTEXP_DIR!\PrintExp.exe
    set ARCH=32-bit
)
if exist "!PRINTEXP_DIR!\PrintExp_X64.exe" (
    set PRINTEXP_EXE=!PRINTEXP_DIR!\PrintExp_X64.exe
    set ARCH=64-bit
)

if "!PRINTEXP_EXE!"=="" (
    echo   WARNING: No PrintExp.exe found in that folder.
    echo   The agent will still work but auto-detection may fail.
    set PRINTEXP_EXE=!PRINTEXP_DIR!\PrintExp.exe
    set ARCH=unknown
)

echo   Found: !PRINTEXP_EXE! (!ARCH!^)
echo.

:: -----------------------------------------------------------------------
:: 2. Auto-detect printer type from DLLs
:: -----------------------------------------------------------------------
echo   [2/3] Detecting printer type...

set PRINTER_TYPE=auto
set DETECTED_FROM=default

:: Check for DTF/UV-specific DLLs
if exist "!PRINTEXP_DIR!\CraftFlow.dll" (
    set PRINTER_TYPE=uv
    set DETECTED_FROM=CraftFlow.dll found
    goto :type_done
)

:: 64-bit exe = DTF or UV, 32-bit = DTG
if "!ARCH!"=="64-bit" (
    :: Check for UV-specific files
    if exist "!PRINTEXP_DIR!\UVDevice.dll" (
        set PRINTER_TYPE=uv
        set DETECTED_FROM=UVDevice.dll found
        goto :type_done
    )
    if exist "!PRINTEXP_DIR!\DTFDevice.dll" (
        set PRINTER_TYPE=dtf
        set DETECTED_FROM=DTFDevice.dll found
        goto :type_done
    )
    :: 64-bit but can't tell — likely DTF
    set PRINTER_TYPE=dtf
    set DETECTED_FROM=64-bit executable
    goto :type_done
)

if "!ARCH!"=="32-bit" (
    set PRINTER_TYPE=dtg
    set DETECTED_FROM=32-bit executable
    goto :type_done
)

:: Check KRemoteMonitor.dll presence
if exist "!PRINTEXP_DIR!\KRemoteMonitor.dll" (
    :: Has KRemoteMonitor = DTF or UV (not DTG)
    if exist "!PRINTEXP_DIR!\CraftFlow.dll" (
        set PRINTER_TYPE=uv
        set DETECTED_FROM=KRemoteMonitor.dll + CraftFlow.dll
    ) else (
        set PRINTER_TYPE=dtf
        set DETECTED_FROM=KRemoteMonitor.dll present
    )
) else (
    set PRINTER_TYPE=dtg
    set DETECTED_FROM=no KRemoteMonitor.dll
)

:type_done
echo   Detected: !PRINTER_TYPE! (!DETECTED_FROM!^)
echo.

:: Let user override
set /p TYPE_OVERRIDE="   Printer type [!PRINTER_TYPE!] (dtg/dtf/uv): "
if not "!TYPE_OVERRIDE!"=="" (
    if /i "!TYPE_OVERRIDE!"=="dtg" set PRINTER_TYPE=dtg
    if /i "!TYPE_OVERRIDE!"=="dtf" set PRINTER_TYPE=dtf
    if /i "!TYPE_OVERRIDE!"=="uv" set PRINTER_TYPE=uv
)
echo.

:: -----------------------------------------------------------------------
:: 3. Ask for port
:: -----------------------------------------------------------------------
echo   [3/3] Agent HTTP port
set /p AGENT_PORT="   Port [8080]: "
if "!AGENT_PORT!"=="" set AGENT_PORT=8080
echo.

:: -----------------------------------------------------------------------
:: 4. Set defaults for the rest
:: -----------------------------------------------------------------------
set AGENT_NAME=PrintFlow-Agent
set TCP_PORT=9100
set MEM_OFFSET=0x016CDB
set TEMP_PATH=C:\Hstemp

:: -----------------------------------------------------------------------
:: 5. Write agent.toml
:: -----------------------------------------------------------------------
echo   Writing config: %TOML_FILE%

:: Escape backslashes for TOML (double them)
set "ESC_EXE=!PRINTEXP_EXE:\=\\!"
set "ESC_TEMP=!TEMP_PATH:\=\\!"

(
    echo [agent]
    echo name = "!AGENT_NAME!"
    echo poll_interval_seconds = 5
    echo.
    echo [printer]
    echo type = "!PRINTER_TYPE!"
    echo.
    echo [printexp]
    echo exe_path = "!ESC_EXE!"
    echo tcp_port = !TCP_PORT!
    echo memory_offset = !MEM_OFFSET!
    echo.
    echo [network]
    echo port = !AGENT_PORT!
    echo dashboard_url = "http://localhost:8000"
    echo.
    echo [files]
    echo nas_path = "\\\\nas\\prn-files"
    echo temp_path = "!ESC_TEMP!"
) > "%TOML_FILE%"

echo.
echo ================================================================
echo   Setup Complete!
echo ================================================================
echo.
echo   Printer type:  !PRINTER_TYPE!
echo   PrintExp path: !PRINTEXP_EXE!
echo   Agent port:    !AGENT_PORT!
echo   Config file:   %TOML_FILE%
echo.
echo   To start the agent:
echo     run-agent.bat
echo.
echo   To install as Windows service:
echo     install-service.bat  (Run as Administrator)
echo.

:done
pause
endlocal
