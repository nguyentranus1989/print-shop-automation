# Phase 4 — Multi-Shop Data Isolation

## Context Links
- DB models: `packages/dashboard/src/dashboard/db/models.py`
- Database: `packages/dashboard/src/dashboard/db/database.py`
- Jobs API: `packages/dashboard/src/dashboard/api/jobs.py`
- Printers API: `packages/dashboard/src/dashboard/api/printers.py`
- Analytics API: `packages/dashboard/src/dashboard/api/analytics.py`
- Phase 1 (prerequisite): `./phase-01-persistent-printer-registry.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Add `shop_id` foreign key to all data tables. Scope all queries to the active shop. Enables self-hosted (single shop) and cloud-hosted (multi-shop) deployment from same codebase.

## Key Insights

For self-hosted: single shop, `shop_id` is always the same value. Minor overhead.
For cloud-hosted: multiple shops share one database instance but MUST NOT see each other's data.

**Strategy: application-level row filtering** (not separate databases per tenant). Simpler, works with SQLite for self-hosted and PostgreSQL for cloud.

All queries go through a `shop_id` filter. A missed filter = data leak. Safeguard: SQLAlchemy event listener that raises if a query on a tenanted table lacks `shop_id` in its WHERE clause (dev-mode only).

## Requirements

### Functional
- New `shops` table: `{id, name, slug, created_at, license_id}`
- `shop_id` FK added to: `printers`, `jobs`, `ink_usage`, `print_events`
- All list/query endpoints accept `shop_id` from auth context (not URL param)
- Self-hosted mode: auto-create single shop on first run, all data scoped to it
- Cloud mode: shop_id derived from authenticated user's session

### Non-Functional
- All existing data migrated with a default shop_id
- Index on `shop_id` for all tenanted tables
- Query safety: dev-mode assertion that tenanted queries include shop_id filter

## Architecture

```
Self-hosted:
  First startup → create default Shop (id=1, name from config)
  All queries: WHERE shop_id = 1 (implicit, from config)

Cloud-hosted:
  User logs in → session contains shop_id
  All queries: WHERE shop_id = session.shop_id
  Admin panel: can see all shops

Shared logic:
  get_shop_id() dependency → returns shop_id from:
    1. Request session (cloud)
    2. Config file (self-hosted)
```

## Related Code Files

### Modify
- `packages/dashboard/src/dashboard/db/models.py` — add Shop model, add shop_id FK to all models
- `packages/dashboard/src/dashboard/db/database.py` — add shop_id session scope helper
- `packages/dashboard/src/dashboard/api/printers.py` — scope queries to shop_id
- `packages/dashboard/src/dashboard/api/jobs.py` — scope queries to shop_id
- `packages/dashboard/src/dashboard/api/analytics.py` — scope queries to shop_id
- `packages/dashboard/src/dashboard/services/job_queue.py` — add shop_id to job creation and queries
- `packages/dashboard/src/dashboard/services/agent_manager.py` — scope polling to shop's printers only

### Create
- `packages/dashboard/src/dashboard/db/tenant.py` — `get_shop_id()` dependency, shop creation

## Implementation Steps

1. **Create Shop model**
   ```python
   class Shop(Base):
       __tablename__ = "shops"
       id: Mapped[int] = mapped_column(Integer, primary_key=True)
       name: Mapped[str] = mapped_column(String(200), nullable=False)
       slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
       license_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
       created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
   ```

2. **Add `shop_id` FK to all tenanted models**
   - `Printer.shop_id` — FK to shops.id, NOT NULL, indexed
   - `Job.shop_id` — FK to shops.id, NOT NULL, indexed
   - `InkUsage.shop_id` — FK to shops.id, NOT NULL, indexed
   - `PrintEvent.shop_id` — FK to shops.id, NOT NULL, indexed

3. **Create tenant helper** (`db/tenant.py`)
   - `get_shop_id(request: Request) -> int` — FastAPI dependency
   - Self-hosted: reads from config or returns default shop ID (1)
   - Cloud: reads from request session (set during login in Phase 7)
   - `ensure_default_shop(db: Session)` — creates shop with id=1 if none exists

4. **Scope all API queries**
   - Every list endpoint: `.filter(Model.shop_id == shop_id)`
   - Every create endpoint: set `shop_id` on new records
   - Every detail/update/delete: verify record belongs to requesting shop

5. **Alembic migration**
   - Add `shops` table
   - Add `shop_id` column (nullable initially) to printers, jobs, ink_usage, print_events
   - Data migration: set `shop_id = 1` for all existing rows
   - Alter to NOT NULL
   - Add indexes

6. **Update AgentManager**
   - When cloud-hosted, AgentManager needs per-shop polling
   - Self-hosted: single manager instance (unchanged behavior)
   - Cloud: manager loads only printers for its shop

7. **Dev-mode safety net**
   - SQLAlchemy `before_execute` event
   - In DEBUG mode: check that queries on tenanted tables include `shop_id` filter
   - Log warning (or raise) if missing — catches data leak bugs early

## Todo List

- [ ] Create `Shop` model
- [ ] Add `shop_id` FK to Printer, Job, InkUsage, PrintEvent
- [ ] Create Alembic migration
- [ ] Create `db/tenant.py` with `get_shop_id()` dependency
- [ ] Update `printers.py` — scope all queries
- [ ] Update `jobs.py` — scope all queries + creation
- [ ] Update `analytics.py` — scope all queries
- [ ] Update `job_queue.py` — add shop_id to operations
- [ ] Update `agent_manager.py` — shop-scoped polling
- [ ] Auto-create default shop on first startup
- [ ] Dev-mode tenant query safety check
- [ ] Tests: shop A cannot see shop B's data
- [ ] Tests: default shop auto-created

## Success Criteria

- Self-hosted: behaves identically to before (transparent shop_id=1)
- Two shops in DB: each only sees their own printers/jobs/analytics
- Creating a job for shop A does not appear in shop B's job list
- Missing shop_id in query triggers dev-mode warning

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Missed shop_id filter on a query | Data leak between shops | Dev-mode query assertion + code review checklist |
| Migration breaks existing installations | Data loss | Reversible migration; backup DB before running |
| Performance with many shops in one DB | Slow queries | Indexed shop_id columns; PostgreSQL for cloud |

## Security Considerations

- shop_id from auth session — never from client-supplied param
- Admin role can see all shops (Phase 7)
- API responses never include shop_id in JSON (internal detail)
- Cross-shop data access = critical security bug — treat as P1
