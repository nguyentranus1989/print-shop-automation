# Phase 5 — Agent Installer

## Context Links
- Agent main: `packages/agent/src/agent/main.py`
- Agent config: `packages/common/src/common/config.py`
- Tech stack (PyInstaller + NSSM): `docs/tech-stack.md` (section 10)
- Phase 3 (prerequisite): `./phase-03-licensing-system.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 4d
- **Description**: One-click Windows installer (.exe) that bundles Python runtime, agent code, NSSM for Windows service, and a configuration wizard. User enters printer name, dashboard URL, license key, and the agent starts running as a background service.

## Key Insights

Target users are print shop operators, not developers. Installation must be:
1. Download .exe
2. Double-click
3. Fill in 3-4 fields
4. Done — agent runs as Windows service

PyInstaller bundles Python + agent into a single .exe. NSSM wraps it as a Windows service. Inno Setup creates the installer wizard.

## Requirements

### Functional
- Installer is a single `.exe` file (~30-50MB)
- Configuration wizard (GUI): printer name, dashboard URL/IP, license key file, agent port
- Installs to `C:\Program Files\PrintFlow Agent\`
- Registers Windows service `PrintFlowAgent` via NSSM
- Service auto-starts on boot, restarts on crash
- Creates `agent.toml` from wizard inputs
- Copies `license.json` from user-selected path to install dir
- System tray icon (optional, v2) — shows agent status
- Uninstaller: stops service, removes NSSM entry, deletes install dir

### Non-Functional
- Works on Windows 10 and 11
- No admin rights needed for agent code, but service registration needs elevation (installer prompts UAC)
- Install time < 60 seconds
- Agent binary size < 50MB (PyInstaller with UPX compression)

## Architecture

```
Build pipeline:
  1. uv build → packages/agent wheel
  2. PyInstaller --onefile agent/__main__.py → printflow-agent.exe
  3. Bundle: printflow-agent.exe + nssm.exe + default agent.toml
  4. Inno Setup compiles all into PrintFlowAgentSetup-1.0.0.exe

Install flow:
  1. User runs PrintFlowAgentSetup-1.0.0.exe
  2. UAC prompt (needs admin for service registration)
  3. Wizard page 1: Welcome
  4. Wizard page 2: License agreement
  5. Wizard page 3: Configuration
     - Printer name: [text input, default: hostname]
     - Dashboard URL: [text input, default: http://192.168.1.100:8000]
     - License file: [file picker for license.json]
     - Agent port: [number input, default: 8080]
  6. Wizard page 4: Install location (default: C:\Program Files\PrintFlow Agent)
  7. Install: extract files, write agent.toml, register service
  8. Wizard page 5: Done — "Agent is running. Visit dashboard to verify."

Runtime:
  Windows boots → NSSM starts PrintFlowAgent service
  Service runs: printflow-agent.exe (reads agent.toml from same dir)
  On crash: NSSM restarts after 5 seconds
  Logs: written to install_dir\logs\ (rotated daily)
```

## Related Code Files

### Create
- `installer/build-agent.py` — PyInstaller build script
- `installer/printflow-agent.iss` — Inno Setup script
- `installer/nssm.exe` — bundled NSSM binary (MIT license)
- `installer/default-agent.toml` — template config
- `scripts/build-installer.sh` — end-to-end build (uv build → PyInstaller → Inno Setup)

### Modify
- `packages/agent/src/agent/main.py` — support `--install-service` and `--uninstall-service` flags
- `packages/common/src/common/config.py` — resolve config path relative to exe location (not CWD)
- `pyproject.toml` — add pyinstaller to dev dependencies

## Implementation Steps

1. **PyInstaller spec file** (`installer/build-agent.py`)
   - One-file mode: `--onefile`
   - Hidden imports: all agent dependencies
   - Include data: `agent.toml.example`
   - UPX compression for smaller binary
   - Test: `printflow-agent.exe --mock` works standalone

2. **NSSM integration**
   - Bundle `nssm.exe` (64-bit, MIT licensed, ~300KB)
   - Service registration command:
     ```
     nssm install PrintFlowAgent "C:\Program Files\PrintFlow Agent\printflow-agent.exe"
     nssm set PrintFlowAgent AppDirectory "C:\Program Files\PrintFlow Agent"
     nssm set PrintFlowAgent AppStdout "C:\Program Files\PrintFlow Agent\logs\stdout.log"
     nssm set PrintFlowAgent AppStderr "C:\Program Files\PrintFlow Agent\logs\stderr.log"
     nssm set PrintFlowAgent AppRotateFiles 1
     nssm set PrintFlowAgent AppRotateBytes 10485760
     nssm set PrintFlowAgent AppRestartDelay 5000
     nssm start PrintFlowAgent
     ```

3. **Inno Setup script** (`installer/printflow-agent.iss`)
   - Pages: Welcome, License (EULA), Configuration (custom page), Directory, Install, Finish
   - Custom config page with Pascal script for form fields
   - Post-install: write `agent.toml` from form inputs, run NSSM install commands
   - Uninstall: stop service, `nssm remove PrintFlowAgent confirm`, delete files

4. **Config path resolution**
   - When running as `.exe`, config path = directory of executable
   - `AgentConfig.load()` should check `Path(sys.executable).parent / "agent.toml"` for frozen mode
   - `sys.frozen` attribute detection for PyInstaller bundles

5. **Logging setup**
   - Agent writes logs to `{install_dir}/logs/`
   - NSSM handles stdout/stderr rotation
   - Add file handler in `main.py` alongside console output

6. **Build automation script**
   ```bash
   #!/bin/bash
   # scripts/build-installer.sh
   uv sync
   uv run pyinstaller installer/build-agent.py
   iscc installer/printflow-agent.iss  # Inno Setup CLI
   # Output: dist/PrintFlowAgentSetup-1.0.0.exe
   ```

7. **Test installer on clean Windows VM**
   - Fresh Windows 10 VM, no Python installed
   - Run installer, fill wizard
   - Verify service starts, agent accessible on port
   - Reboot, verify service auto-starts
   - Run uninstaller, verify clean removal

## Todo List

- [ ] Create PyInstaller spec file
- [ ] Test standalone .exe with `--mock`
- [ ] Bundle NSSM binary
- [ ] Write Inno Setup script with custom config page
- [ ] Implement config path resolution for frozen mode
- [ ] Add logging to file
- [ ] Create build automation script
- [ ] Test on clean Windows 10 VM
- [ ] Test on clean Windows 11 VM
- [ ] Test uninstaller — clean removal
- [ ] Test service restart on crash
- [ ] Document installer build process

## Success Criteria

- Download single .exe, double-click, fill 3 fields, agent running as service within 60s
- Service survives reboot (auto-start)
- Service restarts on crash (within 5s)
- Uninstaller cleanly removes everything
- Works on Windows 10 and 11 without pre-installed Python

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| PyInstaller false positive antivirus | Users can't install | Sign .exe with code signing certificate ($200-400/yr); whitelist guide |
| NSSM version conflicts | Service management issues | Bundle specific NSSM version (2.24), don't rely on system NSSM |
| Large binary size | Slow download | UPX compression; host on CDN; provide torrent/mirror |
| Inno Setup custom pages complex | Delayed delivery | Start with minimal wizard (3 text fields), add polish later |
| Windows Defender SmartScreen block | Scary warning for users | Code signing certificate solves this; EV cert removes warning |

## Security Considerations

- Code signing certificate: essential for commercial distribution (avoid SmartScreen/antivirus)
- Installer requests UAC elevation only for service registration
- Agent runs as SYSTEM or LOCAL SERVICE (no user session required)
- License file validated before service start
- No network calls during install (offline-friendly)
