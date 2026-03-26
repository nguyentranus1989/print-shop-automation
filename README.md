# PrintFlow

Print shop automation — bridges PodFactory (order management) with DTG/DTF/UV printers via PrintExp. Supports auto-detection and DLL injection for seamless multi-printer workflows.

## Architecture

Three Python packages in a uv workspace:

| Package | Role | Runs on |
|---------|------|---------|
| `agent` | Headless service — polls orders, injects print jobs via TCP 9100, controls PrintExp | Each printer PC |
| `dashboard` | Web UI — order queue, printer status, analytics | Printer PC or central server |
| `common` | Shared models, config, protocols (HSRP, WM_COMMAND) | Imported by both |

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — `pip install uv` or `winget install astral-sh.uv`
- **Windows 10/11** (for agent — uses Win32 APIs via ctypes)

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd print-shop-automation
uv sync

# 2. Run tests
uv run pytest

# 3. Start dev stack (dashboard + 3 mock agents)
# Windows:
scripts\dev-start.bat
# Linux/macOS/Git Bash:
bash scripts/dev-start.sh

# 4. Open dashboard
# http://localhost:8000
```

## Configuration

Copy the example files and edit:

```bash
cp .env.example .env           # Dashboard config (port, DB path, API keys)
cp agent.toml.example agent.toml  # Agent config (printer type, PrintExp path, ports)
```

### .env (Dashboard)

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_HOST` | `0.0.0.0` | Bind address |
| `DASHBOARD_PORT` | `8000` | HTTP port |
| `DASHBOARD_DB_PATH` | `printflow.db` | SQLite database path |
| `PODFACTORY_API_KEY` | — | PodFactory API key |
| `PODFACTORY_MONGO_URI` | — | PodFactory MongoDB connection |

### agent.toml (Agent)

See `agent.toml.example` for all options. Key settings:

- `printer.type` — `auto` (detects DTG/DTF/UV), `dtg`, `dtf`, or `uv`
- `printexp.exe_path` — Path to PrintExp.exe
- `printexp.tcp_port` — Raw print port (default: 9100)
- `network.port` — Agent HTTP API port (default: 8080)

Agent auto-detects printer type and uses appropriate memory injection backend. See [docs/printer-backend-integration.md](docs/printer-backend-integration.md) for technical details.

## Running

### Development Mode

```bash
# Dashboard only
uv run python -m dashboard --port 8000

# Agent in mock mode (no printer required)
uv run python -m agent --mock --port 8081

# Agent with real printer
uv run python -m agent --printer-type dtg --port 8080
```

### Production (.exe)

```bash
# Build standalone executables
scripts\build-agent.bat
scripts\build-dashboard.bat

# Run agent .exe
scripts\run-agent.bat --mock --port 8081

# Install agent as Windows service
scripts\install-service.bat
```

## Testing

```bash
# All tests
uv run pytest

# Verbose with coverage
uv run pytest -v --tb=short

# Specific package
uv run pytest tests/test_common/
uv run pytest tests/test_agent/
```

### Hardware Testing

On a PC with PrintExp running:

```bash
python scripts/printer-test.py              # Full diagnostic
python scripts/printer-test.py --inject C:\path\to\file.prn  # Test TCP 9100
python scripts/printer-test.py --move left  # Test axis movement
```

## Project Structure

```
print-shop-automation/
├── packages/
│   ├── agent/          # Printer agent service
│   ├── dashboard/      # Web dashboard (FastAPI + HTMX)
│   └── common/         # Shared models and protocols
├── scripts/
│   ├── dev-start.bat   # Start dev stack (Windows)
│   ├── dev-start.sh    # Start dev stack (bash)
│   ├── build-agent.bat
│   ├── build-dashboard.bat
│   ├── install-service.bat
│   ├── uninstall-service.bat
│   └── printer-test.py # Hardware diagnostic
├── tests/
├── docs/               # Technical documentation
├── plans/              # Implementation plans
├── .env.example
├── agent.toml.example
└── pyproject.toml      # Root workspace config
```

## Tech Stack

Python 3.11+ · FastAPI · HTMX · SQLite · Jinja2 · uv workspaces · PyInstaller

See [docs/tech-stack.md](docs/tech-stack.md) for detailed rationale.
