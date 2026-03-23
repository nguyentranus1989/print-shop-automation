@echo off
:: Build printflow-dashboard.exe using PyInstaller (--onedir, console mode).
:: Run from anywhere — this script always resolves to the workspace root.

cd /d "%~dp0\.."

echo [build-dashboard] Workspace: %CD%
echo [build-dashboard] Running PyInstaller...

uv run pyinstaller scripts\dashboard.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo [build-dashboard] ERROR: PyInstaller failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo [build-dashboard] Build complete.
echo [build-dashboard] Output: dist\printflow-dashboard\printflow-dashboard.exe
echo.
echo [build-dashboard] Quick test (default port 8000):
echo   dist\printflow-dashboard\printflow-dashboard.exe
echo.
echo [build-dashboard] Health check (from another terminal):
echo   curl http://localhost:8000/health
