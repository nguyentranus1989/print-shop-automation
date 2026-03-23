# Phase 5 -- Installer Testing Strategy

## Context Links
- Phase 1 (build pipeline): `./phase-01-build-pipeline-pyinstaller-inno-setup.md`
- Phase 2 (dashboard): `./phase-02-dashboard-deployment-strategy.md`
- Phase 3 (updates): `./phase-03-auto-update-mechanism.md`

## Overview
- **Priority**: P1 (blocks distribution)
- **Status**: Pending
- **Effort**: 2d
- **Description**: How to test the installer on clean Windows machines without requiring physical hardware for every test cycle. Covers VM-based testing, snapshot workflows, and a test checklist.

## Key Insights

1. **Docker is not viable for Windows service testing**. Windows containers can't run GUI apps, don't have NSSM support, and don't represent real user environments.

2. **VMs are the correct approach**. Hyper-V (free on Win10/11 Pro) or VirtualBox (free, works on Home edition) with Windows 10/11 ISOs.

3. **Snapshot workflow is key**: create a "clean Windows" snapshot, test installer, revert to snapshot, repeat. This gives deterministic, repeatable tests.

4. **Three test levels needed**:
   - **Level 1 (dev machine)**: Test PyInstaller .exe works with `--mock` flag
   - **Level 2 (clean VM)**: Full installer on fresh Windows, no Python installed
   - **Level 3 (real hardware)**: Test on actual printer PC with PrintExp running

## Requirements

### Test Environments

| Environment | OS | Purpose | Frequency |
|-------------|------|---------|-----------|
| Dev machine | Win 11 | Quick smoke test of .exe | Every build |
| VM - Win10 | Windows 10 22H2 | Full installer test | Every release |
| VM - Win11 | Windows 11 23H2 | Full installer test | Every release |
| Real printer PC | Win 10/11 + PrintExp | End-to-end integration | Before customer delivery |

### VM Setup

**Option A: Hyper-V (Recommended if Win Pro)**
- Free, built into Windows 10/11 Pro
- Better performance than VirtualBox (native hypervisor)
- Supports quick snapshots (checkpoints)
- Enable: `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All`

**Option B: VirtualBox (if Win Home)**
- Free, works on Home edition
- Slightly slower but functional
- Supports snapshots

**Option C: GitHub Actions Windows Runner (CI)**
- `windows-latest` runner (Windows Server 2022)
- Free for public repos (2000 min/mo)
- Good for automated smoke tests
- Cannot test full GUI installer (no interactive desktop)

### Windows ISOs (Free, Legal)

- Windows 10: https://www.microsoft.com/software-download/windows10ISO
- Windows 11: https://www.microsoft.com/software-download/windows11
- Microsoft Evaluation VMs: https://developer.microsoft.com/windows/downloads/virtual-machines/ (90-day trial, pre-built .vhdx)

**Recommendation**: Use Microsoft Evaluation VMs for quickest setup. They come pre-configured, expire in 90 days (just re-download). Take a snapshot immediately after setup before any changes.

## Architecture

### Snapshot Workflow

```
VM LIFECYCLE
============

1. SETUP (once per OS version)
   - Create VM (4GB RAM, 60GB disk, 2 vCPUs)
   - Install Windows 10/11 from ISO
   - Install Windows Updates
   - Take snapshot: "CLEAN-WINDOWS"

2. TEST CYCLE (per build)
   - Restore snapshot "CLEAN-WINDOWS"
   - Copy installer .exe to VM (shared folder or network)
   - Run installer
   - Execute test checklist
   - Record results
   - (Do NOT save state -- always revert to clean snapshot)

3. VARIANT TESTING
   - Restore "CLEAN-WINDOWS"
   - Test with antivirus (Windows Defender active)
   - Restore "CLEAN-WINDOWS"
   - Test upgrade (install v1.0.0, then upgrade to v1.1.0)
   - Restore "CLEAN-WINDOWS"
   - Test uninstall
```

### Test Automation (GitHub Actions)

```yaml
# .github/workflows/test-agent-build.yml
# Smoke test: build .exe, run --mock, verify health endpoint
name: Test Agent Build
on: [push, pull_request]

jobs:
  build-and-test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync

      # Build PyInstaller exe
      - run: uv run pyinstaller installer/agent/pyinstaller-agent-spec.py --clean -y

      # Start agent in mock mode (background)
      - run: |
          Start-Process -NoNewWindow dist\printflow-agent\printflow-agent.exe `
            -ArgumentList "--mock","--port","8081"
        shell: pwsh

      # Wait for startup
      - run: Start-Sleep -Seconds 10
        shell: pwsh

      # Health check
      - run: |
          $response = Invoke-WebRequest -Uri http://localhost:8081/health -UseBasicParsing
          if ($response.StatusCode -ne 200) { exit 1 }
          Write-Host "Health check passed: $($response.Content)"
        shell: pwsh

      # Version check
      - run: |
          $response = Invoke-WebRequest -Uri http://localhost:8081/version -UseBasicParsing
          Write-Host "Version: $($response.Content)"
        shell: pwsh
```

## Implementation Steps

### Step 1: Set Up Test VMs

1. Enable Hyper-V (or install VirtualBox)
2. Download Windows 10 + 11 evaluation VMs from Microsoft
3. Create VMs with 4GB RAM, 60GB disk
4. Install Windows, run updates
5. Take "CLEAN-WINDOWS" snapshot on each
6. Document VM names and snapshot names

### Step 2: Create Test Checklist Script

Create `scripts/test-installer-checklist.ps1` (run inside VM):

```powershell
# PrintFlow Agent Installer Test Checklist
# Run this script inside a clean Windows VM after installing

$ErrorActionPreference = "Stop"
$results = @()

function Test-Check {
    param([string]$Name, [scriptblock]$Test)
    try {
        $result = & $Test
        if ($result) {
            Write-Host "[PASS] $Name" -ForegroundColor Green
            $script:results += @{Name=$Name; Status="PASS"}
        } else {
            Write-Host "[FAIL] $Name" -ForegroundColor Red
            $script:results += @{Name=$Name; Status="FAIL"}
        }
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
        $script:results += @{Name=$Name; Status="FAIL"; Error=$_.Exception.Message}
    }
}

Write-Host "=== PrintFlow Agent Installer Test ===" -ForegroundColor Cyan

# 1. Files exist
Test-Check "Agent exe exists" {
    Test-Path "C:\Program Files\PrintFlow Agent\printflow-agent.exe"
}

Test-Check "NSSM exe exists" {
    Test-Path "C:\Program Files\PrintFlow Agent\nssm.exe"
}

Test-Check "agent.toml exists" {
    Test-Path "C:\Program Files\PrintFlow Agent\agent.toml"
}

Test-Check "Logs directory exists" {
    Test-Path "C:\Program Files\PrintFlow Agent\logs"
}

# 2. Service registered
Test-Check "Service registered" {
    $svc = Get-Service -Name "PrintFlowAgent" -ErrorAction SilentlyContinue
    $null -ne $svc
}

Test-Check "Service running" {
    $svc = Get-Service -Name "PrintFlowAgent"
    $svc.Status -eq "Running"
}

Test-Check "Service set to auto-start" {
    $svc = Get-Service -Name "PrintFlowAgent"
    $svc.StartType -eq "Automatic"
}

# 3. Agent responding
Test-Check "Health endpoint responds" {
    $port = (Get-Content "C:\Program Files\PrintFlow Agent\agent.toml" |
        Select-String "port\s*=\s*(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value })
    if (-not $port) { $port = "8080" }
    $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 10
    $response.StatusCode -eq 200
}

Test-Check "Version endpoint responds" {
    $port = "8080"
    $response = Invoke-WebRequest -Uri "http://localhost:$port/version" -UseBasicParsing -TimeoutSec 10
    $response.StatusCode -eq 200
}

# 4. Config correct
Test-Check "Config has printer name" {
    $config = Get-Content "C:\Program Files\PrintFlow Agent\agent.toml" -Raw
    $config -match 'name\s*='
}

Test-Check "Config has dashboard URL" {
    $config = Get-Content "C:\Program Files\PrintFlow Agent\agent.toml" -Raw
    $config -match 'dashboard_url\s*='
}

# 5. Summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
$pass = ($results | Where-Object { $_.Status -eq "PASS" }).Count
$fail = ($results | Where-Object { $_.Status -eq "FAIL" }).Count
Write-Host "Passed: $pass / $($results.Count)" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Yellow" })
if ($fail -gt 0) {
    Write-Host "FAILED: $fail tests" -ForegroundColor Red
    $results | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Red }
}
```

### Step 3: Create Manual Test Checklist

For human testers (when automated script isn't sufficient):

**Install Test**
- [ ] Double-click installer .exe
- [ ] UAC prompt shows (verify publisher name if signed)
- [ ] Welcome page displays PrintFlow branding
- [ ] License agreement page shows EULA
- [ ] Config page: printer name field has default (hostname)
- [ ] Config page: PrintExp auto-detected (if installed) or browse works
- [ ] Config page: dashboard URL field has default
- [ ] Config page: license key field allows blank (demo mode)
- [ ] Install location page shows default path
- [ ] Installation completes without errors
- [ ] "Start service" checkbox checked by default
- [ ] Finish page offers to open dashboard in browser

**Post-Install Test**
- [ ] Service appears in `services.msc` as "PrintFlowAgent"
- [ ] Service status: Running
- [ ] Service startup type: Automatic
- [ ] `curl localhost:8080/health` returns `{"status":"ok"}`
- [ ] agent.toml contains wizard inputs
- [ ] Logs directory created with stdout.log
- [ ] Start Menu shortcut exists

**Reboot Test**
- [ ] Restart Windows
- [ ] Service auto-starts after reboot
- [ ] Health endpoint responds within 60s of login

**Crash Recovery Test**
- [ ] Kill `printflow-agent.exe` via Task Manager
- [ ] Service restarts within 10 seconds (NSSM restart delay)
- [ ] Health endpoint responds after restart

**Uninstall Test**
- [ ] Run uninstaller from Add/Remove Programs
- [ ] Service stopped
- [ ] Service removed from services.msc
- [ ] Install directory removed
- [ ] Start Menu shortcut removed
- [ ] No orphan files remain

**Upgrade Test**
- [ ] Install v1.0.0
- [ ] Verify running
- [ ] Install v1.1.0 over existing
- [ ] Config preserved (agent.toml not overwritten)
- [ ] Service updated to new binary
- [ ] Version endpoint shows 1.1.0

### Step 4: GitHub Actions Smoke Test

Create `.github/workflows/test-agent-build.yml` (as shown in Architecture section above). This runs on every push and verifies the PyInstaller build produces a working .exe.

### Step 5: Test Matrix

| Test | Dev Machine | Clean VM (Win10) | Clean VM (Win11) | Real Printer PC | GitHub Actions |
|------|:-----------:|:-----------------:|:-----------------:|:---------------:|:--------------:|
| PyInstaller .exe builds | x | | | | x |
| .exe --mock works | x | | | | x |
| Health endpoint | x | | | | x |
| Full installer | | x | x | | |
| Config wizard | | x | x | | |
| Service registration | | x | x | | |
| Reboot auto-start | | x | x | | |
| Crash recovery | | x | x | | |
| Uninstaller | | x | x | | |
| Real PrintExp integration | | | | x | |
| Upgrade path | | x | | | |
| Antivirus compatibility | | x | x | | |

## Todo List

- [ ] Set up Hyper-V or VirtualBox
- [ ] Download Windows 10 + 11 evaluation VMs
- [ ] Create VMs and take "CLEAN-WINDOWS" snapshots
- [ ] Create `test-installer-checklist.ps1`
- [ ] Create `.github/workflows/test-agent-build.yml`
- [ ] Document VM setup and snapshot workflow
- [ ] Run full test cycle on Win10 VM
- [ ] Run full test cycle on Win11 VM
- [ ] Test on real printer PC (when available)
- [ ] Test with Windows Defender active (no exclusions)

## Success Criteria

- Installer passes all checklist items on clean Win10 VM
- Installer passes all checklist items on clean Win11 VM
- GitHub Actions smoke test passes on every push
- Test cycle (restore snapshot -> install -> verify -> revert) takes < 15 minutes
- No manual test steps require developer-level knowledge

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hyper-V not available on Win Home | Can't create VMs | Use VirtualBox as fallback |
| Evaluation VMs expire (90 days) | Must re-download | Re-download is quick; re-take snapshots |
| Real printer PC not always available | Can't test PrintExp integration | Mock mode covers 90% of test surface; schedule real-hardware tests |
| GitHub Actions can't test GUI installer | No automated installer test | VM testing is manual but reliable; GA tests the .exe build only |
| Different Windows Update states affect behavior | Inconsistent test results | Always update VM before taking snapshot; document Windows build number |
