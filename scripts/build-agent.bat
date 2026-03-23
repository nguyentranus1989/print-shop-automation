@echo off
:: Build printflow-agent.exe using PyInstaller (--onedir, console mode).
:: Run from anywhere — this script always resolves to the workspace root.

cd /d "%~dp0\.."

echo [build-agent] Workspace: %CD%
echo [build-agent] Running PyInstaller...

uv run pyinstaller scripts\agent.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo [build-agent] ERROR: PyInstaller failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo [build-agent] Build complete.
echo [build-agent] Output: dist\printflow-agent\printflow-agent.exe
echo.
echo [build-agent] Quick test (mock mode, port 8081):
echo   dist\printflow-agent\printflow-agent.exe --mock --port 8081
echo.
echo [build-agent] Health check (from another terminal):
echo   curl http://localhost:8081/health
