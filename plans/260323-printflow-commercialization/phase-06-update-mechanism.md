# Phase 6 — Self-Hosted Update Mechanism

## Context Links
- Agent main: `packages/agent/src/agent/main.py`
- Phase 5 (prerequisite): `./phase-05-agent-installer.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Agent checks for updates, downloads new binary, restarts service. Dashboard (if self-hosted) has similar mechanism. Must not interrupt active print jobs.

## Key Insights

Agent runs as a Windows service via NSSM. Update = download new .exe, stop service, replace binary, start service. NSSM handles the restart.

**Critical constraint**: never interrupt a printing job. Agent must check if a job is active before applying update.

**Simplest approach**: check a version endpoint on your update server, compare semver, download if newer, apply on next idle window.

## Requirements

### Functional
- Agent checks `https://updates.printflow.com/api/agent/latest?current=1.0.0` daily
- If newer version: download `.exe` to temp dir, verify checksum
- Wait for idle state (no active print job)
- Replace binary: rename current → `.bak`, move new → current
- Restart service via NSSM
- If restart fails: rollback (rename `.bak` back)
- Dashboard notification: "Update available" / "Update applied, restarting"
- Manual trigger: `POST /api/agent/update` to force check + apply
- Config option: `auto_update = true/false` (default: true)

### Non-Functional
- Update check is non-blocking (background task)
- Download with resume support (partial downloads on flaky connections)
- Integrity verification: SHA-256 checksum
- Rollback on failure: agent always recoverable
- Update server can be self-hosted (for air-gapped environments)

## Architecture

```
Update check (daily or manual):
  1. GET https://updates.printflow.com/api/agent/latest
     Response: {version: "1.1.0", url: "https://...exe", sha256: "abc...", release_notes: "..."}
  2. Compare with current version
  3. If newer:
     a. Download to %TEMP%\printflow-agent-1.1.0.exe
     b. Verify SHA-256
     c. Wait for idle (no active job)
     d. Stop service (NSSM)
     e. Rename current .exe → .exe.bak
     f. Move downloaded → current
     g. Start service (NSSM)
     h. Verify health check passes
     i. Delete .bak
  4. If health check fails after restart:
     a. Stop service
     b. Restore .bak
     c. Start service
     d. Report update failure
```

## Related Code Files

### Create
- `packages/agent/src/agent/updater.py` — update check, download, apply logic
- `packages/agent/src/agent/updater_service_control.py` — NSSM service stop/start via subprocess

### Modify
- `packages/agent/src/agent/main.py` — start update checker as background task
- `packages/agent/src/agent/api.py` — add `GET /version`, `POST /update` endpoints
- `packages/common/src/common/config.py` — add `auto_update`, `update_url` config fields

## Implementation Steps

1. **Version endpoint on agent**
   - `GET /version` → `{version: "1.0.0", build_date: "...", python: "3.12"}`
   - Version embedded at build time via PyInstaller

2. **Update checker** (`agent/updater.py`)
   - `check_for_update(current_version, update_url) -> UpdateInfo | None`
   - `download_update(url, dest_path, expected_sha256) -> bool`
   - `apply_update(new_exe_path, current_exe_path) -> bool`
   - `rollback_update(current_exe_path) -> bool`

3. **Service control** (`agent/updater_service_control.py`)
   - `stop_service(service_name="PrintFlowAgent") -> bool` — subprocess call to `nssm stop`
   - `start_service(service_name="PrintFlowAgent") -> bool` — subprocess call to `nssm start`
   - `is_service_running(service_name) -> bool`

4. **Idle wait logic**
   - Before applying: check `backend.get_status().printing`
   - If printing: schedule retry in 5 minutes
   - Max wait: 2 hours, then notify admin "update pending, printer busy"

5. **Background update task**
   - `asyncio.create_task` in lifespan startup
   - Check daily (configurable interval)
   - Download in background, don't block API
   - Apply only when idle

6. **Manual trigger**
   - `POST /api/agent/update` — force check + apply
   - Returns: `{update_available: true, version: "1.1.0", status: "downloading/applying/up-to-date"}`

7. **Dashboard self-update** (simpler)
   - Dashboard admin page: "Check for updates" button
   - Shows current vs available version
   - For self-hosted: same mechanism (download, replace, restart uvicorn)
   - For cloud-hosted: managed by ops team (not user-facing)

## Todo List

- [ ] Create `agent/updater.py` — check, download, apply, rollback
- [ ] Create `agent/updater_service_control.py` — NSSM subprocess calls
- [ ] Add `GET /version` endpoint
- [ ] Add `POST /api/agent/update` endpoint
- [ ] Background update task in agent startup
- [ ] Idle wait before applying update
- [ ] SHA-256 verification of downloaded binary
- [ ] Rollback on failed restart
- [ ] Config: `auto_update`, `update_url` fields
- [ ] Dashboard: update notification banner
- [ ] Tests: version comparison logic
- [ ] Tests: rollback on failure

## Success Criteria

- Agent detects new version within 24h of release
- Update applies without interrupting active print
- Failed update automatically rolls back
- Manual trigger works for impatient admins
- Air-gapped shops can point `update_url` to local server

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Update corrupts agent binary | Agent down | SHA-256 check + .bak rollback |
| Update during print job | Lost print job | Idle-wait with 2h timeout |
| NSSM service restart fails | Agent stuck | Rollback + admin notification |
| Network timeout during download | Partial file | Resume support, retry 3x, temp file cleanup |
| Antivirus quarantines new binary | Update blocked | Code signing (same cert as installer) |
