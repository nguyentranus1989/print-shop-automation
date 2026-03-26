# PrintFlow Documentation

Navigation guide for print-shop-automation project documentation.

---

## Core Architecture & Design

| Document | Purpose | Last Updated |
|----------|---------|--------------|
| [tech-stack.md](./tech-stack.md) | Technology choices, rationale, dependency summary | 2026-03-26 |
| [design-guidelines.md](./design-guidelines.md) | Dashboard UI/UX design system, dark theme, component library | 2026-03-22 |

---

## Printer Integration (Backend)

| Document | Purpose | Last Updated |
|----------|---------|--------------|
| [printer-backend-integration.md](./printer-backend-integration.md) | **DTF & UV memory injection technical reference** — offsets, vtables, struct layouts, workflow | 2026-03-26 ✨ |
| [agent-printer-backend.md](./agent-printer-backend.md) | **Agent developer guide** — printer type detection, backend classes, job injector, testing | 2026-03-26 ✨ |
| [dtf-memory-patch-research.md](./dtf-memory-patch-research.md) | Historical DTF research notes (legacy, see printer-backend-integration.md) | 2026-03-26 |

**For Agent Developers:** Start with [agent-printer-backend.md](./agent-printer-backend.md) for implementation reference, then consult [printer-backend-integration.md](./printer-backend-integration.md) for technical deep-dive.

---

## Research & Exploration

| Document | Purpose |
|----------|---------|
| [research-python-monorepo.md](./research-python-monorepo.md) | Python packaging options (uv workspaces) |
| [research-htmx-dark-theme.md](./research-htmx-dark-theme.md) | HTMX + dark theme implementation patterns |
| [research-mobile-dashboard.md](./research-mobile-dashboard.md) | Mobile/touch-first dashboard design |
| [research-dashboard-inspiration.md](./research-dashboard-inspiration.md) | Commercial print shop dashboard UX examples |
| [research-commercial-landscape.md](./research-commercial-landscape.md) | Market analysis and competitive landscape |

---

## Change Log

| Document | Purpose |
|----------|---------|
| [UPDATE-LOG-UV-INTEGRATION.md](./UPDATE-LOG-UV-INTEGRATION.md) | Summary of UV PrintExp integration documentation (2026-03-26) |

---

## Quick Reference

### For Agent Implementation
1. Read: [agent-printer-backend.md](./agent-printer-backend.md) — Design and workflow
2. Reference: [printer-backend-integration.md](./printer-backend-integration.md) — Technical details
3. Test: Use hardware test scripts in agent package

### For Dashboard Development
1. Read: [design-guidelines.md](./design-guidelines.md) — UI/UX system
2. Reference: [tech-stack.md](./tech-stack.md) — FastAPI, HTMX, Pico CSS setup

### For Printer Integration
1. **DTF backend:** [printer-backend-integration.md](./printer-backend-integration.md#dtf-backend-v576)
2. **UV backend:** [printer-backend-integration.md](./printer-backend-integration.md#uv-backend-v57945008)
3. **Safety notes:** [printer-backend-integration.md](./printer-backend-integration.md#critical-warnings)

---

## Technical Stack Summary

**Frontend:** FastAPI + Jinja2 + HTMX 2.0 + Pico CSS (no React/Node.js)

**Backend:** Python 3.11+ · uv workspaces · SQLAlchemy 2.0 · SQLite + WAL mode

**Printer Control:**
- **TCP 9100** — Raw PRN file injection
- **DLL Injection** — Memory patching for filename display (DTF v5.7.6 & UV v5.7.9+)
- **Win32 API** — PostMessage for UI automation (pause/resume/cancel)

**Development:** pytest · ruff (linting) · PyInstaller (packaging)

See [tech-stack.md](./tech-stack.md) for full details.

---

## File Naming Convention

- **Core docs:** descriptive kebab-case (`printer-backend-integration.md`)
- **Research docs:** prefix with `research-` (`research-python-monorepo.md`)
- **Updates:** prefix with `UPDATE-LOG-` (`UPDATE-LOG-UV-INTEGRATION.md`)
- **Guides:** descriptive name, can include topic prefix (`agent-printer-backend.md`)

---

## Size Limits

All documentation files kept under 400 LOC for optimal readability and context management.

- `printer-backend-integration.md` — 364 LOC
- `agent-printer-backend.md` — 384 LOC
- `tech-stack.md` — 198 LOC
- Other files — 50–200 LOC each

Total documentation: ~2,300 lines across 11 files.

---

## Contributing

When updating documentation:

1. **Link properly:** Use relative links (`[text](./file.md)`)
2. **Keep it modular:** Split large topics into separate files
3. **Update this README:** Add/remove files from tables above
4. **Cross-reference:** Link related topics
5. **Verify accuracy:** Check code against actual implementation
