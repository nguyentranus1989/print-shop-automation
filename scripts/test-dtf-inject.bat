@echo off
:: Self-elevate to admin
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "C:\Users\12104\Projects\print-shop-automation"
echo Running as Administrator...
.venv\Scripts\python.exe scripts\test-dtf-inject.py
pause
