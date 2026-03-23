#!/bin/bash
# Start dashboard + 3 mock agents for local development.
# Run from the repo root: bash scripts/dev-start.sh
set -e

echo "[dev] Starting PrintFlow development stack..."

# Dashboard on :8000, mock agents on :8081-8083
uv run python -m dashboard --port 8000 &
DASH_PID=$!

uv run python -m agent --mock --port 8081 &
AGENT1_PID=$!

uv run python -m agent --mock --port 8082 &
AGENT2_PID=$!

uv run python -m agent --mock --port 8083 &
AGENT3_PID=$!

echo "[dev] Dashboard: http://localhost:8000"
echo "[dev] Agent 1:   http://localhost:8081"
echo "[dev] Agent 2:   http://localhost:8082"
echo "[dev] Agent 3:   http://localhost:8083"
echo ""
echo "[dev] Register agents in the dashboard UI or via API:"
echo "  curl -X POST http://localhost:8000/api/printers -H 'Content-Type: application/json' -d '{\"name\":\"Mock-1\",\"agent_url\":\"http://127.0.0.1:8081\"}'"
echo ""
echo "[dev] Press Ctrl+C to stop all."

# Wait for any child to exit and clean up all
trap "kill $DASH_PID $AGENT1_PID $AGENT2_PID $AGENT3_PID 2>/dev/null; exit" INT TERM
wait
