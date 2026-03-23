# Phase 9 — Telemetry & Support (v2)

## Context Links
- Agent API: `packages/agent/src/agent/api.py`
- Agent main: `packages/agent/src/agent/main.py`

## Overview
- **Priority**: P2 (v2)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Anonymous usage telemetry, crash reporting, remote diagnostics for customer support.

## Key Insights

Telemetry must be opt-in or clearly disclosed. Print shops handle private orders — respect that. Only collect operational metrics (printer type, job count, error rates), never job content or customer data.

## Requirements

### Functional
- Agent sends daily anonymous report: printer type, job count (24h), error count, agent version, uptime
- Crash reporting: on unhandled exception, send stack trace to Sentry (or self-hosted equivalent)
- Remote diagnostics: support team can request logs from agent via dashboard API
- Opt-out: config flag `telemetry = false` disables all external reporting
- Dashboard shows telemetry status (enabled/disabled) per agent

### Non-Functional
- Telemetry payload < 1KB per report
- No PII (no job names, no filenames, no IP addresses)
- HTTPS only for telemetry endpoint
- Crash reports include: stack trace, agent version, OS version, Python version

## Implementation Steps

1. **Telemetry module** (`agent/telemetry.py`)
   - Daily async task: collect metrics, POST to telemetry endpoint
   - Payload: `{agent_id_hash, printer_type, jobs_24h, errors_24h, version, uptime_hours}`
   - `agent_id_hash`: SHA-256 of machine ID (not reversible to identity)

2. **Crash reporting**
   - Wrap main entry point in try/except
   - On crash: POST stack trace to error endpoint
   - Use `sentry_sdk` (optional dependency) or simple HTTP POST

3. **Remote log access**
   - `GET /api/agent/logs?lines=100` — returns last N lines of agent log
   - Auth-protected (Phase 2 API key required)
   - Dashboard admin can view agent logs remotely

4. **Opt-out config**
   - `agent.toml`: `[telemetry] enabled = true`
   - If false: no external HTTP calls for telemetry/crash reporting
   - Log access still works (it's authenticated, not telemetry)

## Todo List

- [ ] Create `agent/telemetry.py`
- [ ] Daily telemetry task
- [ ] Crash reporting integration
- [ ] `GET /api/agent/logs` endpoint
- [ ] Config opt-out flag
- [ ] Privacy policy documenting what's collected
- [ ] Tests: telemetry disabled → no HTTP calls
