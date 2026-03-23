# Phase 2 — Agent-Dashboard Auth

## Context Links
- Agent API: `packages/agent/src/agent/api.py`
- Dashboard printers API: `packages/dashboard/src/dashboard/api/printers.py`
- Agent config: `packages/common/src/common/config.py`
- Phase 1 (prerequisite): `./phase-01-persistent-printer-registry.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Mutual API key authentication between agent and dashboard. Dashboard authenticates to agent for status/control. Agent authenticates to dashboard for registration/heartbeat. Prevents unauthorized access on LAN.

## Key Insights

Current system has zero auth — any device on the LAN can send print commands to agents or register fake printers. For commercial product, at minimum need shared-secret API key auth.

Full OAuth2/JWT is overkill for LAN-first deployment. Simple `X-API-Key` header with HMAC-SHA256 signed keys is sufficient and works offline.

## Requirements

### Functional
- API key generated during initial setup (first dashboard run or installer)
- Agent stores API key in `agent.toml` under `[auth]` section
- Dashboard stores API keys in DB (one per registered printer)
- All agent->dashboard requests include `X-API-Key` header
- All dashboard->agent requests include `X-API-Key` header
- Dashboard rejects requests without valid key (401)
- Agent rejects requests without valid key (401)

### Non-Functional
- Keys are 256-bit random, hex-encoded (64 chars)
- Keys stored in config files (agent.toml) or DB (dashboard), never in URL params
- Key rotation: admin can regenerate key for a printer (old key immediately invalid)
- Performance: key lookup must be O(1) — in-memory cache refreshed from DB

## Architecture

```
Setup flow:
  1. Admin generates API key in dashboard (or during install)
  2. Key displayed once, admin copies to agent.toml [auth] section
  3. Agent uses key for all requests to dashboard
  4. Dashboard stores hash of key (not plaintext) in printers table

Runtime:
  Agent -> Dashboard (register/heartbeat):
    POST /api/printers/register
    Header: X-API-Key: <key>
    Dashboard: lookup key hash in DB, validate

  Dashboard -> Agent (status/control):
    GET http://agent:8080/status
    Header: X-API-Key: <key>
    Agent: compare with key from agent.toml
```

## Related Code Files

### Modify
- `packages/common/src/common/config.py` — add `api_key` field to AgentConfig
- `packages/agent/src/agent/api.py` — add API key middleware/dependency
- `packages/agent/src/agent/main.py` — load API key from config
- `packages/dashboard/src/dashboard/api/printers.py` — validate agent API keys
- `packages/dashboard/src/dashboard/services/agent_manager.py` — include API key in outbound requests
- `packages/dashboard/src/dashboard/db/models.py` — add `api_key_hash` to Printer model

### Create
- `packages/common/src/common/auth.py` — key generation, hashing, validation utilities
- `packages/dashboard/src/dashboard/api/auth_middleware.py` — FastAPI dependency for API key validation

## Implementation Steps

1. **Create `common/auth.py`**
   - `generate_api_key() -> str` — `secrets.token_hex(32)` (64-char hex string)
   - `hash_api_key(key: str) -> str` — SHA-256 hash for DB storage
   - `verify_api_key(key: str, stored_hash: str) -> bool` — constant-time compare

2. **Add `api_key_hash` column to Printer model**
   - `api_key_hash: Mapped[str | None]` on `Printer` in `db/models.py`
   - Alembic migration to add column

3. **Dashboard API key generation endpoint**
   - `POST /api/printers/{id}/generate-key` — generates key, stores hash, returns plaintext once
   - Admin-only (secured in Phase 7; for now any request)

4. **Dashboard inbound auth middleware**
   - FastAPI `Depends` function: extract `X-API-Key` header
   - Look up hash in printers table (cached in memory for performance)
   - Return 401 if missing/invalid
   - Apply to: register, heartbeat endpoints

5. **Agent outbound auth**
   - `AgentConfig.api_key` loaded from `[auth]` section in agent.toml
   - `registration.py` includes key in `X-API-Key` header
   - Agent API health endpoint remains unauthenticated (needed for discovery)

6. **Agent inbound auth**
   - Middleware on agent's FastAPI app: check `X-API-Key` header
   - Compare against `config.api_key` (same key used bidirectionally)
   - Exempt: `GET /health` (unauthenticated, needed for connectivity checks)

7. **Dashboard outbound auth**
   - `AgentManager` loads API key from Printer DB record when polling
   - Includes key in `X-API-Key` header for all agent requests

8. **Config update**
   - `agent.toml` gains `[auth]` section:
     ```toml
     [auth]
     api_key = "a1b2c3d4..."
     ```
   - Dashboard UI shows key once during generation (copy-to-clipboard button)

## Todo List

- [ ] Create `common/auth.py` (generate, hash, verify)
- [ ] Add `api_key_hash` to Printer model + migration
- [ ] Add key generation endpoint
- [ ] Dashboard inbound auth middleware
- [ ] Agent inbound auth middleware
- [ ] Agent outbound auth (registration + heartbeat)
- [ ] Dashboard outbound auth (AgentManager polling)
- [ ] Update `agent.toml` format with `[auth]` section
- [ ] UI: key display/copy on printer detail page
- [ ] Tests: auth middleware rejects bad keys, accepts good keys
- [ ] Tests: key rotation invalidates old key immediately

## Success Criteria

- Agent cannot register without valid API key → 401
- Dashboard cannot poll agent without valid API key → 401
- Random LAN device cannot send print commands to agent → 401
- `/health` endpoints remain open (needed for discovery)
- Key rotation works: generate new key, update agent.toml, old key rejected

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Key leaked in logs | Unauthorized access | Never log API keys; redact in error messages |
| Key lost (agent.toml deleted) | Agent can't communicate | Admin regenerates in dashboard, re-enters in agent config |
| Performance overhead | Slower requests | In-memory key cache with 60s TTL, skip DB lookup per request |
| Migration breaks existing setups | Downtime | Auth optional during migration period (env var `PRINTFLOW_AUTH_REQUIRED=false`) |

## Security Considerations

- Keys are 256-bit entropy — brute force infeasible
- Stored as SHA-256 hash in DB — DB compromise doesn't leak keys
- Constant-time comparison prevents timing attacks
- No key in URL (query params) — only in headers
- HTTPS recommended but not required (Phase 8 adds TLS for cloud)
