# Phase 3 — Licensing System

## Context Links
- Agent config: `packages/common/src/common/config.py`
- Agent main: `packages/agent/src/agent/main.py`
- AES crypto already available: `packages/common/src/common/protocols/hsrp_crypto.py`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 4d
- **Description**: Offline-first per-printer licensing. License key file validated locally, optional online check. Grace period when license server unreachable.

## Key Insights

Print shops have unreliable internet. License validation MUST work offline. Online validation is a bonus for anti-piracy, not a requirement for operation.

**Chosen approach: Signed license file (JWT-like)**. Dashboard/server generates a JSON license signed with Ed25519. Agent validates signature with embedded public key. No online check required for basic validation.

This is simpler than hardware fingerprinting (printer PCs get replaced), more reliable than online-only validation, and harder to crack than a simple serial key.

## Requirements

### Functional
- License key = signed JSON file (`license.json`) placed in agent install directory
- Contains: `shop_id`, `max_printers`, `expires_at`, `features[]`, `issued_at`
- Agent validates signature on startup using embedded public key
- If valid: agent runs normally
- If expired: 7-day grace period with warning banner, then agent stops accepting new jobs (existing jobs finish)
- If invalid/missing: agent runs in "demo mode" (5 jobs/day limit, watermark in logs)
- Optional online check: agent pings license server daily for revocation list
- Dashboard shows license status (valid/expiring/expired/demo)

### Non-Functional
- License file is human-readable JSON (easy to email/share)
- Signature prevents tampering (can't edit max_printers)
- Public key embedded in agent binary — no separate key distribution
- License generation is a CLI tool or admin API endpoint (not in agent)

## Architecture

```
License generation (your server / CLI tool):
  1. Create JSON payload: {shop_id, max_printers, expires_at, features}
  2. Sign with Ed25519 private key
  3. Output: license.json = {payload: {...}, signature: "base64..."}

Agent startup:
  1. Read license.json from install directory
  2. Verify Ed25519 signature using embedded public key
  3. Check expiry date
  4. If valid: proceed
  5. If expired < 7 days: proceed with warning
  6. If expired > 7 days: demo mode
  7. If invalid signature: demo mode
  8. If missing: demo mode

Optional online check (daily):
  1. POST license-server.printflow.com/api/validate
     Body: {license_id, shop_id, agent_version}
  2. Server responds: {valid: true, revoked: false}
  3. If revoked: enter demo mode
  4. If server unreachable: ignore, use cached result
```

### License File Format

```json
{
  "payload": {
    "license_id": "LIC-2026-001",
    "shop_id": "SHOP-ABC123",
    "shop_name": "Quick Print Co",
    "max_printers": 5,
    "issued_at": "2026-03-23T00:00:00Z",
    "expires_at": "2027-03-23T00:00:00Z",
    "features": ["dtg", "dtf", "analytics"],
    "edition": "professional"
  },
  "signature": "base64-ed25519-signature..."
}
```

## Related Code Files

### Create
- `packages/common/src/common/licensing/license_model.py` — Pydantic model for license payload
- `packages/common/src/common/licensing/license_validator.py` — signature verification, expiry check, grace period logic
- `packages/common/src/common/licensing/__init__.py`
- `packages/agent/src/agent/license_check.py` — startup license validation, periodic re-check
- `scripts/generate-license.py` — CLI tool to sign license files (uses private key)

### Modify
- `packages/agent/src/agent/main.py` — call license check before starting, inject license status into backend
- `packages/agent/src/agent/api.py` — add `GET /license` endpoint for dashboard to query
- `packages/common/src/common/config.py` — add `license_path` config field
- `packages/dashboard/src/dashboard/api/printers.py` — fetch and display license status from agents
- `packages/dashboard/src/dashboard/templates/printers.html` — license status badge per printer

## Implementation Steps

1. **License model** (`common/licensing/license_model.py`)
   - Pydantic model: `LicensePayload` with fields above
   - `LicenseFile` model: `{payload: LicensePayload, signature: str}`
   - `LicenseStatus` enum: `VALID`, `EXPIRING`, `EXPIRED`, `INVALID`, `DEMO`

2. **License validator** (`common/licensing/license_validator.py`)
   - Embed Ed25519 public key as constant
   - `validate_license(license_path: Path) -> LicenseResult`
   - Returns: `LicenseResult(status, payload, days_remaining, message)`
   - Grace period logic: expired < 7 days = EXPIRING, > 7 days = EXPIRED

3. **License generator script** (`scripts/generate-license.py`)
   - CLI: `python generate-license.py --shop-id SHOP-ABC --max-printers 5 --expires 2027-03-23 --out license.json`
   - Reads Ed25519 private key from env var or file
   - Signs payload, outputs license.json
   - Private key NEVER shipped in agent; kept on your build server only

4. **Agent license check** (`agent/license_check.py`)
   - Called from `main.py` before `uvicorn.run()`
   - If DEMO mode: log warning, set job limit (5/day)
   - If EXPIRING: log warning with days remaining
   - If EXPIRED: log error, disable new job injection
   - Expose status via `GET /license` endpoint

5. **Demo mode enforcement**
   - In `agent/api.py` `inject_job()`: check license status
   - If DEMO: count jobs today, reject if > 5
   - If EXPIRED (past grace): reject all new jobs with 403
   - Existing running jobs always allowed to finish

6. **Dashboard license display**
   - When polling agents, also fetch `GET /license` from each
   - Show badge on printer card: green (valid), yellow (expiring X days), red (expired/demo)

7. **Optional online validation** (can defer to v2)
   - Daily background task in agent
   - POST to license server with license_id
   - Cache response locally (last_online_check.json)
   - If revoked: enter demo mode

## Todo List

- [ ] Create `common/licensing/license_model.py`
- [ ] Create `common/licensing/license_validator.py`
- [ ] Generate Ed25519 keypair, embed public key in validator
- [ ] Create `scripts/generate-license.py`
- [ ] Create `agent/license_check.py`
- [ ] Add `GET /license` endpoint to agent API
- [ ] Enforce demo mode limits in `inject_job()`
- [ ] Add `license_path` to AgentConfig
- [ ] Update agent `main.py` — license check on startup
- [ ] Dashboard: fetch + display license status
- [ ] Tests: valid license passes, expired fails, tampered signature fails
- [ ] Tests: demo mode job limit enforced
- [ ] Tests: grace period logic (day 1-7 warning, day 8+ blocked)

## Success Criteria

- Valid license.json: agent starts normally, no restrictions
- Expired < 7 days: agent works with warning in logs + dashboard badge
- Expired > 7 days: agent rejects new jobs, shows "License Expired" in dashboard
- Missing/tampered license: demo mode (5 jobs/day)
- License file is portable — works on any PC (not hardware-locked)

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Private key leaked | Anyone can forge licenses | Keep private key on airgapped or HSM-protected build server |
| Customer loses license file | Can't use software | License reissue process via support portal |
| Clock manipulation to bypass expiry | Piracy | Optional online check; for MVP, accept this risk |
| PyInstaller decompilation reveals public key | N/A | Public key is meant to be public; private key signs |

## Security Considerations

- Ed25519 signature = cryptographically strong, fast, small keys
- Public key in source is fine — it can only verify, not sign
- Private key stored separately (env var, secrets manager, HSM)
- License file JSON is readable — intentional for transparency
- No phone-home required — respect customer privacy
