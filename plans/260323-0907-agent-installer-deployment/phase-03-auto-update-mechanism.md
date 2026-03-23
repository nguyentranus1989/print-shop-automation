# Phase 3 -- Auto-Update Mechanism

## Context Links
- Agent main: `packages/agent/src/agent/main.py`
- Agent API: `packages/agent/src/agent/api.py`
- Existing update plan: `plans/260323-printflow-commercialization/phase-06-update-mechanism.md`
- Agent config: `packages/common/src/common/config.py`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Agent checks for updates on startup and every 24h, downloads new binary, waits for idle state, swaps binary, restarts service via NSSM, rolls back if health check fails.

## Key Insights

1. **NSSM makes this straightforward**: The agent doesn't need to restart itself. It signals NSSM to stop the service, replaces the binary, then a separate helper script (or NSSM's own restart) starts the new version. Alternatively, the agent can write a "pending update" flag and exit -- NSSM will restart it, and on startup it applies the pending update.

2. **`--onedir` mode helps updates**: With `--onedir`, the main .exe is small (~5-10MB). Only the .exe needs replacing for most updates. The `_internal/` folder (Python runtime) rarely changes. Full updates replace everything; patch updates replace only the .exe.

3. **Two update approaches considered**:
   - **Approach A (Recommended)**: Agent downloads update to temp, writes `update-pending.json`, exits cleanly. NSSM restarts it. On startup, agent detects `update-pending.json`, applies the swap, deletes the flag, continues normally.
   - **Approach B**: Agent spawns a helper process that waits for agent to stop, swaps binary, then starts service. More complex, race conditions possible.

   Approach A is simpler and avoids process coordination issues.

4. **Update server can be minimal**: A static file host (S3 bucket, GitHub Releases, or self-hosted nginx) serving `latest.json` + versioned .exe files. No custom backend needed initially.

## Requirements

### Functional
- Agent checks `{update_url}?current={version}&os=win64` on startup + every 24h
- Update check is non-blocking background task
- If newer version available:
  1. Download new .exe to `{install_dir}\updates\printflow-agent-{version}.exe`
  2. Verify SHA-256 checksum
  3. Wait for idle state (no active print job, checked via `backend.get_status().printing`)
  4. Write `{install_dir}\update-pending.json` with new version info
  5. Exit cleanly (NSSM restarts)
  6. On restart, detect pending update, apply swap, continue startup
- Rollback: if health check fails within 30s of restart, restore `.bak` binary
- Manual trigger: `POST /update/check` and `POST /update/apply`
- Config: `auto_update = true/false`, `update_url`, `update_check_interval_hours`
- Dashboard notification: agent reports update status via `/status` endpoint

### Non-Functional
- Download with retry (3 attempts, exponential backoff)
- Resume partial downloads (HTTP Range header)
- Max idle wait: 2 hours, then notify dashboard "update pending, printer busy"
- Update check should use < 1KB bandwidth when no update available
- Must work behind corporate proxy (respect `HTTP_PROXY` env var)

## Architecture

### Update Server (Static Hosting)

```
https://updates.printflow.com/
  agent/
    latest.json                    # Current latest version metadata
    printflow-agent-1.0.0.exe      # Version binaries
    printflow-agent-1.0.1.exe
    printflow-agent-1.1.0.exe

latest.json format:
{
  "version": "1.1.0",
  "url": "https://updates.printflow.com/agent/printflow-agent-1.1.0.exe",
  "sha256": "abc123...",
  "size_bytes": 35000000,
  "release_notes": "Bug fixes and performance improvements",
  "min_version": "0.9.0",
  "released_at": "2026-04-01T12:00:00Z"
}
```

**Hosting options (cheapest first)**:
1. GitHub Releases (free, unlimited bandwidth for public repos)
2. Cloudflare R2 (free egress, $0.015/GB storage)
3. AWS S3 + CloudFront (~$0.085/GB egress)
4. Self-hosted nginx on VPS ($5/mo)

**Recommendation**: GitHub Releases for MVP. Free, versioned, has API for latest release. Switch to R2/S3 when volume justifies.

### Update Flow (Agent Side)

```
STARTUP
=======
1. Check for update-pending.json
   YES -> Apply pending update:
          a. Rename current .exe -> .exe.bak
          b. Move downloaded .exe -> current
          c. Delete update-pending.json
          d. Verify: run --version on new exe (subprocess)
          e. If verify fails: rollback (.bak -> current), log error
          f. Continue normal startup
   NO  -> Continue normal startup

2. Start background update checker (asyncio task)


BACKGROUND CHECK (every 24h)
=============================
1. GET {update_url}?current={version}
2. Compare semver: response.version > current_version?
   NO  -> Log "up to date", sleep 24h, repeat
   YES -> Continue

3. Download to {install_dir}\updates\{filename}
   - Use httpx with streaming
   - Verify SHA-256 after download
   - If download fails: retry 3x, then give up until next check

4. Wait for idle:
   while backend.get_status().printing:
       sleep 5 minutes
       if waited > 2 hours:
           log warning "update pending, printer busy"
           continue waiting (don't give up)

5. Write update-pending.json:
   {
     "version": "1.1.0",
     "exe_path": "updates/printflow-agent-1.1.0.exe",
     "sha256": "abc123...",
     "downloaded_at": "2026-04-01T14:30:00Z"
   }

6. Exit with code 0 (NSSM restarts -> goes to STARTUP step 1)


ROLLBACK (if new version fails)
================================
On startup after update, if health check fails within 30s:
  1. Stop (crash)
  2. NSSM restarts
  3. On restart, detect .exe.bak exists
  4. Restore: .exe.bak -> .exe
  5. Delete failed update binary
  6. Write update-failed.json with error details
  7. Continue with old version
  8. Report failure to dashboard
```

## Related Code Files

### Create
| File | Purpose |
|------|---------|
| `packages/agent/src/agent/updater.py` | Core update logic: check, download, verify, apply, rollback |
| `packages/agent/src/agent/updater_service_control.py` | NSSM service control via subprocess |

### Modify
| File | Change |
|------|--------|
| `packages/agent/src/agent/main.py` | Startup: check for pending update; start background update task |
| `packages/agent/src/agent/api.py` | Add `GET /version`, `GET /update/status`, `POST /update/check`, `POST /update/apply` |
| `packages/common/src/common/config.py` | Add `auto_update`, `update_url`, `update_check_interval_hours` fields |

## Implementation Steps

### Step 1: Config Fields

Add to `AgentConfig`:
```python
auto_update: bool = True
update_url: str = "https://updates.printflow.com/agent/latest.json"
update_check_interval_hours: int = 24
```

Add to `agent.toml` sections:
```toml
[updates]
auto_update = true
update_url = "https://updates.printflow.com/agent/latest.json"
check_interval_hours = 24
```

### Step 2: Updater Module

`packages/agent/src/agent/updater.py` -- core functions:

```python
@dataclass
class UpdateInfo:
    version: str
    url: str
    sha256: str
    size_bytes: int
    release_notes: str

async def check_for_update(current_version: str, update_url: str) -> UpdateInfo | None:
    """GET latest.json, compare semver, return UpdateInfo if newer."""

async def download_update(info: UpdateInfo, dest_dir: Path) -> Path:
    """Stream download with SHA-256 verification. Returns path to downloaded file."""

def apply_pending_update(install_dir: Path) -> bool:
    """Called on startup. Reads update-pending.json, swaps binaries. Returns True on success."""

def rollback_update(install_dir: Path) -> bool:
    """Restore .exe.bak if update failed."""

def write_pending_marker(install_dir: Path, info: UpdateInfo, exe_path: Path) -> None:
    """Write update-pending.json."""

async def background_update_loop(config: AgentConfig, backend: PrinterBackend) -> None:
    """Long-running async task: check -> download -> wait idle -> write pending -> exit."""
```

### Step 3: Version Comparison

Use `packaging.version.Version` for proper semver comparison (already available as a pip dependency of most packages). Or use a minimal inline comparator:

```python
def version_is_newer(current: str, available: str) -> bool:
    """Compare semantic versions. Returns True if available > current."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    return parse(available) > parse(current)
```

### Step 4: API Endpoints

Add to `api.py`:

```python
@app.get("/version")
def get_version():
    from agent import __version__
    return {"version": __version__.__version__, "service": "printflow-agent"}

@app.get("/update/status")
async def update_status():
    """Return current update state: up-to-date, available, downloading, pending-restart."""

@app.post("/update/check")
async def force_update_check():
    """Trigger an immediate update check."""

@app.post("/update/apply")
async def force_update_apply():
    """Force-apply a downloaded update (skip idle wait)."""
```

### Step 5: Startup Integration

In `main.py`, before starting uvicorn:

```python
# 1. Check for pending update (synchronous, before server starts)
from agent.updater import apply_pending_update
from agent.frozen_path_resolver import get_install_dir

if getattr(sys, "frozen", False):
    applied = apply_pending_update(get_install_dir())
    if applied:
        print(f"[agent] Update applied successfully", flush=True)

# 2. Start background update checker (after server is running)
# In lifespan or as asyncio.create_task after uvicorn starts
```

### Step 6: Idle Wait Logic

```python
async def wait_for_idle(backend: PrinterBackend, timeout_hours: float = 2.0) -> bool:
    """Wait until printer is not actively printing. Returns True if idle achieved."""
    start = time.monotonic()
    while True:
        status = await backend.get_status()
        if not status.printing:
            return True
        elapsed_hours = (time.monotonic() - start) / 3600
        if elapsed_hours > timeout_hours:
            # Don't give up -- just log warning and keep waiting
            logging.warning("Update pending for %.1f hours, printer still busy", elapsed_hours)
        await asyncio.sleep(300)  # Check every 5 minutes
```

### Step 7: Update Server Setup (GitHub Releases)

For MVP, use GitHub Releases:

```bash
# Build and upload
scripts/build-agent-installer.sh 1.1.0
sha256sum dist/printflow-agent/printflow-agent.exe > dist/printflow-agent.sha256

# Create GitHub release
gh release create v1.1.0 \
  dist/printflow-agent/printflow-agent.exe \
  --title "PrintFlow Agent v1.1.0" \
  --notes "Bug fixes and performance improvements"
```

Agent checks GitHub Releases API:
```
GET https://api.github.com/repos/yourorg/printflow-releases/releases/latest
```

Or host a simple `latest.json` in the release assets.

## Todo List

- [ ] Add update config fields to `AgentConfig`
- [ ] Create `updater.py` with check/download/apply/rollback functions
- [ ] Implement semver comparison
- [ ] Implement SHA-256 verification
- [ ] Implement download with retry + resume
- [ ] Implement idle-wait logic
- [ ] Implement `update-pending.json` marker mechanism
- [ ] Implement startup pending-update detection + swap
- [ ] Implement rollback on failed startup
- [ ] Add `/version`, `/update/status`, `/update/check`, `/update/apply` API endpoints
- [ ] Start background update loop in main.py lifespan
- [ ] Set up update server (GitHub Releases or static host)
- [ ] Upload test update and verify end-to-end flow
- [ ] Test rollback scenario (corrupt binary)
- [ ] Test update while printer is busy (idle wait)

## Success Criteria

- Agent detects new version within 24h of release
- Update downloads and applies without human intervention
- No print jobs interrupted by updates
- Failed update rolls back automatically within 60s
- Manual trigger (`POST /update/check`) works for impatient admins
- Agent reports its version via `GET /version`
- Works behind corporate proxy (HTTP_PROXY respected)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Update corrupts binary | Agent down permanently | SHA-256 verification + .bak rollback |
| Update during active print | Lost print job, wasted garment | Idle-wait with 5-min polling; never force |
| NSSM doesn't restart after exit | Agent stays down | Test NSSM restart behavior; set AppRestartDelay=5000 |
| GitHub rate limiting (60 req/hr unauthenticated) | Update checks fail | Cache last check result; check only every 24h; use auth token if needed |
| Partial download on flaky WiFi | Corrupt file applied | SHA-256 check rejects partial downloads; retry 3x |
| Antivirus quarantines downloaded .exe | Update stuck | Code signing (Phase 4); pre-signed update binaries |

## Security Considerations

- Downloaded binaries verified by SHA-256 checksum from update server
- Update server should use HTTPS (GitHub Releases does by default)
- Future: sign update binaries with code signing cert; verify signature before apply
- `update-pending.json` written to install dir (requires admin/service ACLs)
- No remote code execution: only pre-built .exe binaries are downloaded and swapped
