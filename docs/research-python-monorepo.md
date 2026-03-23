# Python Monorepo with uv Workspaces — Research Report

**Date:** 2026-03-22
**Scope:** uv workspace setup, FastAPI+Jinja2+HTMX, SQLAlchemy+SQLite, PyInstaller Windows services, NSSM integration

---

## 1. UV Workspace Setup

**Structure:** Root `pyproject.toml` defines `[tool.uv.workspace]` with `members` (glob patterns) and optional `exclude` keys. Each package has its own `pyproject.toml`.

**Cross-package deps:** Use `[tool.uv.sources]` with `{ workspace = true }` flag. Single shared lockfile enforces dependency consistency across all members.

**Example:**
```toml
[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[project.dependencies]
shared-lib = { workspace = true }
```

**Key insight:** Workspaces enforce isolation (separate concerns per package) while maintaining monorepo consistency. Ideal for internal tools with shared core + specialized modules.

---

## 2. FastAPI + Jinja2 + HTMX Patterns

**Core approach:** Return HTML fragments from endpoints, HTMX swaps them into DOM. Server-rendered hypermedia replaces JSON/client-side React-style rendering.

**Best practices:**
- Organize templates: root templates in `/templates`, reusable components in `/templates/partials/`
- Always declare `Request` param in path operations; pass to `TemplateResponse()`
- Use libraries like `fasthx` or `fastapi-htmx` to reduce boilerplate with decorators
- Progressive enhancement: HTMX enhances existing server-rendered pages

**Advantage:** Minimal client-side logic, SPA-like UX with less JavaScript, faster page loads.

**Setup:**
```python
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
```

---

## 3. SQLAlchemy + SQLite Best Practices

**Async vs Sync:**
- **Async:** Use `create_async_engine("sqlite+aiosqlite://...")`, `async_sessionmaker`. Set `expire_on_commit=False`.
- **Sync:** Standard `create_engine("sqlite://...")`. Simpler but blocks on I/O.
- **Mixed:** Use `AsyncSession.run_sync()` to run sync functions inside async context if needed.

**WAL Mode (Write-Ahead Logging):** Enable via event listener:
```python
from sqlalchemy import event
event.listen(engine.sync_engine, "connect",
             lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA journal_mode=WAL"))
```
Improves concurrency; important for sqlite in production.

**Session management:** Async sessions require explicit `await commit()`. Use context managers for cleanup.

---

## 4. PyInstaller → Windows Service: Gotchas

**Critical issues:**
- **Hidden imports:** PyInstaller misses transitive deps (e.g., `win32timezone`). Use `--hidden-import` flags per build; requires trial-and-error.
- **Error 1053:** Service doesn't respond in time. Often caused by missing imports or slow startup.
- **Auto-start failures:** Service may stay stopped even if code runs manually. Manually start after deployment.
- **Antivirus:** Whitelist entire output directory to prevent blacklisting.
- **PyInstaller bugs:** Use develop branch for newer bugfixes; version mismatch with dependencies can break builds.

---

## 5. Windows Service Patterns + NSSM

**NSSM advantages:** Non-Sucking Service Manager is simpler than winreg/win32api approaches. Wraps any executable + args as a service.

**Auto-restart:**
- Default: NSSM monitors process, restarts if it dies. Throttles rapid restarts (default 1500ms threshold).
- Configure delay: Registry `HKLM\...\Services\servicename\Parameters\AppRestartDelay` (milliseconds).
- Configure action: `AppExit` key — set to `Restart` (default), `Ignore`, or `Exit`.

**Startup:** Auto-start enabled by default. Service runs under Local System account unless configured otherwise.

**Flow:**
1. Build exe with PyInstaller: `pyinstaller --onefile --hidden-import win32timezone app.py`
2. Install with NSSM: `nssm install MyService C:\path\to\app.exe`
3. Configure: `nssm set MyService AppRestartDelay 5000`
4. Start: `nssm start MyService`

---

## Summary

**uv workspaces** enable monorepo isolation with shared lockfile. **FastAPI+HTMX** delivers interactive UIs with server-side logic. **Async SQLAlchemy+SQLite** supports concurrency via WAL mode. **PyInstaller+NSSM** packages Python as Windows services, but requires hidden-import vigilance and antivirus whitelisting.

**Recommendation for internal tools:** uv workspace + FastAPI (sync is simpler unless IO-heavy) + sync SQLAlchemy (simpler than async for SQLite) + NSSM-wrapped PyInstaller executable.

---

## Sources

- [uv Workspace Documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [Building Python Monorepos with uv (Feb 2026)](https://medium.com/@naorcho/building-a-python-monorepo-with-uv-the-modern-way-to-manage-multi-package-projects-4cbcc56df1b4)
- [FastAPI + HTMX: Hypermedia-Driven Applications](https://medium.com/@strasbourgwebsolutions/fastapi-as-a-hypermedia-driven-application-w-htmx-jinja2templates-644c3bfa51d1)
- [HTMX with FastAPI — TestDriven.io](https://testdriven.io/blog/fastapi-htmx/)
- [SQLAlchemy 2.0 Async I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy + FastAPI Users Configuration](https://fastapi-users.github.io/fastapi-users/latest/configuration/databases/sqlalchemy/)
- [PyInstaller + Windows Services Guide](https://metallapan.se/post/windows-service-pywin32-pyinstaller/)
- [NSSM Non-Sucking Service Manager](http://nssm.cc/usage)
- [NSSM Auto-Restart Configuration](https://www.skedler.com/blog/how-to-configure-auto-restart-of-skedler-service-in-windows-using-nssm/)
