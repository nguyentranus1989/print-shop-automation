# Phase 1 — Persistent Printer Registry

## Context Links
- Current agent manager: `packages/dashboard/src/dashboard/services/agent_manager.py`
- Current DB models: `packages/dashboard/src/dashboard/db/models.py`
- Current printers API: `packages/dashboard/src/dashboard/api/printers.py`
- Dashboard main: `packages/dashboard/src/dashboard/main.py`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Replace CLI-arg-based agent URL list with a persistent DB-backed printer registry. "Add Printer" from dashboard UI, agents self-register on startup.

## Key Insights

Current `AgentManager.__init__` takes `agent_urls: list[str]` from CLI args. The `Printer` DB model already exists but isn't used for discovery — it's populated separately. The two systems (in-memory URL list vs DB printers table) are disconnected.

The fix: AgentManager loads printer URLs from the DB at startup and dynamically adds/removes them when printers are registered/deleted via API.

## Requirements

### Functional
- POST `/api/printers/register` — agent calls this on startup with `{name, ip, port, printer_type, api_key}`
- GET `/api/printers` — list all registered printers (already exists, needs minor update)
- DELETE `/api/printers/{id}` — remove a printer
- PUT `/api/printers/{id}` — update printer name/config
- Dashboard UI: "Add Printer" button on printers page with form (name, IP, port)
- Agent heartbeat: agent periodically POSTs to dashboard `/api/printers/heartbeat` with its status

### Non-Functional
- Registration idempotent — re-registering same `agent_url` updates existing record
- No data loss on dashboard restart — all printers reload from DB

## Architecture

```
Agent startup:
  1. Read agent.toml → get dashboard_url
  2. POST {dashboard_url}/api/printers/register {name, ip, port, type}
  3. Dashboard upserts into printers table
  4. AgentManager adds URL to polling set

Dashboard startup:
  1. init_db()
  2. Load all Printer rows from DB
  3. AgentManager starts polling those URLs

Manual add:
  1. User clicks "Add Printer" in dashboard UI
  2. Enters name + IP + port
  3. POST /api/printers/register
  4. Same flow as agent self-register
```

## Related Code Files

### Modify
- `packages/dashboard/src/dashboard/services/agent_manager.py` — add `add_agent()`, `remove_agent()`, load from DB
- `packages/dashboard/src/dashboard/api/printers.py` — add register/delete/update endpoints
- `packages/dashboard/src/dashboard/main.py` — load printers from DB at startup instead of CLI args
- `packages/dashboard/src/dashboard/templates/printers.html` — add "Add Printer" form
- `packages/agent/src/agent/main.py` — add self-registration call on startup
- `packages/common/src/common/config.py` — ensure `dashboard_url` is always present

### Create
- `packages/agent/src/agent/registration.py` — agent-side registration + heartbeat logic

## Implementation Steps

1. **Add registration endpoint to dashboard API** (`api/printers.py`)
   - `POST /api/printers/register` — accepts `{name, agent_url, printer_type}`
   - Upsert logic: if `agent_url` exists, update name/type/last_seen; else insert
   - Returns printer ID and acknowledgment

2. **Add delete/update endpoints**
   - `DELETE /api/printers/{id}` — removes from DB + tells AgentManager to stop polling
   - `PUT /api/printers/{id}` — update mutable fields (name)

3. **Refactor AgentManager to be dynamic**
   - Remove `agent_urls` constructor param
   - Add `load_from_db(session)` method — queries all Printer rows, populates internal URL set
   - Add `add_agent(url)` / `remove_agent(url)` — live updates to polling set
   - Called by register/delete endpoints

4. **Update dashboard startup**
   - `_make_app()` no longer takes `agent_urls` param
   - In lifespan: `init_db()` then `manager.load_from_db(session)`
   - Remove `--agents` CLI flag (keep env var as fallback for migration)

5. **Agent self-registration**
   - New `registration.py`: on startup, POST to `{dashboard_url}/api/printers/register`
   - Retry with backoff if dashboard unreachable (dashboard might start later)
   - Periodic heartbeat: POST `/api/printers/heartbeat` every 30s with agent status

6. **Dashboard UI — "Add Printer" form**
   - HTMX form on printers page: name, IP, port fields
   - `hx-post="/api/printers/register"` with form data
   - Success: new printer card appears via HTMX swap

7. **Alembic migration** for any schema changes (probably none needed — Printer model is sufficient)

## Todo List

- [ ] Add `POST /api/printers/register` endpoint (upsert)
- [ ] Add `DELETE /api/printers/{id}` endpoint
- [ ] Add `PUT /api/printers/{id}` endpoint
- [ ] Refactor `AgentManager` — dynamic URL set, `load_from_db()`
- [ ] Update `_make_app()` to load from DB
- [ ] Remove `--agents` CLI flag
- [ ] Create `agent/registration.py` — self-register + heartbeat
- [ ] Update agent `main.py` — call registration on startup
- [ ] Add "Add Printer" form to `printers.html`
- [ ] Write tests for register/delete/update endpoints
- [ ] Write test for AgentManager dynamic add/remove

## Success Criteria

- Dashboard starts with zero CLI args and discovers printers from DB
- Agent self-registers on startup; appears in dashboard within 5s
- Manually adding a printer via UI starts polling immediately
- Deleting a printer stops polling and removes from DB
- Dashboard restart preserves all registered printers

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Agent starts before dashboard | Agent can't register | Retry with exponential backoff (1s, 2s, 4s... max 60s) |
| Stale printers (agent removed but DB entry remains) | Dashboard polls dead URL | Heartbeat timeout: mark offline after 3 missed heartbeats, auto-remove after 7 days |
| Race condition in upsert | Duplicate entries | Use `agent_url` UNIQUE constraint (already exists in model) |

## Security Considerations

- Registration endpoint is unauthenticated in this phase (secured in Phase 2)
- No sensitive data in registration payload
- Rate-limit registration endpoint to prevent abuse (10 req/min per IP)
