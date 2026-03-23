# Phase 10 — mDNS Auto-Discovery (v2)

## Context Links
- Phase 1: `./phase-01-persistent-printer-registry.md`
- Agent main: `packages/agent/src/agent/main.py`
- Dashboard agent manager: `packages/dashboard/src/dashboard/services/agent_manager.py`

## Overview
- **Priority**: P3 (v2, nice-to-have)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Zero-configuration LAN printer discovery using mDNS/DNS-SD. Agent advertises itself, dashboard discovers without manual IP entry.

## Key Insights

mDNS (Bonjour/Avahi) is standard for LAN service discovery. Agent broadcasts `_printflow._tcp.local.` service. Dashboard scans for these services and auto-populates the "Add Printer" dialog.

Only useful for self-hosted LAN deployments. Cloud-hosted agents register over HTTPS (Phase 1 registration is sufficient).

Python `zeroconf` library handles mDNS on Windows, macOS, Linux.

## Requirements

### Functional
- Agent advertises mDNS service on startup: `_printflow._tcp.local.`
- Service TXT record includes: agent name, printer type, port, version
- Dashboard "Add Printer" page shows "Discovered Printers" section
- User clicks discovered printer → auto-fills name/IP/port fields
- Discovery is passive (no user action needed, auto-refresh every 30s)
- Discovery disabled in cloud mode

### Non-Functional
- `zeroconf` library (~100KB, pure Python)
- mDNS works across subnets only with proper router config (limitation documented)
- Discovery timeout: 5 seconds per scan

## Implementation Steps

1. **Agent mDNS advertiser** (`agent/mdns_advertiser.py`)
   - Register `_printflow._tcp.local.` service on startup
   - TXT record: `name=DTG-Printer-01, type=dtg, port=8080, version=1.0.0`
   - Unregister on shutdown (lifespan cleanup)

2. **Dashboard mDNS scanner** (`dashboard/services/mdns_scanner.py`)
   - Scan for `_printflow._tcp.local.` services
   - Return list of `{name, ip, port, printer_type}` discovered
   - Cache results for 30 seconds

3. **API endpoint**
   - `GET /api/printers/discover` — returns discovered printers not yet registered
   - Filters out already-registered agent URLs

4. **Dashboard UI**
   - "Discovered Printers" section on printers page
   - Cards with "Add" button for each discovered printer
   - HTMX polling: `hx-get="/api/printers/discover" hx-trigger="every 30s"`

5. **Add `zeroconf` dependency**
   - Optional: `pip install printflow-agent[discovery]`
   - Graceful fallback if not installed

## Todo List

- [ ] Add `zeroconf` dependency (optional)
- [ ] Create `agent/mdns_advertiser.py`
- [ ] Create `dashboard/services/mdns_scanner.py`
- [ ] `GET /api/printers/discover` endpoint
- [ ] UI: "Discovered Printers" section
- [ ] Tests: mock mDNS service registration and discovery
- [ ] Document subnet limitation

## Success Criteria

- Agent starts → appears in dashboard "Discovered Printers" within 10s
- Click "Add" on discovered printer → registered and polling starts
- Stopping agent → disappears from discovery list within 30s
- Works without internet (LAN only)
