@echo off
:: Start dashboard + 3 mock agents for local development.
:: Run from anywhere — resolves to workspace root automatically.

cd /d "%~dp0\.."

echo [dev] Starting PrintFlow development stack...
echo.

start "PrintFlow Dashboard" cmd /c "uv run python -m dashboard --port 8000"
start "PrintFlow Agent 1"   cmd /c "uv run python -m agent --mock --port 8081"
start "PrintFlow Agent 2"   cmd /c "uv run python -m agent --mock --port 8082"
start "PrintFlow Agent 3"   cmd /c "uv run python -m agent --mock --port 8083"

echo [dev] Dashboard: http://localhost:8000
echo [dev] Agent 1:   http://localhost:8081
echo [dev] Agent 2:   http://localhost:8082
echo [dev] Agent 3:   http://localhost:8083
echo.
echo [dev] Register agents in the dashboard UI or via API:
echo   curl -X POST http://localhost:8000/api/printers -H "Content-Type: application/json" -d "{\"name\":\"Mock-1\",\"agent_url\":\"http://127.0.0.1:8081\"}"
echo.
echo [dev] Each process runs in its own window. Close them to stop.
