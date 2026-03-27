# PrintFlow Project Changelog

Detailed record of all significant changes, features, and fixes.

---

## [2026-03-26] Phase 1.5 Completion — MULTIWS + Build Variants

### Features

**MULTIWS Workstation Assignment (Phase 1 RE Complete)**
- feat: API endpoint for WS selection (`POST /api/ws/assign`)
- feat: Dashboard UI buttons for WS:0 (Left) & WS:1 (Right) assignment
- feat: Memory patch mechanism for CJobProcess+0x90 MULTIWS bitmask
- docs: Documented WS selection architecture in `system-architecture.md`

**Build Variant Architecture**
- feat: `DTFBackend(build_variant="v5.7.6" | "v5.8.2")` parameter
- feat: `UVBackend()` auto-detects UV build
- feat: Auto-detection logic based on EXE file size
- feat: Three bridge DLLs support (printflow-bridge.dll, printflow-bridge-dtf82.dll, printflow-bridge-uv.dll)
- docs: Build variant selection documented in `system-architecture.md`

**New Modules**
- feat: `dtg_ws_controller.py` — WS assignment API + memory patching
- feat: `dtg_ws_log_parser.py` — Parse PrintExp logs for WS assignments

**UV & DTF v5.8.2 Integration**
- feat: Bridge DLL compilation for UV (printflow-bridge-uv.dll)
- feat: Bridge DLL compilation for DTF v5.8.2 (printflow-bridge-dtf82.dll)
- feat: UV white ink channel control via `CTaskInfo+0x708` MultiInk flags
- feat: UV varnish control via bit manipulation in same offset
- docs: Updated `system-architecture.md` with three-DLL system design

### Fixes

**Job Table HTML Escaping**
- fix: Escape `<`, `>`, `&`, `"` in job filenames in dashboard HTML
- fix: Prevent XSS attacks via malicious filenames
- test: Added HTML escaping test cases (covered in E2E suite)

**Temp DLL Cleanup**
- fix: Add cleanup thread to remove stale inject DLLs
- fix: Prevent orphaned processes from accumulating
- fix: Cleanup runs after every 10 jobs or on shutdown
- test: Cleanup validation in E2E suite

### Testing

**E2E Test Suite (104 tests)**
- test: Job queue CRUD operations (20 tests)
- test: MULTIWS WS assignment (15 tests)
- test: DLL injection success/failure paths (25 tests)
- test: UV channel control (white/varnish toggles) (12 tests)
- test: DTF v5.7.6 vs v5.8.2 offset handling (18 tests)
- test: HTML escaping & XSS prevention (7 tests)
- test: DLL cleanup & orphan process handling (7 tests)

**Coverage:** 100% of critical paths (injection, WS assign, cleanup)

### Documentation

- docs: Created `project-roadmap.md` (roadmap + phase tracking)
- docs: Created `system-architecture.md` (complete architecture + data flow)
- docs: Updated `README.md` with new docs links
- docs: Updated MULTIWS WS bitmask design in `system-architecture.md`

---

## [2026-03-25] UV + DTF v5.8.2 Backend Integration

### Features

**UV PrintExp v5.7.9.4.5008 Backend**
- feat: DLL injection bridge for UV
- feat: Memory structure offsets (global pointer 0x1D2F10, AddFile vtable[9])
- feat: File vector management at +0x08 offset
- feat: White ink control (MultiInk channel flags)
- feat: Varnish control (MultiInk channel flags)
- feat: Safety notes documented (no print vector copying)

**DTF v5.8.2 Unicode Support**
- feat: Bridge DLL for DTF v5.8.2 (Unicode variant)
- feat: Build variant detection via EXE file size
- feat: Offset mapping preserved from v5.7.6 (pending full RE if needed)

### Fixes

- fix: UV backend no longer copies to print vector (prevents R6025 error)

### Documentation

- docs: Updated `printer-backend-integration.md` with UV offsets
- docs: Added DTF v5.8.2 architecture comparison table
- docs: Documented white/varnish control offsets for UV

---

## [2026-03-22] Dashboard + Agent Foundation

### Features

**Dashboard (HTMX)**
- feat: Job queue display with real-time status
- feat: Dark theme via Pico CSS
- feat: Job add form
- feat: Print control buttons (pause/resume/cancel — UI only, no backend yet)

**Agent Foundation**
- feat: FastAPI server on port 8000
- feat: Job queue management (SQLite)
- feat: DTF backend integration (DLL injection working)
- feat: TCP 9100 fallback for unsupported operations

### Documentation

- docs: Created `design-guidelines.md`
- docs: Created `tech-stack.md`
- docs: Created `printer-backend-integration.md` (initial DTF only)
- docs: Created `agent-printer-backend.md`

---

## [2026-03-20] Project Initialization

### Features

- feat: Python monorepo structure (uv workspaces)
- feat: SQLite job queue with WAL mode
- feat: Basic TCP 9100 PRN file injection (all builds)

### Documentation

- docs: Created `README.md`
- docs: Created research documents for tech stack & design

---

## Upcoming (Phase 2)

- [ ] Win32 PostMessage UI automation (pause/resume/cancel buttons wired)
- [ ] Real-time job progress monitoring
- [ ] Media & settings control (ink, platen temp)
- [ ] Offline queue persistence
- [ ] Print history dashboard (DTF v5.8.2, UV only)

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Commits | 5+ |
| Features Completed | 22 |
| Fixes Applied | 3 |
| Tests Written | 104 |
| Documentation Files | 8 |
| Total LOC (Docs) | ~2,500 |
| Build Support | 4 (DTG, DTF v5.7.6, DTF v5.8.2, UV) |

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 1.0 MVP | 2026-03-26 | ✅ RELEASED |
| 0.9 Beta | 2026-03-25 | ✅ TESTED |
| 0.5 Alpha | 2026-03-22 | ✅ WORKING |

---

## Last Updated

2026-03-26 15:00 UTC
