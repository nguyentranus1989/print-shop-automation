# PrintFlow Tech Stack

> Internal print shop automation tool bridging PodFactory (order management) with DTG/DTF/UV printers via PrintExp.
> Windows-only deployment on printer workstation PCs (Windows 10/11).
> Supports 4 PrintExp builds: DTG v5.7.7 (x86), DTF v5.7.6 & v5.8.2 (x64), UV v5.7.9 (x64).

## Architecture Summary

Python monorepo with 3 packages managed by uv workspaces:

| Package | Role | Runs on |
|---|---|---|
| `common` | Shared models, DB, config, protocols | Imported by both |
| `agent` | Headless service on each printer PC — polls orders, injects jobs via TCP 9100, patches PrintExp memory | Printer PC |
| `dashboard` | FastAPI web UI — order queue, job status, printer health | Printer PC or central server |

---

## 1. Runtime

| Component | Choice | Notes |
|---|---|---|
| Python | **3.11+** | `tomllib` built-in (no third-party TOML reader). Target 3.12 for perf. |
| Package manager | **uv** | Fast resolver, workspace support (`uv.lock`), replaces pip/poetry/hatch. |
| Workspace layout | `uv` workspaces | Root `pyproject.toml` declares `[tool.uv.workspace]` with `packages/common`, `packages/agent`, `packages/dashboard`. |

**Why uv:** Single lock file, fast installs, native workspace deps (`common = { workspace = true }`), Windows-friendly.

## 2. Web Framework

| Component | Choice | Version |
|---|---|---|
| API/server | **FastAPI** | 0.115+ |
| ASGI server | **Uvicorn** | Latest stable |
| Templating | **Jinja2** | Via `fastapi.templating` |

FastAPI serves both HTML pages (Jinja2) and JSON API endpoints. No separate frontend build step. Uvicorn runs in single-worker mode (SQLite constraint).

## 3. Frontend

| Component | Choice | Notes |
|---|---|---|
| Interactivity | **HTMX 2.0** | Declarative, no JS build. Partial HTML swaps via `hx-get`, `hx-swap`. |
| Real-time | **SSE** (`EventSource`) | Server-Sent Events via FastAPI `StreamingResponse`. Job status updates, printer health. No WebSocket complexity. |
| CSS | **Pico CSS** | Classless/minimal. Clean defaults, dark mode, responsive. Single `<link>` tag. |

**No React, no Node.js, no npm.** HTMX loaded from CDN or vendored static file. JS limited to HTMX extensions and tiny inline scripts if needed.

## 4. Database

| Component | Choice | Notes |
|---|---|---|
| ORM | **SQLAlchemy 2.0** | Sync mode (`create_engine`, not `create_async_engine`). 2.0-style `select()` queries. |
| Database | **SQLite** | WAL mode enabled (`PRAGMA journal_mode=WAL`). Single-file, zero-config, adequate for single-site throughput. |
| Migrations | **Alembic** | Schema versioning. Bundled in `common` package. |

**Why sync SQLAlchemy:** SQLite + async = complexity (aiosqlite, thread pools) with no benefit at this scale. FastAPI handles async routes; DB calls are fast enough synchronously.

**WAL mode:** Enables concurrent reads while writing. Set at engine creation via `engine.execute("PRAGMA journal_mode=WAL")` event listener.

## 5. Protocols

| Need | Library | Usage |
|---|---|---|
| AES encryption | **pycryptodome** | Decrypt PodFactory API payloads or stored credentials if needed. AES-CBC/GCM. |
| TCP 9100 (raw print) | **stdlib `socket`** | Send .prn file data to PrintExp `127.0.0.1:9100`. Raw TCP, no HTTP. |
| HSRP / Hoson protocol | **stdlib `socket`** | Future: mainboard communication on `192.168.127.10:5001`. Binary protocol, CRC validation. |

No third-party socket libraries needed. Python stdlib `socket` is sufficient for raw TCP.

## 6. Win32 Integration

| API | Method | Usage |
|---|---|---|
| `PostMessageW` | **ctypes** | Send WM_COMMAND to PrintExp (print, pause, cancel, axis movement). |
| `WriteProcessMemory` | **ctypes** | Memory patching for filename injection (DTG x86 approach). |
| `EnumWindows` / `EnumChildWindows` | **ctypes** | Find PrintExp HWND (changes each launch). |
| `OpenProcess` | **ctypes** | Get process handle with `PROCESS_VM_WRITE \| PROCESS_VM_OPERATION`. |
| `CreateToolhelp32Snapshot` | **ctypes** | Find PrintExp PID and DLL base addresses. |
| **DLL Injection** | **ctypes** | Modern approach for DTF/UV x64 — inject compiled DLL into PrintExp to access internal vtables and CTaskManager. |

**Why ctypes over pywin32:** Zero install dependency, ships with Python, sufficient for the handful of Win32 calls needed. No COM automation required.

**Multi-build support:**
- DTG v5.7.7 (x86) — WriteProcessMemory via global pointer
- DTF v5.7.6 (x64) — DLL injection with vtable[7] AddFile (offset: EXE+0x176B98)
- DTF v5.8.2 (x64) — DLL injection with same method, offsets TBD
- UV v5.7.9 (x64) — DLL injection with vtable[9] AddFile (offset: EXE+0x1D2F10)

See [printer-support-matrix.md](./printer-support-matrix.md) for feature comparison and [printer-backend-integration.md](./printer-backend-integration.md) for DTF/UV DLL injection technical details.

## 7. HTTP Client

| Component | Choice | Notes |
|---|---|---|
| HTTP client | **httpx** | Async client for agent polling loop + PodFactory API calls. Connection pooling, timeout config, retry support. |

Agent uses `httpx.AsyncClient` for:
- Polling PodFactory API for new orders
- Downloading .prn files from NAS/S3
- Reporting status to dashboard (if running on separate host)

## 8. Configuration

| Component | Choice | Notes |
|---|---|---|
| Agent config | **TOML** (`agent.toml`) | Per-printer config: printer name, PrintExp path, TCP ports, poll interval, NAS paths. |
| Parser | **tomllib** (stdlib) | Built into Python 3.11+. Read-only (no write needed for config). |
| Secrets | **.env** + `python-dotenv` | API keys, MongoDB URI. Not committed to git. |

Example `agent.toml`:
```toml
[agent]
name = "DTG-Printer-01"
poll_interval_seconds = 5

[printexp]
exe_path = "C:\\PrintExp_5.7.7.1.12_MULTIWS\\PrintExp.exe"
tcp_port = 9100
memory_offset = 0x016CDB

[nas]
prn_share = "\\\\NAS\\dtg-rip-output"
```

## 9. Testing

| Component | Choice | Notes |
|---|---|---|
| Test runner | **pytest** | Standard. Fixtures, parametrize, assert rewriting. |
| Async tests | **pytest-asyncio** | Test async httpx calls, SSE endpoints. |
| HTTP testing | **httpx** (`ASGITransport`) | Test FastAPI app without running server. |
| Coverage | **pytest-cov** | Track coverage, enforce minimum. |

Win32 functions (ctypes calls) tested via mocking since they require a running PrintExp process. Integration tests run on actual printer PCs.

## 10. Packaging & Deployment

| Component | Choice | Notes |
|---|---|---|
| Binary bundling | **PyInstaller** | Freeze agent + dashboard into standalone `.exe`. No Python install needed on target PCs. |
| Windows service | **NSSM** | "Non-Sucking Service Manager." Wraps the agent `.exe` as a Windows service (auto-start, restart on crash, log rotation). |
| Alternative service | **pywin32 `serviceutil`** | Fallback if NSSM causes issues. Native Windows service via Python. |

**Deployment flow:**
1. `uv build` packages
2. PyInstaller bundles `agent` and `dashboard` separately
3. Copy `.exe` + `agent.toml` to printer PC
4. `nssm install PrintFlowAgent <path>\agent.exe`
5. `nssm set PrintFlowAgent AppDirectory <path>`
6. `nssm start PrintFlowAgent`

## 11. Linting & Formatting

| Component | Choice | Notes |
|---|---|---|
| Linter + formatter | **ruff** | Replaces flake8, isort, black. Single tool, fast (Rust-based). |
| Type checking | **pyright** (optional) | VS Code integration. Not enforced in CI initially. |

Ruff config in root `pyproject.toml`:
```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
```

---

## Dependency Summary

### Production

```
fastapi>=0.115
uvicorn[standard]
jinja2
sqlalchemy>=2.0
alembic
httpx
pycryptodome
python-dotenv
```

### Development

```
pytest
pytest-asyncio
pytest-cov
ruff
pyinstaller
```

### Not Used (and why)

| Avoided | Reason |
|---|---|
| React / Vue / Node.js | HTMX + Jinja2 is simpler, no build step, no JS ecosystem |
| aiosqlite / async SQLAlchemy | Unnecessary complexity for SQLite at this scale |
| pywin32 | ctypes covers all needed Win32 calls without install dependency |
| Django | Heavier than needed; FastAPI + SQLAlchemy gives more control |
| WebSocket | SSE is simpler for server-to-client updates; no bidirectional need |
| MongoDB driver | Dashboard uses SQLite locally; PodFactory data fetched via HTTP API |
| celery / task queue | Agent is single-process; asyncio tasks sufficient |
