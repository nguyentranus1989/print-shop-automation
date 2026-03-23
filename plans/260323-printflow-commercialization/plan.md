---
title: "PrintFlow Commercialization Architecture"
description: "Architecture changes to turn PrintFlow from internal tool into multi-shop commercial product"
status: pending
priority: P1
effort: 26d
branch: N/A
tags: [architecture, commercial, multi-tenant, licensing, security]
created: 2026-03-23
---

# PrintFlow Commercialization Plan

## Current State Summary

PrintFlow is a single-shop internal tool with 3 packages in a uv monorepo:

| Package | Role | Key Details |
|---|---|---|
| `common` | Shared models, config, protocols | Pydantic models, SQLAlchemy, AES crypto, TCP 9100, Win32 ctypes |
| `agent` | Headless printer service | FastAPI on :8080, PrinterBackend protocol, DTG/Mock backends |
| `dashboard` | Web UI + central API | FastAPI+Jinja2+HTMX on :8000, SQLite+WAL, SSE, polls agents via httpx |

**Architecture gap**: Dashboard takes agent URLs as CLI args, no auth, no persistent printer registry, single SQLite file, no tenant isolation. Agent has no identity verification.

---

## Phase Overview

| # | Phase | Scope | Effort | Priority |
|---|---|---|---|---|
| 1 | Persistent Printer Registry | DB-backed printer CRUD, replaces CLI args | 2d | MVP |
| 2 | Agent-Dashboard Auth | API key auth between agent/dashboard, login for dashboard users | 3d | MVP |
| 3 | Licensing System | Offline-first per-printer licensing with grace period | 4d | MVP |
| 4 | Multi-Shop Data Isolation | shop_id FK on all tables, scoped queries | 3d | MVP |
| 5 | Agent Installer | PyInstaller .exe + NSSM service + config wizard | 4d | MVP |
| 6 | Self-Hosted Update Mechanism | Version endpoint + download + service restart | 3d | MVP |
| 7 | Dashboard Auth & RBAC | Login page, admin/operator roles, session management | 3d | MVP |
| 8 | Cloud-Hosted Mode | HTTPS, PostgreSQL option, reverse proxy config | 2d | v2 |
| 9 | Telemetry & Support | Anonymous usage stats, crash reporting, remote diagnostics | 2d | v2 |
| 10 | mDNS Auto-Discovery | Zero-conf LAN printer discovery | 2d | v2 |

**MVP total: ~22d | v2 additions: ~6d**

---

## Phase Status

- [ ] Phase 1 — Persistent Printer Registry
- [ ] Phase 2 — Agent-Dashboard Auth
- [ ] Phase 3 — Licensing System
- [ ] Phase 4 — Multi-Shop Data Isolation
- [ ] Phase 5 — Agent Installer
- [ ] Phase 6 — Self-Hosted Update Mechanism
- [ ] Phase 7 — Dashboard Auth & RBAC
- [ ] Phase 8 — Cloud-Hosted Mode (v2)
- [ ] Phase 9 — Telemetry & Support (v2)
- [ ] Phase 10 — mDNS Auto-Discovery (v2)

---

## Key Dependencies

- Phase 2 (Auth) depends on Phase 1 (Registry) — agents register with API key
- Phase 4 (Multi-Shop) depends on Phase 1 — shop_id FK on printers table
- Phase 5 (Installer) depends on Phase 3 (Licensing) — installer prompts for license key
- Phase 6 (Updates) depends on Phase 5 — updates delivered to installed agents
- Phase 7 (Dashboard RBAC) depends on Phase 4 — users scoped to shops
- Phase 8 (Cloud) depends on Phase 4 + Phase 7

---

## Detailed Phase Files

- [Phase 1 — Persistent Printer Registry](./phase-01-persistent-printer-registry.md)
- [Phase 2 — Agent-Dashboard Auth](./phase-02-agent-dashboard-auth.md)
- [Phase 3 — Licensing System](./phase-03-licensing-system.md)
- [Phase 4 — Multi-Shop Data Isolation](./phase-04-multi-shop-data-isolation.md)
- [Phase 5 — Agent Installer](./phase-05-agent-installer.md)
- [Phase 6 — Self-Hosted Update Mechanism](./phase-06-update-mechanism.md)
- [Phase 7 — Dashboard Auth & RBAC](./phase-07-dashboard-auth-rbac.md)
- [Phase 8 — Cloud-Hosted Mode](./phase-08-cloud-hosted-mode.md)
- [Phase 9 — Telemetry & Support](./phase-09-telemetry-support.md)
- [Phase 10 — mDNS Auto-Discovery](./phase-10-mdns-auto-discovery.md)
