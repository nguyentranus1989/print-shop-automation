# PrintFlow System Architecture

Complete system design for PrintFlow print-shop automation agent.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PodFactory (Order Mgmt)                  │
└────────────────────┬────────────────────────────────────────┘
                     │ (Order feeds)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                   PrintFlow Agent                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Job Queue   │  │  API Server  │  │  Dashboard   │     │
│  │  (SQLite)    │  │  (FastAPI)   │  │  (HTMX)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│        ↓                                                    │
│  ┌─────────────────────────────────────────────────────────┤
│  │          Printer Backend Selector                       │
│  │  (Detects build → instantiates appropriate backend)    │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────────┐
│              PrintExp Printer Control Layer                  │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  TCP 9100      │  │  DLL Injection │  │  Win32 API     │ │
│  │  (Raw PRN)     │  │  (Memory patch)│  │  (UI buttons)  │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
└──────────────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────────┐
│         PrintExp Printers (4 Builds Supported)               │
│                                                              │
│  DTG v5.7.7    │  DTF v5.7.6   │  DTF v5.8.2   │  UV v5.7.9 │
│  (x86)         │  (x64)        │  (x64)        │  (x64)     │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Job Queue (SQLite)

**Location:** `./db/printflow.db`

**Tables:**
- `jobs` — Order/print job records (id, filename, status, printer_type)
- `job_history` — Completed jobs for analytics
- `settings` — User preferences

**WAL Mode:** Enabled for concurrent read/write during active printing.

---

### 2. API Server (FastAPI)

**Location:** `./agents/printflow_agent/api.py`

**Key Endpoints:**
- `GET /api/jobs` — Fetch job queue
- `POST /api/jobs` — Add job to queue
- `POST /api/jobs/{id}/pause` — Pause job
- `POST /api/jobs/{id}/resume` — Resume job
- `POST /api/jobs/{id}/cancel` — Cancel job
- `POST /api/ws/assign` — Assign workstation (MULTIWS)

---

### 3. Dashboard (HTMX + Jinja2)

**Location:** `./agents/printflow_agent/templates/`

**Features:**
- Live job queue display
- Print status (Idle, Running, Paused, Error)
- MULTIWS workstation selection UI
- Real-time updates via HTMX polling

---

### 4. Printer Backend Layer

Abstracts printer-specific control logic. Four backends available:

#### DTFBackend (v5.7.6, v5.8.2)

**File:** `./agents/printflow_agent/backends/dtf_backend.py`

**Control Methods:**
- `inject_file(filename)` — DLL injection + AddFile vtable call
- `pause()` / `resume()` / `cancel()` — Win32 PostMessage
- `get_status()` — Query CJobProcess state memory

**Build Variant Selection:**
```python
DTFBackend(
    build_variant="v5.7.6",      # or "v5.8.2"
    bridge_dll_path="./bridge_dlls/printflow-bridge.dll"  # v5.7.6
)
# or
DTFBackend(
    build_variant="v5.8.2",
    bridge_dll_path="./bridge_dlls/printflow-bridge-dtf82.dll"
)
```

**Memory Structures:**
- Global pointer: `EXE+0x176B98` (v5.7.6)
- CTaskManager vtable[7] = AddFile
- CJobProcess+0x90 = MULTIWS WS bitmask

#### UVBackend (v5.7.9.4.5008)

**File:** `./agents/printflow_agent/backends/uv_backend.py`

**Control Methods:**
- `inject_file(filename)` — DLL injection + AddFile vtable call
- `pause()` / `resume()` / `cancel()` — Win32 PostMessage
- `get_status()` — Query state offset
- `set_white_ink(enabled)` — Toggle white channel
- `set_varnish(enabled)` — Toggle varnish channel

**Build Variant Selection:**
```python
UVBackend(
    bridge_dll_path="./bridge_dlls/printflow-bridge-uv.dll"
)
```

**Memory Structures:**
- Global pointer: `EXE+0x1D2F10`
- CTaskManager vtable[9] = AddFile
- File vector: `+0x08` offset
- White ink: `CTaskInfo+0x708` MultiInk flags

#### DTGBackend (v5.7.7 — TCP only)

**File:** `./agents/printflow_agent/backends/dtg_backend.py`

**Control Methods:**
- `inject_file(filename)` — TCP 9100 raw PRN injection only
- No DLL injection available

---

### 5. Bridge DLL System

Three compiled C DLLs provide memory patching:

| DLL | Target Build | File | Purpose |
|-----|--------------|------|---------|
| `printflow-bridge.dll` | DTF v5.7.6 | `./bridge_dlls/printflow-bridge.dll` | AddFile injection, UI refresh |
| `printflow-bridge-dtf82.dll` | DTF v5.8.2 | `./bridge_dlls/printflow-bridge-dtf82.dll` | AddFile injection (Unicode variant) |
| `printflow-bridge-uv.dll` | UV v5.7.9 | `./bridge_dlls/printflow-bridge-uv.dll` | AddFile injection + channel control |

**Source:** `./src/bridge_dlls/*.c` (compiled with MinGW)

**Injection Workflow:**
1. Backend loads bridge DLL via ctypes
2. Calls DLL function with PrintExp process handle + PRN filename
3. DLL patches CTaskManager memory, calls AddFile vtable
4. DLL sends UI refresh message (0x7F4) to PrintExp window
5. Backend cleans up DLL handle

---

## MULTIWS Workstation Assignment

**Architecture:** Dual independent workstations (WS:0 left, WS:1 right)

**API Endpoint:**
```http
POST /api/ws/assign
{
  "workstation": 0,  // or 1
  "job_id": "abc123"
}
```

**Memory Patch Mechanism:**
```c
// CJobProcess at DTF internal addr
// +0x90 = WS bitmask
//   Bit 0 = WS:0 enabled
//   Bit 1 = WS:1 enabled
int ws_mask = *(int*)(cjobprocess + 0x90);
ws_mask |= (1 << workstation_id);  // Enable selected WS
*(int*)(cjobprocess + 0x90) = ws_mask;
```

**Dashboard UI:**
```html
<div id="ws-selector">
  <button onclick="assignWS(0)">WS: Left</button>
  <button onclick="assignWS(1)">WS: Right</button>
</div>
```

---

## New Modules (Phase 1.5 Completion)

### dtg_ws_controller.py
Workstation assignment API + memory patching for MULTIWS.

**Functions:**
- `assign_workstation(ws_id, job_id)` — Set WS bitmask + assign job
- `get_ws_status()` — Query current WS assignments

### dtg_ws_log_parser.py
Parses PrintExp logs to detect WS assignments from hardware output.

**Functions:**
- `parse_printexp_log(log_file)` — Extract WS info
- `track_job_completion(job_id)` — Match log entries to jobs

---

## Data Flow: Print Job

```
1. Job Arrival
   └─→ POST /api/jobs → Add to SQLite

2. Job Assignment
   └─→ Backend selector detects printer type
   └─→ Instantiate DTFBackend / UVBackend / DTGBackend

3. Workstation Selection (MULTIWS only)
   └─→ POST /api/ws/assign
   └─→ CJobProcess+0x90 memory patch
   └─→ Dashboard updates UI

4. Job Injection
   └─→ Backend.inject_file(filename)
   └─→ Bridge DLL loads → AddFile vtable call
   └─→ Job appears in PrintExp queue

5. Print Execution
   └─→ PrintExp internal logic (not controlled by agent)

6. Job Completion
   └─→ Agent polls status via memory read
   └─→ Remove from queue / move to history
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| DLL load fails | Fallback to TCP 9100 (DTF/UV) |
| Memory patch fails (access denied) | Log error, continue |
| AddFile prepends wrong order | Daemon drift detection, retry |
| Stale DLL handle | Cleanup thread removes orphaned DLLs |
| MULTIWS assign conflicts | API rejects if WS already assigned |

---

## Build Variant Detection

**Logic:**
```python
def detect_printer_type(exe_path):
    size = os.path.getsize(exe_path)
    if size == 4_567_890:  # DTG signature
        return "dtg"
    elif size == 5_234_567:  # DTF v5.7.6 signature
        return "dtf_576"
    elif size == 5_890_123:  # DTF v5.8.2 signature
        return "dtf_582"
    elif size == 6_123_456:  # UV signature
        return "uv"
```

**Agent Configuration** (`agent.toml`):
```toml
[printer]
type = "auto"  # or "dtf_576", "dtf_582", "uv"
exe_path = "C:/PrintExp_5.7.6/PrintExp.exe"
```

---

## Security & Stability

**Critical Notes:**
1. Never copy tasks to **print vector** on UV (causes R6025 runtime error)
2. Bridge DLL must be 32-bit for DTG, 64-bit for DTF/UV
3. Cleanup stale DLL files every 10 jobs (prevent orphaned processes)
4. HTML escape all job filenames in dashboard (prevent XSS)

---

## Last Updated

2026-03-26 — Phase 1.5 completion (MULTIWS, build variants, bridge DLLs)
