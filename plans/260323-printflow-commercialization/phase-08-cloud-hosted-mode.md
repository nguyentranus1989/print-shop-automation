# Phase 8 — Cloud-Hosted Mode (v2)

## Context Links
- Database: `packages/dashboard/src/dashboard/db/database.py`
- Phase 4: `./phase-04-multi-shop-data-isolation.md`
- Phase 7: `./phase-07-dashboard-auth-rbac.md`

## Overview
- **Priority**: P2 (v2)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Enable running dashboard as a cloud service for shops that don't want to self-host. HTTPS, PostgreSQL support, reverse proxy config, data isolation enforced.

## Key Insights

Self-hosted is the primary deployment. Cloud is optional for shops that want zero maintenance. Same codebase, switched by config/env vars.

Main changes: swap SQLite for PostgreSQL, add TLS termination via reverse proxy (nginx/Caddy), ensure multi-shop isolation (Phase 4) is airtight.

## Requirements

### Functional
- `DASHBOARD_MODE=cloud` env var switches behavior
- PostgreSQL connection via `DATABASE_URL` env var (SQLAlchemy URL)
- HTTPS termination via reverse proxy (not in Python)
- Multi-worker support (Gunicorn/Uvicorn workers) — no longer SQLite single-writer constraint
- Signup flow: new shop → create Shop record → create admin user → generate license
- Per-shop subdomain or URL path routing (optional, v2.1)

### Non-Functional
- Zero code changes between self-hosted and cloud binary
- PostgreSQL 15+ (jsonb, good performance)
- Connection pooling via SQLAlchemy pool (or PgBouncer for scale)
- HTTPS with Let's Encrypt via Caddy (simplest reverse proxy)

## Architecture

```
Cloud deployment:
  Caddy (HTTPS, reverse proxy)
    → Uvicorn (multiple workers)
      → FastAPI dashboard app
        → PostgreSQL (multi-shop data)
        → Redis (optional, for session store at scale)

  Agents on customer LANs:
    → HTTPS to cloud dashboard
    → API key auth (Phase 2)
    → Shop ID in registration payload
```

## Implementation Steps

1. **Database abstraction** — make engine creation configurable
   - If `DATABASE_URL` starts with `postgresql://`: use psycopg2 driver
   - If `sqlite://`: keep current behavior
   - Add `psycopg2-binary` as optional dependency

2. **Multi-worker support**
   - Remove `check_same_thread=False` for PostgreSQL
   - Use connection pool (SQLAlchemy default pool for PostgreSQL)
   - Test with `uvicorn --workers 4`

3. **Reverse proxy config**
   - Caddy config template for HTTPS + Let's Encrypt
   - Trust `X-Forwarded-For` headers
   - Add `--proxy-headers` to uvicorn

4. **Cloud signup flow** (simple)
   - `GET /signup` → shop name + admin email + password
   - Creates Shop, User, generates license
   - Redirects to dashboard

5. **Docker Compose** for cloud deployment
   - `docker-compose.yml`: dashboard, postgresql, caddy
   - Environment variables for secrets

## Todo List

- [ ] Make database engine configurable (SQLite or PostgreSQL)
- [ ] Add `psycopg2-binary` optional dependency
- [ ] Remove SQLite-specific pragmas when using PostgreSQL
- [ ] Caddy config template
- [ ] Docker Compose for cloud
- [ ] Cloud signup flow
- [ ] Test multi-worker mode
- [ ] Load test with multiple shops

## Success Criteria

- Same dashboard binary runs self-hosted (SQLite) or cloud (PostgreSQL)
- Multiple shops on cloud instance cannot see each other's data
- HTTPS works with auto-renewed Let's Encrypt certificates
- Agent on customer LAN connects to cloud dashboard over HTTPS
