# PrintFlow Development Roadmap

Living document tracking project phases, milestones, and progress.

---

## Phase 1: MVP Print Automation (COMPLETE)

**Status:** ✅ COMPLETE (2026-03-26)

### 1.1 - Foundation & Dashboard Setup
- ✅ FastAPI + Jinja2 + HTMX baseline
- ✅ SQLite job queue + WAL mode
- ✅ Dashboard layout & dark theme
- ✅ Job table with status display

**Completion:** 2026-03-22

### 1.2 - DTF Backend Integration
- ✅ DLL injection framework (v5.7.6 & v5.8.2)
- ✅ Memory patching for filename display
- ✅ Job table HTML escaping fix
- ✅ TCP 9100 fallback

**Completion:** 2026-03-25

### 1.3 - UV Backend Integration
- ✅ UV PrintExp v5.7.9.4.5008 DLL injection
- ✅ Build variant selection (3 bridge DLLs)
- ✅ UV-specific memory offsets & safety notes
- ✅ Injection backend wired into agent

**Completion:** 2026-03-26

### 1.4 - Multi-Workstation (MULTIWS) Support
- ✅ MULTIWS WS assignment API
- ✅ Dashboard UI for WS selection
- ✅ CJobProcess+0x90 memory patch for WS bitmask
- ✅ RE phase complete (Phase 1)

**Completion:** 2026-03-26

### 1.5 - Quality Assurance
- ✅ Temp DLL cleanup fix (prevent orphaned processes)
- ✅ Job table HTML escaping fix
- ✅ E2E test suite (104 tests)

**Completion:** 2026-03-26

---

## Phase 2: Advanced Controls (PLANNED)

**Status:** 📋 PLANNED

### 2.1 - Print Controls
- [ ] Win32 PostMessage UI automation
- [ ] Pause/Resume/Cancel via UI buttons
- [ ] Real-time print progress monitoring
- [ ] Job preview in queue

### 2.2 - Media & Settings
- [ ] White ink control (DTF/UV)
- [ ] Varnish control (UV)
- [ ] Platen temperature (DTF)
- [ ] Ink channel toggles (UV)

### 2.3 - Offline Mode
- [ ] Job queue persistence on network failure
- [ ] Queue recovery on reconnect
- [ ] Offline indicator UI

---

## Phase 3: Analytics & Reporting

**Status:** 📋 PLANNED

### 3.1 - Print History Dashboard
- [ ] Job completion metrics (DTF v5.8.2, UV)
- [ ] Print time trends
- [ ] Media usage tracking
- [ ] Hardware error frequency

### 3.2 - Export & Reporting
- [ ] CSV export of job history
- [ ] PDF reports
- [ ] Monthly usage summaries

---

## Phase 4: Scaling & Reliability

**Status:** 📋 PLANNED

### 4.1 - Multi-Printer Orchestration
- [ ] Queue prioritization across printers
- [ ] Load balancing
- [ ] Failover handling

### 4.2 - Monitoring & Alerts
- [ ] Hardware health checks
- [ ] Error notification email
- [ ] Uptime dashboard

---

## Key Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Build Support | 4 (DTG, DTF v5.7.6, DTF v5.8.2, UV) | ✅ 4/4 |
| DLL Injection | DTF + UV | ✅ Complete |
| MULTIWS WS Selection | Memory patch + API | ✅ Complete |
| E2E Test Coverage | 100+ tests | ✅ 104/104 |
| Dashboard Features | Print queue + controls | ✅ Partial (queue only) |

---

## Dependencies & Blockers

None currently blocking Phase 2. DTF v5.8.2 offset discovery (vtable, global pointer) pending if manual AddFile behavior differs from v5.7.6.

---

## Last Updated

2026-03-26 — Phase 1 completion & MULTIWS support
