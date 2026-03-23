# Phase 7 — Dashboard Auth & RBAC

## Context Links
- Dashboard main: `packages/dashboard/src/dashboard/main.py`
- DB models: `packages/dashboard/src/dashboard/db/models.py`
- Templates: `packages/dashboard/src/dashboard/templates/`
- Phase 4 (prerequisite): `./phase-04-multi-shop-data-isolation.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Login page for dashboard, session-based auth, admin/operator roles. Protects the web UI from unauthorized access.

## Key Insights

Dashboard currently has no login — anyone on the LAN can access it. For commercial: need user accounts with passwords, session cookies, and two roles.

**Keep it simple**: no OAuth2, no external identity provider. Local username/password stored in SQLite (hashed with bcrypt). Session cookie with HMAC signature. This is sufficient for self-hosted LAN deployments. Cloud mode can add OAuth2 later.

**Two roles**:
- **Admin**: full access (add/remove printers, manage users, view all data, config)
- **Operator**: view dashboard, submit jobs, control printers (no user management, no config)

## Requirements

### Functional
- Login page: username + password form
- First-run setup: create admin account (no default passwords)
- Session cookie: HttpOnly, SameSite=Lax, configurable expiry (default 8h)
- Admin can: create/delete users, assign roles, manage printers, generate API keys
- Operator can: view dashboard, submit/cancel jobs, send printer commands
- Logout button in nav
- Password change (any user can change their own)
- Admin password reset (admin resets operator passwords)
- Session timeout: auto-logout after 8h of inactivity

### Non-Functional
- Passwords hashed with bcrypt (cost factor 12)
- Session cookie signed with HMAC-SHA256 (secret from env or generated on first run)
- Rate-limit login: 5 attempts per 15 minutes per IP (prevent brute force)
- No remember-me (security-first for print shop environments)

## Architecture

```
Models:
  User(id, username, password_hash, role, shop_id, created_at, last_login)
  Session table or signed cookie (cookie is simpler)

Login flow:
  1. GET /login → render login.html
  2. POST /login {username, password}
  3. Verify password hash
  4. Create signed session cookie: {user_id, shop_id, role, exp}
  5. Redirect to /

Protected routes:
  1. Middleware checks session cookie on every request
  2. If missing/invalid → redirect to /login
  3. If expired → redirect to /login
  4. If valid → inject user context (user_id, shop_id, role)

RBAC:
  @require_role("admin") decorator on admin-only endpoints
  Operator blocked from: user management, printer deletion, API key generation
```

## Related Code Files

### Create
- `packages/dashboard/src/dashboard/db/user_model.py` — User SQLAlchemy model
- `packages/dashboard/src/dashboard/auth/session.py` — cookie signing, validation, middleware
- `packages/dashboard/src/dashboard/auth/password.py` — bcrypt hashing, verification
- `packages/dashboard/src/dashboard/auth/rbac.py` — role-checking dependency
- `packages/dashboard/src/dashboard/auth/__init__.py`
- `packages/dashboard/src/dashboard/api/users.py` — user CRUD endpoints
- `packages/dashboard/src/dashboard/templates/login.html` — login page
- `packages/dashboard/src/dashboard/templates/setup.html` — first-run admin creation
- `packages/dashboard/src/dashboard/templates/_partial-user-management.html` — admin user list

### Modify
- `packages/dashboard/src/dashboard/main.py` — add auth middleware, login/logout routes
- `packages/dashboard/src/dashboard/db/database.py` — import user model for create_all
- `packages/dashboard/src/dashboard/templates/base.html` — add user info in nav, logout button
- `packages/dashboard/pyproject.toml` — add `bcrypt` dependency

## Implementation Steps

1. **User model** (`db/user_model.py`)
   ```python
   class User(Base):
       __tablename__ = "users"
       id: Mapped[int] = primary key
       username: Mapped[str] = unique, max 50
       password_hash: Mapped[str] = String(128)
       role: Mapped[str] = "admin" | "operator"
       shop_id: Mapped[int] = FK to shops
       created_at: Mapped[datetime]
       last_login: Mapped[datetime | None]
   ```

2. **Password utilities** (`auth/password.py`)
   - `hash_password(plain: str) -> str` — bcrypt hash, cost 12
   - `verify_password(plain: str, hashed: str) -> bool` — bcrypt verify

3. **Session management** (`auth/session.py`)
   - Signed cookie approach (no server-side session table)
   - Cookie payload: `{user_id, shop_id, role, username, exp}`
   - Sign with HMAC-SHA256 using `SESSION_SECRET` env var (or auto-generated on first run, saved to config)
   - `create_session(response, user) -> None` — set cookie
   - `get_current_user(request) -> UserSession | None` — parse + verify cookie
   - `require_auth` — FastAPI dependency, redirects to /login if no valid session

4. **RBAC dependency** (`auth/rbac.py`)
   - `require_role(role: str)` — FastAPI dependency
   - Checks `current_user.role` against required role
   - Returns 403 if insufficient permissions

5. **Login routes** (in `main.py` or separate router)
   - `GET /login` — render login.html
   - `POST /login` — validate credentials, set cookie, redirect to /
   - `POST /logout` — clear cookie, redirect to /login
   - `GET /setup` — first-run page (only if no users exist)
   - `POST /setup` — create first admin user

6. **Auth middleware**
   - Applied to all routes except: /login, /setup, /health, /static
   - API routes (`/api/*`): return 401 JSON if not authenticated
   - HTML routes: redirect to /login

7. **User management API** (`api/users.py`)
   - `GET /api/users` — list users (admin only)
   - `POST /api/users` — create user (admin only)
   - `DELETE /api/users/{id}` — delete user (admin only, can't delete self)
   - `PATCH /api/users/{id}/password` — change password (self or admin)

8. **Login page template** (`login.html`)
   - Centered card with username/password fields
   - Error message for invalid credentials
   - Follows existing dark theme design guidelines

9. **First-run setup page** (`setup.html`)
   - Only accessible if zero users in DB
   - Create admin username + password + confirm password
   - Redirects to /login after creation

## Todo List

- [ ] Add `bcrypt` to dashboard dependencies
- [ ] Create User model + migration
- [ ] Create `auth/password.py`
- [ ] Create `auth/session.py` — cookie signing
- [ ] Create `auth/rbac.py` — role dependency
- [ ] Add login/logout routes
- [ ] Add first-run setup route
- [ ] Create `login.html` template
- [ ] Create `setup.html` template
- [ ] Auth middleware on all routes
- [ ] User management API (admin only)
- [ ] Add user info + logout to `base.html` nav
- [ ] Rate-limit login attempts
- [ ] Tests: login with valid/invalid credentials
- [ ] Tests: RBAC — operator blocked from admin routes
- [ ] Tests: session expiry

## Success Criteria

- First run: redirected to setup page to create admin account
- Login required: unauthenticated access to / redirects to /login
- Admin can create operator accounts
- Operator cannot access user management
- Session expires after 8h
- 5 failed login attempts: temporary lockout

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| SESSION_SECRET lost on reinstall | All sessions invalidated | Auto-regenerate is fine (users just re-login) |
| Brute force login | Account compromise | Rate limiting (5 attempts / 15 min) |
| Cookie stolen (HTTP, not HTTPS) | Session hijack | HttpOnly + SameSite; HTTPS in Phase 8 |
| Admin forgets password | Locked out | CLI tool: `printflow-dashboard reset-admin-password` |

## Security Considerations

- bcrypt with cost 12: 200-300ms per hash (intentionally slow for brute force resistance)
- HttpOnly cookie: not accessible to JavaScript (XSS mitigation)
- SameSite=Lax: CSRF protection for GET requests
- CSRF token for POST forms (HTMX compatible)
- No default admin password — forced setup on first run
- Password minimum: 8 characters (enforced server-side)
