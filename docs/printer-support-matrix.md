# PrintFlow Printer Support Matrix

> Complete feature and integration status for all 4 target PrintExp builds.

---

## Executive Summary

PrintFlow supports **four PrintExp builds** spanning two architectures and three integration methods. Feature coverage varies by build; not all printers support all controls (pause/cancel/movement). Print History and analytics are available via StatisticData.db on UV and DTF v5.8.2+.

---

## 4 Target Builds

| Build | Arch | Version | Integration | Status | Added |
|-------|------|---------|-------------|--------|-------|
| **DTG MULTIWS** | x86 (32-bit) | v5.7.7.1.12 | TCP 9100 + WriteProcessMemory | ✅ WORKING | Phase 0 |
| **DTF Standard** | x64 (64-bit) | v5.7.6.5.103 | DLL injection (vtable[7]) | ✅ WORKING | 2026-03-20 |
| **DTF Unicode** | x64 (64-bit) | v5.8.2.1.32 | DLL injection (TBD offsets) | 🚧 TODO | 2026-03-26 |
| **UV Professional** | x64 (64-bit) | v5.7.9.4.5008 | DLL injection (vtable[9]) | ✅ WORKING | 2026-03-26 |

---

## Feature Comparison

### Job Queue Management

| Feature | DTG | DTF v5.7.6 | DTF v5.8.2 | UV |
|---------|-----|-----------|-----------|-----|
| TCP 9100 injection | ✅ | ✅ | ✅ | ✅ |
| Filename display | 🟡 (memory patch) | ✅ (DLL) | ❓ (TBD) | ✅ (DLL) |
| Job persistence | N/A | N/A | ✅ (TSKF) | N/A |
| Statistics DB | ❌ | ❌ | ✅ (first run) | ✅ |
| Print History | ❌ | ❌ | ✅ (via DB) | ✅ (via DB) |

### Job Control (WM_COMMAND IDs)

| Feature | DTG | DTF | UV |
|---------|-----|-----|-----|
| Print/Go | ID: TBD | ID: TBD | ID: TBD |
| Pause | ID: TBD | ID: TBD | ID: TBD |
| Resume | ID: TBD | ID: TBD | ID: TBD |
| Cancel | ID: TBD | ID: TBD | ID: TBD |

**Status:** Stubs identified but **NOT wired** in any build. Requires per-version offset discovery or UI automation mapping.

### Print Settings

| Setting | DTG | DTF v5.7.6 | DTF v5.8.2 | UV |
|---------|-----|-----------|-----------|-----|
| Speed (via INI) | ❌ | ❌ | ❌ | ✅ (DebugParam.ini) |
| Direction (via INI) | ❌ | ❌ | ❌ | ✅ (DebugParam.ini) |
| Mirror (via INI) | ❌ | ❌ | ❌ | ✅ (DebugParam.ini) |
| White/Varnish | ❌ | ❓ (CraftFlow) | ❓ (CraftFlow) | 🚧 (CraftFlow deep scan) |

---

## Hardware Architecture

### DTG (v5.7.7.1.12 MULTIWS)

**Architecture:** x86 (32-bit) — requires WriteProcessMemory approach.

**Key differences:**
- Global pointer: Memory offset (no Ghidra reverse-engineering)
- No TaskMgr.dll — uses HSCD.dll instead
- MULTIWS = 2 independent workstations (WS:0 left, WS:1 right)
- NOT simultaneous printing; printer selects one WS per job
- No DLL injection (x86 architecture constraint)

**Status:** Production. All documented in DTG_automation memory patch investigation.

---

### DTF v5.7.6 (x64)

**Architecture:** x64 — full DLL injection support via vtable[7].

**Key facts:**
- Global pointer: `EXE+0x176B98`
- CTaskManager: via app vtable index 22
- AddFile vtable: Index 7
- File vector offset: `+0x28`
- Display vector offset: `+0x48`
- CTaskInfo size: 0xB08 bytes
- Filename field at: `+0x5B0`

**Status:** Production (2026-03-20). DLL compiled and tested. Reference implementation available in DTG_automation.

---

### DTF v5.8.2 Unicode (x64)

**Architecture:** x64 — DLL injection method same as v5.7.6, but **offsets differ**.

**Discovery status:** NOT YET DONE

**Next steps:**
1. Run memory scanner on v5.8.2 executable
2. Identify global pointer, vtable indices
3. Compute offset table (estimate: 5% variance from v5.7.6)
4. Compile and test DLL injection
5. Create v5.8.2-specific injection DLL

**Expected timeline:** 1-2 days (once offsets discovered)

**Note:** Creates StatisticData.db on first run. Print History will be available after running the printer once.

---

### UV v5.7.9.4.5008 (x64)

**Architecture:** x64 — full DLL injection support via vtable[9].

**Key facts:**
- Global pointer: `EXE+0x1D2F10`
- CTaskManager: device_obj at `+0x70`
- AddFile vtable: Index 9
- File vector offset: `+0x08`
- Display vector offset: `+0x28`
- CTaskInfo size: 0xCA0 bytes
- Filename field at: `+0x140`
- **CRITICAL:** Do NOT copy to print vector (causes R6025 crash)

**Status:** Production (2026-03-26). DLL compiled, tested on actual hardware. Full offset table documented.

**Print settings:** Direction, mirror, speed via DebugParam.ini (agent reads/writes).

**Statistics:** StatisticData.db populated after each print job (available for Print History UI).

---

## New Features (2026-03-26)

### 1. Print History Page (Dashboard)

**Location:** `packages/dashboard/templates/reports.html`

**Data source:** StatisticData.db (UV + DTF v5.8.2 only)

**Endpoint:** Agent `/reports/jobs` (queries past N days of print history)

**Fields:**
- Job name / filename
- Timestamp (start/end)
- Status (completed/failed/cancelled)
- Ink/dye usage
- Total print time

### 2. Agent `/reports/*` Endpoints

**Base path:** `/api/reports/`

**Endpoints:**
- `GET /api/reports/jobs` — List jobs (filterable by date range, status)
- `GET /api/reports/statistics` — Aggregate metrics (jobs/day, avg print time)
- `GET /api/reports/usage` — Ink/dye consumption (if available in DB)

**Database:** Queries StatisticData.db (local to printer PC)

**Availability:** DTG (❌), DTF v5.7.6 (❌), DTF v5.8.2 (✅), UV (✅)

### 3. UV Print Settings

**INI file:** `DebugParam.ini` (PrintExp data folder)

**Agent control:**
```toml
[uv.settings]
speed = 3  # 1=slow, 2=normal, 3=fast
direction = 0  # 0=right-to-left, 1=left-to-right
mirror = false
```

**Implementation:** Agent reads INI on startup, writes changes before job submission.

### 4. TSKF Format Writer

**Purpose:** Job persistence (DTF v5.8.2, UV future)

**Format:** Binary task file format (TSKF = Task Format)

**Agent support:** Serializes print job metadata to TSKF for recovery on restart.

### 5. Job Report CLI Tool

**Script:** `scripts/job-report.py`

**Usage:**
```bash
python scripts/job-report.py --printer=uv --days=7
python scripts/job-report.py --printer=dtf --since="2026-03-20"
```

**Output:** CSV or JSON with job history, status, timings.

---

## Feature Gaps & TODOs

### 1. DTF v5.8.2 Offset Discovery ❌

**Blocker:** Memory offsets not yet identified.

**Work required:**
- Run Python memory scanner on v5.8.2 executable
- Identify global pointer (likely `EXE+0x176B98` same as v5.7.6)
- Verify vtable indices
- Test DLL injection on actual hardware

**Owner:** PrintFlow team or DTG_automation investigator

**Timeline:** 1-2 days

---

### 2. Job Control (Print/Pause/Cancel/Movement) 🚧

**Status:** Stub WM_COMMAND IDs identified but NOT wired in any build.

**Work required per build:**
- DTG: Map HSCD.dll window classes, identify WM_COMMAND message IDs
- DTF: Reverse-engineer TaskMgr.dll UI message handling
- UV: Reverse-engineer TaskMgr.dll UI message handling

**Expected complexity:** Medium (requires Ghidra or UI automation mapping)

**Timeline:** 3-5 days per build (serial)

---

### 3. White/Varnish (DTF & UV) 🚧

**Status:** Requires CraftFlow deep scan (DTG_automation has started)

**Work required:**
- Identify CraftFlow plugin memory layout
- Find color/channel selector offsets
- Implement memory patching or DLL injection for white layer

**Timeline:** 2-3 days (after DTG_automation completes scan)

---

### 4. DebugParam.ini (DTF) 🚧

**Status:** Only UV currently has documented INI support.

**Work required:**
- Verify DTF v5.7.6 and v5.8.2 also use DebugParam.ini
- Document INI keys for speed, direction, mirror
- Test agent INI write/read flow on DTF hardware

**Timeline:** 1 day

---

## Statistics Database (StatisticData.db)

### Availability

| Build | Has DB | Auto-created | Retention |
|-------|--------|--------------|-----------|
| DTG | ❌ | N/A | N/A |
| DTF v5.7.6 | ❌ | No | N/A |
| DTF v5.8.2 | ✅ | Yes (first run) | Until deleted |
| UV v5.7.9 | ✅ | No (pre-existing) | Until deleted |

### Schema (UV/DTF v5.8.2)

Tables typically include:
- **Jobs** — job_name, timestamp, status, duration
- **Ink** — color, consumed_ml, refill_date
- **Parameters** — speed, direction, mirror settings

**Note:** Exact schema varies. Agent must query to discover available tables.

### Agent Integration

```python
# In agent backend (DTF v5.8.2, UV only)
db_path = printexp_data_folder / "StatisticData.db"
conn = sqlite3.connect(db_path)
cursor = conn.execute("SELECT * FROM Jobs WHERE timestamp > ?", (start_date,))
```

---

## Configuration & Detection

### Auto-Detection

```python
def detect_printer_type(exe_path: str) -> str:
    """Detect printer type from PrintExp.exe."""
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)

    if size_mb > 10:      # v5.8.2, UV (~11-12 MB)
        return "dtf-v5.8.2" if has_unicode_strings(exe_path) else "uv"
    elif size_mb > 9.5:   # UV (~10-11 MB)
        return "uv"
    elif 8.0 <= size_mb <= 9.5:  # DTF v5.7.6 (~8-9 MB)
        return "dtf"
    else:                 # DTG or unknown
        return "dtg"
```

### agent.toml

```toml
[printer]
type = "auto"  # auto, dtg, dtf, dtf-v5.8.2, uv

[printexp]
exe_path = "C:\\PrintExp_5.7.9.4.5008\\PrintExp.exe"
tcp_port = 9100

[uv.settings]  # UV only
speed = 2
direction = 0
mirror = false

[dtf.settings]  # DTF v5.8.2 only
speed = 2
direction = 0
mirror = false
```

---

## Integration Timeline

### Phase 1: Foundation (✅ Complete — 2026-03-26)
- [x] DTG TCP 9100 + WriteProcessMemory
- [x] DTF DLL injection (v5.7.6)
- [x] UV DLL injection (v5.7.9.4.5008)
- [x] Print History dashboard page
- [x] Agent `/reports/*` endpoints
- [x] TSKF writer for job persistence

### Phase 2: DTF v5.8.2 (🔄 In Progress)
- [ ] Offset discovery (memory scanner)
- [ ] DLL compilation & testing
- [ ] Agent backend integration
- [ ] Hardware validation

### Phase 3: Job Control (🚧 TODO)
- [ ] Pause/Resume implementation (per build)
- [ ] Cancel implementation (per build)
- [ ] Movement control (per build)

### Phase 4: Advanced Features (🚧 TODO)
- [ ] White/Varnish support (DTF & UV)
- [ ] Direction/Mirror for DTF (if DebugParam.ini available)
- [ ] Ink consumption tracking (all builds)

---

## References

- **Printer-backend-integration.md** — Full technical details (offsets, vtables, struct layouts)
- **Agent-printer-backend.md** — Agent implementation guide (detection, backends, error handling)
- **DTG_automation project** — DLL source code, memory scanners, reference implementations
- **Tech-stack.md** — Architecture, Win32 APIs, configuration

---

## Troubleshooting

### "Version not supported" error

Check agent.toml `printer.type` and PrintExp.exe path. Use `auto` for auto-detection.

### "DLL injection failed" (DTF/UV)

1. Verify PrintExp process is running
2. Check file permissions on `.dll` files
3. Ensure PrintExp.exe version matches (file size)
4. Review agent logs for memory offset details

### "Print History not available"

StatisticData.db only available on UV and DTF v5.8.2. DTF v5.7.6 and DTG do not maintain print history.

### Print job shows as "~section0.prn"

Indicates DLL injection failed; fell back to TCP 9100 (raw file, no filename metadata).

---

## Next Actions

1. **Discover DTF v5.8.2 offsets** — Run memory scanner on actual v5.8.2 build
2. **Implement job control** — Reverse-engineer WM_COMMAND IDs per build
3. **Test on all hardware** — Validate each build on actual printer PC
4. **Update roadmap** — Track Phase 2 & 3 progress
