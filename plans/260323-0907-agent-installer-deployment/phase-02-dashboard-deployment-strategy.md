# Phase 2 -- Dashboard Deployment Strategy

## Context Links
- Dashboard main: `packages/dashboard/src/dashboard/main.py`
- Dashboard pyproject: `packages/dashboard/pyproject.toml`
- Agent installer phase: `./phase-01-build-pipeline-pyinstaller-inno-setup.md`
- Commercial landscape: `docs/research-commercial-landscape.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Define how the dashboard component is deployed for different customer scenarios: self-hosted (on-prem), manual install (first customers), and future cloud-hosted.

## Key Insights

1. **Dashboard is simpler than agent** -- no Win32 integration, no service registration needed for first iteration. It's a standard FastAPI web app.

2. **Three deployment tiers** (phased rollout):
   - **Tier 1 (Now)**: Manual install by PrintFlow team for first 3-5 customers
   - **Tier 2 (MVP)**: Self-hosted installer (same pattern as agent, but dashboard-specific)
   - **Tier 3 (v2)**: Cloud-hosted SaaS option

3. **Dashboard runs on any machine on the LAN** -- doesn't have to be a printer PC. Could be an office PC, a NAS, or cloud server. This is different from the agent which must run on the printer PC.

4. **SQLite is fine for single-shop self-hosted**. For cloud-hosted multi-tenant (Tier 3), PostgreSQL migration will be needed (separate plan in Phase 8 of commercialization).

## Requirements

### Tier 1: Manual Install (First Customers)

- PrintFlow team SSHs/TeamViewers into customer machine
- Installs Python 3.11+ and uv
- Clones repo or copies wheel files
- Runs `uv run python -m dashboard --port 8000 --agents "..."`
- Sets up as Windows service via NSSM manually
- Timeline: now, no dev work needed

### Tier 2: Self-Hosted Installer (MVP)

- Same pattern as agent installer: PyInstaller + Inno Setup
- Wizard collects: port, admin password (for Phase 7 RBAC)
- Installs to `C:\Program Files\PrintFlow Dashboard\`
- Registers `PrintFlowDashboard` Windows service via NSSM
- Creates `dashboard.toml` config
- Agent discovery: manual entry of agent IPs in wizard, or auto-discovery later (Phase 10 mDNS)

### Tier 3: Cloud-Hosted (v2, Future)

- SaaS option: `https://app.printflow.com`
- PostgreSQL database
- Multi-tenant with shop_id isolation
- Agents connect outbound to cloud dashboard (reverse connection)
- Requires Phase 4 (multi-shop isolation) and Phase 8 (cloud mode) from commercialization plan

## Architecture

### Tier 1: Manual Install (current)

```
Customer LAN
+-------------------+     +-----------------------+
| Printer PC #1     |     | Office PC / Any PC    |
| Agent :8080       |<--->| Dashboard :8000       |
+-------------------+     | (Python + uv)         |
                          +-----------------------+
+-------------------+            ^
| Printer PC #2     |            |
| Agent :8080       |<-----------+
+-------------------+
```

Setup: TeamViewer session, install Python+uv, copy code, run via NSSM.
Time per customer: ~30 minutes.
Viable for first 3-5 customers.

### Tier 2: Self-Hosted Installer

```
Same topology, but dashboard installed via:
  PrintFlowDashboardSetup-1.0.0.exe

Wizard pages:
  1. Welcome
  2. License Agreement
  3. Config:
     - HTTP port (default: 8000)
     - Agent URLs (comma-separated)
     - Admin password
  4. Install directory
  5. Finish (start service, open browser)

Installed to: C:\Program Files\PrintFlow Dashboard\
Service: PrintFlowDashboard (via NSSM)
```

### Tier 2 Alternative: ZIP + run.bat

Simpler alternative to a full installer for dashboard (since dashboard doesn't need Win32):

```
PrintFlowDashboard-1.0.0.zip
  printflow-dashboard.exe
  _internal/
  dashboard.toml.example
  start-dashboard.bat        # Convenience script
  install-service.bat        # NSSM setup (run as admin)
  uninstall-service.bat      # NSSM teardown
  nssm.exe
```

**Recommendation**: Start with ZIP + scripts for dashboard (Tier 2a), build full Inno Setup installer only if customer feedback demands it (Tier 2b). Agent installer is higher priority because it must run unattended on printer PCs.

## Related Code Files

### Create (Tier 2 -- ZIP approach first)
| File | Purpose |
|------|---------|
| `installer/dashboard/pyinstaller-dashboard-spec.py` | PyInstaller spec for dashboard |
| `installer/dashboard/dashboard.toml.example` | Template config |
| `installer/dashboard/install-service.bat` | NSSM service registration |
| `installer/dashboard/uninstall-service.bat` | NSSM service removal |
| `installer/dashboard/start-dashboard.bat` | Manual start without service |
| `scripts/build-dashboard-package.sh` | Build script (PyInstaller only, no Inno Setup) |

### Create (Tier 2b -- Full installer, if needed later)
| File | Purpose |
|------|---------|
| `installer/dashboard/inno-setup-dashboard.iss` | Full installer wizard |

### Modify
| File | Change |
|------|--------|
| `packages/dashboard/src/dashboard/main.py` | Frozen path resolution; TOML config support (currently uses CLI args + env vars only) |

## Implementation Steps

### Step 1: Dashboard TOML Config Support

Dashboard currently uses CLI args and env vars. Add `dashboard.toml` support parallel to agent:

```toml
[dashboard]
port = 8000
host = "0.0.0.0"

[agents]
urls = [
  "http://192.168.1.101:8080",
  "http://192.168.1.102:8080",
]

[database]
path = "printflow.db"
```

### Step 2: PyInstaller Spec for Dashboard

Similar to agent spec but include:
- Jinja2 templates directory as data files
- Static assets (CSS, JS, images) as data files
- SQLAlchemy + Alembic migrations as data files

```python
datas=[
    ("../../packages/dashboard/src/dashboard/templates", "dashboard/templates"),
    ("../../packages/dashboard/src/dashboard/static", "dashboard/static"),
],
```

This is the main difference from agent -- dashboard has template/static files that must be bundled.

### Step 3: Build Script

```bash
#!/bin/bash
# scripts/build-dashboard-package.sh
set -euo pipefail
VERSION="${1:-0.1.0}"

python installer/shared/version-embed.py "$VERSION" dashboard
uv sync
uv run pyinstaller installer/dashboard/pyinstaller-dashboard-spec.py --clean -y

# Assemble ZIP
mkdir -p dist/printflow-dashboard-package
cp -r dist/printflow-dashboard/* dist/printflow-dashboard-package/
cp installer/agent/nssm.exe dist/printflow-dashboard-package/    # Reuse same NSSM
cp installer/dashboard/dashboard.toml.example dist/printflow-dashboard-package/
cp installer/dashboard/install-service.bat dist/printflow-dashboard-package/
cp installer/dashboard/uninstall-service.bat dist/printflow-dashboard-package/
cp installer/dashboard/start-dashboard.bat dist/printflow-dashboard-package/

cd dist && zip -r "PrintFlowDashboard-${VERSION}.zip" printflow-dashboard-package/
echo "[build] Done: dist/PrintFlowDashboard-${VERSION}.zip"
```

### Step 4: Service Scripts (BAT files)

`install-service.bat`:
```batch
@echo off
echo Installing PrintFlow Dashboard as Windows service...
echo This requires Administrator privileges.
net session >nul 2>&1 || (echo ERROR: Run as Administrator & pause & exit /b 1)

set INSTALLDIR=%~dp0
"%INSTALLDIR%nssm.exe" install PrintFlowDashboard "%INSTALLDIR%printflow-dashboard.exe" --config "%INSTALLDIR%dashboard.toml"
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard AppDirectory "%INSTALLDIR%"
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard AppStdout "%INSTALLDIR%logs\stdout.log"
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard AppStderr "%INSTALLDIR%logs\stderr.log"
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard AppRotateFiles 1
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard AppRotateBytes 10485760
"%INSTALLDIR%nssm.exe" set PrintFlowDashboard Start SERVICE_AUTO_START
"%INSTALLDIR%nssm.exe" start PrintFlowDashboard

echo Done. Dashboard service is running.
echo Open http://localhost:8000 in your browser.
pause
```

`uninstall-service.bat`:
```batch
@echo off
echo Removing PrintFlow Dashboard service...
net session >nul 2>&1 || (echo ERROR: Run as Administrator & pause & exit /b 1)
"%~dp0nssm.exe" stop PrintFlowDashboard
"%~dp0nssm.exe" remove PrintFlowDashboard confirm
echo Done. Service removed.
pause
```

## Todo List

- [ ] Add `dashboard.toml` config loading to `dashboard/main.py`
- [ ] Create PyInstaller spec for dashboard (with templates/static data)
- [ ] Test dashboard .exe standalone
- [ ] Create `install-service.bat` / `uninstall-service.bat` / `start-dashboard.bat`
- [ ] Create `dashboard.toml.example`
- [ ] Create `build-dashboard-package.sh`
- [ ] Build and test ZIP package on clean Windows
- [ ] Document Tier 1 manual install steps for first customers

## Success Criteria

- **Tier 1**: Can manually install dashboard on customer PC in < 30 minutes
- **Tier 2**: Customer can unzip, edit `dashboard.toml`, run `install-service.bat`, and dashboard works
- Dashboard .exe includes templates and static assets (no missing files)
- Service auto-starts on boot, restarts on crash

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Jinja2 templates not bundled correctly by PyInstaller | Dashboard serves blank pages | Explicit `datas=` in spec; test before shipping |
| Static files (CSS/JS) missing from bundle | Broken UI | Same; add to `datas` list; verify with `--onedir` output |
| ZIP approach too complex for non-technical users | Poor adoption | Graduate to Inno Setup installer if feedback demands it |
| Dashboard and agent version mismatch | API incompatibility | Version check on agent registration; warn on mismatch |

## Security Considerations

- Dashboard admin password set during install (or on first login for ZIP approach)
- dashboard.toml should not be world-readable (ACLs set by install script)
- SQLite database file in install dir, same ACL restrictions
- No secrets in the ZIP; credentials entered post-install
