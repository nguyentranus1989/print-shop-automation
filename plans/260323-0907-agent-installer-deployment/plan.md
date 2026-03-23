---
title: "PrintFlow Agent Installer & Deployment Strategy"
description: "One-click Windows installer, service registration, auto-updates, code signing, and dashboard deployment for commercial PrintFlow product"
status: pending
priority: P1
effort: 12d
branch: N/A
tags: [installer, deployment, pyinstaller, inno-setup, nssm, windows-service, auto-update, code-signing]
created: 2026-03-23
---

# PrintFlow Agent Installer & Deployment Strategy

## Current State

- Agent: Python FastAPI app, runs via `uv run python -m agent.main --mock --port 8081`
- Dashboard: Python FastAPI app, runs via `python -m dashboard --port 8000 --agents "..."`
- Config: `agent.toml` read by `common.config.AgentConfig.load()` (TOML, Python 3.11+ stdlib)
- Monorepo: 3 packages (`common`, `agent`, `dashboard`) under `packages/`, managed by `uv` workspaces
- Target users: non-technical print shop operators on Windows 10/11

## Phase Overview

| # | Phase | Effort | Depends On |
|---|-------|--------|------------|
| 1 | Build Pipeline (PyInstaller + Inno Setup) | 3d | - |
| 2 | Dashboard Deployment | 2d | Phase 1 |
| 3 | Auto-Update Mechanism | 3d | Phase 1 |
| 4 | Code Signing & Distribution | 2d | Phase 1 |
| 5 | Installer Testing Strategy | 2d | All |

## Phase Status

- [ ] Phase 1 -- Build Pipeline (PyInstaller + Inno Setup)
- [ ] Phase 2 -- Dashboard Deployment
- [ ] Phase 3 -- Auto-Update Mechanism
- [ ] Phase 4 -- Code Signing & Distribution
- [ ] Phase 5 -- Installer Testing Strategy

## Key Dependencies

- Phase 1 must complete before any other phase (produces the .exe and installer)
- Phase 3 (updates) requires the installed agent from Phase 1
- Phase 4 (signing) should be applied to Phase 1 output before customer distribution
- Phase 5 validates all other phases

## Detailed Phase Files

- [Phase 1 -- Build Pipeline](./phase-01-build-pipeline-pyinstaller-inno-setup.md)
- [Phase 2 -- Dashboard Deployment](./phase-02-dashboard-deployment-strategy.md)
- [Phase 3 -- Auto-Update Mechanism](./phase-03-auto-update-mechanism.md)
- [Phase 4 -- Code Signing & Distribution](./phase-04-code-signing-and-distribution.md)
- [Phase 5 -- Installer Testing Strategy](./phase-05-installer-testing-strategy.md)

## File Structure (New Files)

```
print-shop-automation/
  installer/
    agent/
      pyinstaller-agent-spec.py          # PyInstaller .spec file for agent
      inno-setup-agent.iss               # Inno Setup script for agent installer
      nssm.exe                           # Bundled NSSM 2.24 (MIT, ~300KB)
      default-agent.toml                 # Template config for fresh installs
      printflow-logo.bmp                 # Installer wizard branding (164x314)
      printflow-icon.ico                 # App icon
      LICENSE.txt                        # EULA text
    dashboard/
      pyinstaller-dashboard-spec.py      # PyInstaller .spec for dashboard
      inno-setup-dashboard.iss           # Inno Setup script for dashboard installer
    shared/
      version-embed.py                   # Inject version into __init__.py at build time
  packages/
    agent/src/agent/
      updater.py                         # Update check, download, apply, rollback
      updater_service_control.py         # NSSM service stop/start via subprocess
      frozen_path_resolver.py            # sys.frozen-aware path resolution
    common/src/common/
      config.py                          # Modified: add update_url, auto_update fields
  scripts/
    build-agent-installer.sh             # End-to-end: uv sync -> PyInstaller -> Inno Setup
    build-dashboard-installer.sh         # Same for dashboard
```
