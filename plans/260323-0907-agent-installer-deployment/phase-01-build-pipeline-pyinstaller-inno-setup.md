# Phase 1 -- Build Pipeline (PyInstaller + Inno Setup)

## Context Links
- Agent main: `packages/agent/src/agent/main.py`
- Agent config: `packages/common/src/common/config.py`
- Agent pyproject: `packages/agent/pyproject.toml`
- Tech stack packaging section: `docs/tech-stack.md` (section 10)
- Existing commercialization plan: `plans/260323-printflow-commercialization/phase-05-agent-installer.md`

## Overview
- **Priority**: P1 (MVP)
- **Status**: Pending
- **Effort**: 3d
- **Description**: Build a complete pipeline that takes the agent Python package, bundles it into a standalone .exe via PyInstaller, then wraps it with NSSM and a configuration wizard using Inno Setup to produce a single `PrintFlowAgentSetup-X.Y.Z.exe`.

## Key Insights

1. **PyInstaller `--onefile` vs `--onedir`**: Use `--onedir` for production. `--onefile` extracts to temp on every launch (slow startup, ~5-10s), antivirus scans every extraction, and prevents in-place binary updates. `--onedir` extracts once at install time, starts instantly, and allows single-file replacement for updates.

2. **NSSM vs pywin32 serviceutil**: NSSM is the right choice. It wraps any .exe as a service without code changes to the agent. pywin32 would require rewriting main.py as a service class. NSSM handles restart-on-crash, log rotation, and graceful shutdown natively.

3. **Inno Setup vs NSIS**: Inno Setup recommended. Pascal-based scripting is simpler for custom config pages. Better documentation. NSIS is more powerful but requires learning its assembly-like scripting. Both produce ~1MB overhead.

4. **Frozen path resolution**: When PyInstaller bundles the app, `sys.executable` points to the .exe, not the Python interpreter. `__file__` paths resolve to temp extraction dirs in `--onefile` mode. Must handle `sys.frozen` attribute to resolve config/data paths relative to the install directory.

5. **Hidden imports**: FastAPI, uvicorn, pydantic, and SQLAlchemy all have dynamic imports that PyInstaller can't detect. Must explicitly list hidden imports in the spec file.

## Requirements

### Functional
- Single `PrintFlowAgentSetup-X.Y.Z.exe` installer file (~40-60MB)
- Installer wizard with 5 pages: Welcome, EULA, Config, Directory, Finish
- Config page collects: printer name, PrintExp path (auto-detect + browse), dashboard URL, license key, agent port
- Auto-detect PrintExp by scanning common paths: `C:\PrintExp*\PrintExp.exe`, `D:\PrintExp*\PrintExp.exe`
- Installs to `C:\Program Files\PrintFlow Agent\` (configurable)
- Creates `agent.toml` from wizard inputs
- Registers `PrintFlowAgent` Windows service via bundled NSSM
- Service: auto-start, restart on crash (5s delay), stdout/stderr to logs dir
- Uninstaller: stops service, removes NSSM registration, deletes install dir
- Creates Start Menu shortcut "PrintFlow Agent" (opens dashboard URL in browser)

### Non-Functional
- Works on Windows 10 21H2+ and Windows 11
- No Python/pip/uv pre-installed on target machine
- Install completes in < 60 seconds
- Agent binary < 60MB (with UPX compression, target ~35-45MB)
- Installer overhead < 2MB

## Architecture

```
BUILD PIPELINE
==============

Developer Machine                       Output
-----------------                       ------
1. uv sync (resolve deps)
2. version-embed.py writes              packages/agent/src/agent/__version__.py
   VERSION = "1.0.0"
3. PyInstaller --onedir                 dist/printflow-agent/
   pyinstaller-agent-spec.py              printflow-agent.exe
                                          _internal/ (Python runtime + deps)
4. Copy NSSM + default config          dist/printflow-agent/
                                          nssm.exe
                                          default-agent.toml
5. Inno Setup compiles                  dist/PrintFlowAgentSetup-1.0.0.exe
   inno-setup-agent.iss                   (single installer, ~40-60MB)


INSTALL FLOW (end user)
=======================

1. User double-clicks PrintFlowAgentSetup-1.0.0.exe
2. UAC prompt (needs admin for service registration)
3. Welcome page (PrintFlow logo)
4. License Agreement page (EULA)
5. Configuration page:
   +-------------------------------------------+
   | Printer Name:    [___DTG-1____________]   |
   | PrintExp Path:   [C:\PrintExp\........] [Browse] |
   |   (Auto-detected: C:\PrintExp_5.7.7...)  |
   | Dashboard URL:   [http://192.168.1.100:8000] |
   | License Key:     [____________________]   |
   |   (Leave blank for 14-day demo)           |
   | Agent Port:      [8080___]                |
   +-------------------------------------------+
6. Install Location page (default: C:\Program Files\PrintFlow Agent)
7. Installing... (extract files, write agent.toml, register service)
8. Finish page:
   [x] Start PrintFlow Agent service now
   [x] Open dashboard in browser
   [Finish]


INSTALLED FILE LAYOUT
=====================

C:\Program Files\PrintFlow Agent\
  printflow-agent.exe              # Main agent binary
  _internal\                       # PyInstaller runtime (Python + deps)
  nssm.exe                         # Service manager
  agent.toml                       # Generated config
  license.key                      # License key file (if provided)
  logs\
    stdout.log                     # NSSM-managed log
    stderr.log                     # Error log
  uninstall.exe                    # Inno Setup uninstaller


RUNTIME FLOW
============

Windows boot
  -> NSSM starts PrintFlowAgent service
    -> printflow-agent.exe --config "C:\Program Files\PrintFlow Agent\agent.toml"
      -> Reads agent.toml (printer name, dashboard URL, etc.)
      -> Detects PrintExp process
      -> Starts FastAPI on 0.0.0.0:{port}
      -> Registers with dashboard via HTTP

On crash:
  NSSM waits 5s -> restarts printflow-agent.exe
  Logs crash to stderr.log
```

## Related Code Files

### Create
| File | Purpose |
|------|---------|
| `installer/agent/pyinstaller-agent-spec.py` | PyInstaller spec: hidden imports, data files, exe metadata |
| `installer/agent/inno-setup-agent.iss` | Inno Setup: wizard pages, NSSM commands, config generation |
| `installer/agent/default-agent.toml` | Template config with placeholder values |
| `installer/agent/printflow-icon.ico` | Application icon (needed for .exe and installer) |
| `installer/agent/LICENSE.txt` | EULA text for installer |
| `installer/shared/version-embed.py` | Script to write `__version__.py` from pyproject.toml version |
| `packages/agent/src/agent/frozen_path_resolver.py` | Resolve paths when running as PyInstaller bundle |
| `scripts/build-agent-installer.sh` | End-to-end build script |

### Modify
| File | Change |
|------|--------|
| `packages/agent/src/agent/main.py` | Use frozen_path_resolver for config path; add `--service` flag |
| `packages/common/src/common/config.py` | Frozen-mode path resolution; add `license_key`, `auto_update`, `update_url` fields |
| `pyproject.toml` (root) | Add `pyinstaller` to dev dependencies |

## Implementation Steps

### Step 1: Frozen Path Resolver Module

Create `packages/agent/src/agent/frozen_path_resolver.py`:

```python
"""Resolve file paths correctly for both development and PyInstaller-frozen modes."""
import sys
from pathlib import Path

def get_install_dir() -> Path:
    """Return the directory containing the agent executable or script.

    PyInstaller --onedir: sys.executable is the .exe in the install dir.
    Development: returns the repo root (or CWD).
    """
    if getattr(sys, "frozen", False):
        # PyInstaller --onedir: exe sits in install dir
        return Path(sys.executable).parent
    # Development mode: use CWD
    return Path.cwd()

def get_default_config_path() -> Path:
    """Return the default agent.toml path."""
    return get_install_dir() / "agent.toml"

def get_logs_dir() -> Path:
    """Return the logs directory, creating it if needed."""
    logs = get_install_dir() / "logs"
    logs.mkdir(exist_ok=True)
    return logs
```

### Step 2: Update config.py for Frozen Mode

In `AgentConfig.load()`, when `config_path` is the default `"agent.toml"`, check if running frozen and resolve relative to exe dir:

```python
# In load() method, before path.exists() check:
if str(config_path) == "agent.toml" and getattr(sys, "frozen", False):
    path = Path(sys.executable).parent / "agent.toml"
```

Add new config fields:
```python
# Agent identity
license_key: str = ""
# Updates
auto_update: bool = True
update_url: str = "https://updates.printflow.com/api/agent/latest"
```

### Step 3: PyInstaller Spec File

Create `installer/agent/pyinstaller-agent-spec.py`:

```python
# PyInstaller spec for PrintFlow Agent
# Run: pyinstaller installer/agent/pyinstaller-agent-spec.py

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Collect all submodules that use dynamic imports
hidden_imports = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("pydantic")
    + collect_submodules("sqlalchemy")
    + collect_submodules("agent")
    + collect_submodules("common")
    + ["tomllib"]
)

a = Analysis(
    ["../../packages/agent/src/agent/main.py"],
    pathex=[
        "../../packages/agent/src",
        "../../packages/common/src",
    ],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="printflow-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Windows service needs console mode
    icon="printflow-icon.ico",
    version_info={
        "CompanyName": "PrintFlow",
        "FileDescription": "PrintFlow Printer Agent",
        "FileVersion": "1.0.0",
        "ProductName": "PrintFlow Agent",
        "ProductVersion": "1.0.0",
    },
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="printflow-agent",
)
```

**Note on spec file**: The actual spec file should be generated via `pyi-makespec` first, then customized. The above is a starting template. PyInstaller version info requires a proper VS_VERSION_INFO resource file (`.rc` or tuple format), not a dict -- adjust during implementation.

### Step 4: Inno Setup Script

Create `installer/agent/inno-setup-agent.iss`:

Key sections of the .iss file:

```pascal
[Setup]
AppName=PrintFlow Agent
AppVersion={#AppVersion}
AppPublisher=PrintFlow
DefaultDirName={autopf}\PrintFlow Agent
DefaultGroupName=PrintFlow
UninstallDisplayIcon={app}\printflow-agent.exe
OutputBaseFilename=PrintFlowAgentSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
SetupIconFile=printflow-icon.ico
WizardImageFile=printflow-logo.bmp

[Files]
; Agent binary and runtime
Source: "..\..\dist\printflow-agent\*"; DestDir: "{app}"; Flags: recursesubdirs
; NSSM service manager
Source: "nssm.exe"; DestDir: "{app}"
; Default config template
Source: "default-agent.toml"; DestDir: "{app}"; DestName: "agent.toml.template"

[Dirs]
Name: "{app}\logs"

[Icons]
Name: "{group}\PrintFlow Dashboard"; Filename: "{code:GetDashboardURL}"
Name: "{group}\Uninstall PrintFlow Agent"; Filename: "{uninstallexe}"

[Run]
; Register and start service after install
Filename: "{app}\nssm.exe"; Parameters: "install PrintFlowAgent ""{app}\printflow-agent.exe"" --config ""{app}\agent.toml"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppDirectory ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppStdout ""{app}\logs\stdout.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppStderr ""{app}\logs\stderr.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppRotateFiles 1"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppRotateBytes 10485760"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent AppRestartDelay 5000"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set PrintFlowAgent Start SERVICE_AUTO_START"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "start PrintFlowAgent"; Flags: runhidden waituntilterminated; Description: "Start PrintFlow Agent"; Check: StartServiceCheck

[UninstallRun]
; Stop and remove service before uninstall
Filename: "{app}\nssm.exe"; Parameters: "stop PrintFlowAgent"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "remove PrintFlowAgent confirm"; Flags: runhidden waituntilterminated

[Code]
{ Custom config page variables }
var
  ConfigPage: TInputQueryWizardPage;
  PrinterNameEdit: TNewEdit;
  PrintExpPathEdit: TNewEdit;
  DashboardURLEdit: TNewEdit;
  LicenseKeyEdit: TNewEdit;
  AgentPortEdit: TNewEdit;

{ Auto-detect PrintExp installation }
function FindPrintExpPath: String;
var
  SearchPaths: array of String;
  I: Integer;
begin
  Result := '';
  SetLength(SearchPaths, 4);
  SearchPaths[0] := 'C:\PrintExp_5.7.7.1.12_MULTIWS\PrintExp.exe';
  SearchPaths[1] := 'D:\PrintExp_5.7.7.1.12_MULTIWS\PrintExp.exe';
  SearchPaths[2] := 'C:\PrintExp\PrintExp.exe';
  SearchPaths[3] := 'D:\PrintExp\PrintExp.exe';
  for I := 0 to 3 do
    if FileExists(SearchPaths[I]) then begin
      Result := SearchPaths[I];
      Exit;
    end;
end;

{ Write agent.toml from wizard inputs }
procedure WriteAgentConfig;
var
  ConfigFile: String;
  Lines: TStringList;
begin
  ConfigFile := ExpandConstant('{app}\agent.toml');
  Lines := TStringList.Create;
  try
    Lines.Add('[agent]');
    Lines.Add('name = "' + PrinterNameEdit.Text + '"');
    Lines.Add('poll_interval_seconds = 5');
    Lines.Add('');
    Lines.Add('[printer]');
    Lines.Add('type = "auto"');
    Lines.Add('');
    Lines.Add('[printexp]');
    Lines.Add('exe_path = "' + PrintExpPathEdit.Text + '"');
    Lines.Add('tcp_port = 9100');
    Lines.Add('memory_offset = 0x016CDB');
    Lines.Add('');
    Lines.Add('[network]');
    Lines.Add('port = ' + AgentPortEdit.Text);
    Lines.Add('dashboard_url = "' + DashboardURLEdit.Text + '"');
    Lines.Add('');
    Lines.Add('[license]');
    Lines.Add('key = "' + LicenseKeyEdit.Text + '"');
    Lines.Add('');
    Lines.Add('[updates]');
    Lines.Add('auto_update = true');
    Lines.Add('update_url = "https://updates.printflow.com/api/agent/latest"');
    Lines.SaveToFile(ConfigFile);
  finally
    Lines.Free;
  end;
end;
```

**Note**: The Pascal code above is a structural skeleton. The actual Inno Setup script needs proper `InitializeWizard` procedure to create custom form controls, `NextButtonClick` for validation, and `CurStepChanged` to trigger config write at `ssPostInstall`. This will be fleshed out during implementation.

### Step 5: NSSM Binary

- Download NSSM 2.24 (64-bit) from https://nssm.cc/download
- MIT license -- free for commercial use
- Place at `installer/agent/nssm.exe` (~300KB)
- Commit to repo (it's small and rarely changes)

### Step 6: Build Automation Script

Create `scripts/build-agent-installer.sh`:

```bash
#!/bin/bash
set -euo pipefail

VERSION="${1:-0.1.0}"
echo "[build] Building PrintFlow Agent Installer v${VERSION}"

# 1. Embed version
python installer/shared/version-embed.py "$VERSION"

# 2. Sync dependencies
uv sync

# 3. Run PyInstaller
uv run pyinstaller installer/agent/pyinstaller-agent-spec.py \
  --distpath dist/ --workpath build/ --clean -y

# 4. Copy NSSM and template config
cp installer/agent/nssm.exe dist/printflow-agent/
cp installer/agent/default-agent.toml dist/printflow-agent/agent.toml.template

# 5. Compile Inno Setup installer
# Requires Inno Setup 6 installed, iscc.exe in PATH
iscc /DAppVersion="$VERSION" installer/agent/inno-setup-agent.iss

echo "[build] Done: dist/PrintFlowAgentSetup-${VERSION}.exe"
```

### Step 7: Version Embedding

Create `installer/shared/version-embed.py`:

```python
"""Write __version__.py into agent package from CLI arg or pyproject.toml."""
import sys
import tomllib
from pathlib import Path

def main():
    if len(sys.argv) > 1:
        version = sys.argv[1]
    else:
        pyproject = Path("packages/agent/pyproject.toml")
        with pyproject.open("rb") as f:
            version = tomllib.load(f)["project"]["version"]

    version_file = Path("packages/agent/src/agent/__version__.py")
    version_file.write_text(f'__version__ = "{version}"\n')
    print(f"[version] Wrote {version} to {version_file}")

if __name__ == "__main__":
    main()
```

### Step 8: Update main.py for Service Mode

Modify `packages/agent/src/agent/main.py`:
- Import `frozen_path_resolver`
- When `sys.frozen`, default `--config` to the install dir path
- Add `--version` flag that prints version and exits
- Add file-based logging alongside console output

### Step 9: Test Standalone .exe

Before building the installer, test the bare PyInstaller output:

```bash
# Build
uv run pyinstaller installer/agent/pyinstaller-agent-spec.py --clean -y

# Test mock mode (no printer needed)
dist/printflow-agent/printflow-agent.exe --mock --port 8081

# Verify health endpoint
curl http://localhost:8081/health
# Expected: {"status":"ok","service":"printflow-agent"}
```

## Todo List

- [ ] Create `installer/` directory structure
- [ ] Create `frozen_path_resolver.py` module
- [ ] Update `config.py` with frozen-mode path resolution + new fields
- [ ] Create `version-embed.py` script
- [ ] Create PyInstaller spec file
- [ ] Test bare .exe with `--mock` (no installer yet)
- [ ] Resolve all hidden import issues
- [ ] Download and commit NSSM 2.24 binary
- [ ] Create `default-agent.toml` template
- [ ] Create Inno Setup .iss script with custom config page
- [ ] Create `build-agent-installer.sh` script
- [ ] Build full installer end-to-end
- [ ] Test installer on dev machine
- [ ] Create `printflow-icon.ico` (placeholder or real)
- [ ] Write LICENSE.txt (EULA)
- [ ] Update root `pyproject.toml` with pyinstaller dev dep

## Success Criteria

- `scripts/build-agent-installer.sh 1.0.0` produces `dist/PrintFlowAgentSetup-1.0.0.exe`
- Installer runs on fresh Windows 10/11, no Python pre-installed
- Config wizard auto-detects PrintExp path
- Agent starts as Windows service after install
- `curl localhost:8080/health` returns OK after install
- Uninstaller cleanly removes service + files

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| PyInstaller hidden import misses | Agent crashes on startup | Maintain explicit hidden_imports list; test with `--mock` before packaging |
| Antivirus false positive on .exe | Users can't install | Code signing (Phase 4); in interim, provide whitelist instructions |
| Large binary (~50MB) | Slow download for customers | UPX compression; CDN hosting; consider --onedir which compresses better |
| Inno Setup Pascal scripting complexity | Dev time overrun | Start with minimal wizard (3 fields), iterate on polish |
| NSSM version conflicts with existing installs | Service issues | Bundle specific NSSM 2.24, use full path to bundled copy |
| Config file path issues in frozen mode | Agent can't find config | `frozen_path_resolver.py` + thorough testing |

## Security Considerations

- Installer requests UAC elevation only for NSSM service registration
- Agent service runs as LOCAL SERVICE (not SYSTEM) -- principle of least privilege
- License key stored in `agent.toml` on disk (file ACLs restrict to admin + service account)
- NSSM binary verified by SHA-256 checksum before bundling
- No network calls during installation (fully offline-capable)
