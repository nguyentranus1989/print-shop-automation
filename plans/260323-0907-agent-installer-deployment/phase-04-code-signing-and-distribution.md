# Phase 4 -- Code Signing & Distribution

## Context Links
- Phase 1: `./phase-01-build-pipeline-pyinstaller-inno-setup.md`
- Phase 3: `./phase-03-auto-update-mechanism.md`
- Commercial landscape: `docs/research-commercial-landscape.md`

## Overview
- **Priority**: P2 (needed before public distribution, not for first 3-5 customers)
- **Status**: Pending
- **Effort**: 2d
- **Description**: Windows SmartScreen and antivirus products aggressively flag unsigned .exe files. Code signing eliminates these warnings and builds customer trust. Also covers distribution infrastructure.

## Key Insights

### SmartScreen Behavior

| Scenario | User Experience |
|----------|----------------|
| Unsigned .exe | "Windows protected your PC" -- blue warning, "Run anyway" hidden behind "More info" link. ~30% of users abandon here. |
| OV code signing cert | Warning appears for first few weeks until Microsoft builds reputation. Then SmartScreen passes silently. |
| EV code signing cert | **Immediate** SmartScreen trust. No reputation period. Gold standard. |

### Certificate Types Compared

| Type | Cost | SmartScreen | Hardware | Notes |
|------|------|-------------|----------|-------|
| OV (Organization Validated) | $100-200/yr | Trust builds over time (~2-4 weeks) | Software-based (PFX file) | Cheapest option. Fine for MVP. |
| EV (Extended Validation) | $250-500/yr | Immediate trust | **Requires hardware token (USB)** | Can't automate signing in CI without HSM. |
| Azure Trusted Signing | ~$10/mo | Immediate trust (EV equivalent) | Cloud-based (Azure HSM) | CI-friendly. Newer option (GA 2024). |

### Recommendation

**Start with OV cert ($100-200/yr), upgrade to Azure Trusted Signing when CI pipeline exists.**

Rationale:
- First 3-5 customers: you install it yourself, can click through SmartScreen warning
- OV builds reputation in 2-4 weeks: by the time you have 10+ customers, SmartScreen passes
- EV requires a physical USB token (YubiKey/SafeNet) -- awkward for CI/CD
- Azure Trusted Signing gives EV-equivalent trust via cloud HSM, CI-friendly, but requires Azure account setup

### Certificate Vendors (OV, cheapest)

| Vendor | OV Price | Notes |
|--------|----------|-------|
| Certum | $69/yr | Polish CA. Good value. Open-source friendly. |
| Sectigo (Comodo) | $179/yr | Most popular. Good tooling. |
| DigiCert | $474/yr | Enterprise. Overkill for MVP. |
| SSL.com | $139/yr | U.S.-based. Easy process. |

**Recommendation**: Certum at $69/yr for MVP. Upgrade to Azure Trusted Signing ($120/yr) when CI pipeline justifies it.

## Requirements

### Functional
- All distributed .exe files are Authenticode-signed (agent installer, dashboard package, update binaries)
- Signing integrated into build script (one command builds + signs)
- Installer shows "Verified publisher: PrintFlow" in UAC prompt
- Updates served via HTTPS from a reliable CDN

### Non-Functional
- Signing adds < 30 seconds to build pipeline
- Certificate private key stored securely (not in git, not on shared drives)
- Signing works on developer machine and CI (GitHub Actions)

## Architecture

### Signing Pipeline

```
BUILD + SIGN FLOW
=================

1. Build .exe (PyInstaller)
   dist/printflow-agent/printflow-agent.exe

2. Sign the .exe
   signtool sign /f cert.pfx /p PASSWORD /tr http://timestamp.sectigo.com /td sha256 /fd sha256
     dist/printflow-agent/printflow-agent.exe

3. Build installer (Inno Setup) -- Inno Setup can auto-sign output
   iscc /SStandard="signtool sign /f cert.pfx ..." installer/agent/inno-setup-agent.iss

4. Sign installer .exe
   signtool sign /f cert.pfx ...
     dist/PrintFlowAgentSetup-1.0.0.exe

5. Upload to distribution server
   - GitHub Releases (free)
   - Or Cloudflare R2 / S3


CERTIFICATE STORAGE
====================

Development:
  - PFX file on developer's local machine (password-protected)
  - Password in Windows Credential Manager or KeePass

CI (GitHub Actions):
  - PFX as base64 in GitHub Secrets
  - Password as GitHub Secret
  - Decode PFX in CI step, sign, delete PFX after
```

### Distribution Infrastructure

```
OPTION A: GitHub Releases (MVP)
================================
- Free for public repos, unlimited bandwidth
- Built-in release management + changelog
- API for latest version check
- URL: https://github.com/yourorg/printflow-releases/releases/latest

OPTION B: Cloudflare R2 + Pages (Scale)
=========================================
- R2: $0.015/GB storage, FREE egress (no bandwidth cost)
- Pages: host download page (free)
- Custom domain: updates.printflow.com
- URL: https://updates.printflow.com/agent/latest.json

OPTION C: Self-hosted (Air-gapped customers)
=============================================
- Customer runs their own update server
- Simple nginx serving static files
- Agent's update_url points to local server
```

## Implementation Steps

### Step 1: Obtain Code Signing Certificate

1. Purchase OV cert from Certum ($69/yr) or SSL.com ($139/yr)
2. Complete organization validation (business registration, domain ownership)
3. Receive PFX file with private key
4. Store PFX securely (encrypted, not in git)
5. Timeline: 3-5 business days for OV validation

### Step 2: Install Signing Tools

- Windows SDK includes `signtool.exe`
- Ensure it's in PATH or reference full path
- Install: `winget install Microsoft.WindowsSDK` or download from Microsoft

### Step 3: Integrate Signing into Build Script

Update `scripts/build-agent-installer.sh`:

```bash
#!/bin/bash
set -euo pipefail

VERSION="${1:-0.1.0}"
CERT_PATH="${PRINTFLOW_CERT_PATH:-$HOME/.printflow/cert.pfx}"
CERT_PASS="${PRINTFLOW_CERT_PASS}"
TIMESTAMP_URL="http://timestamp.sectigo.com"

# ... (existing build steps) ...

# Sign agent .exe
echo "[sign] Signing printflow-agent.exe..."
signtool sign /f "$CERT_PATH" /p "$CERT_PASS" \
  /tr "$TIMESTAMP_URL" /td sha256 /fd sha256 \
  dist/printflow-agent/printflow-agent.exe

# Build installer (Inno Setup)
iscc /DAppVersion="$VERSION" installer/agent/inno-setup-agent.iss

# Sign installer
echo "[sign] Signing installer..."
signtool sign /f "$CERT_PATH" /p "$CERT_PASS" \
  /tr "$TIMESTAMP_URL" /td sha256 /fd sha256 \
  "dist/PrintFlowAgentSetup-${VERSION}.exe"

# Verify signatures
signtool verify /pa dist/printflow-agent/printflow-agent.exe
signtool verify /pa "dist/PrintFlowAgentSetup-${VERSION}.exe"

echo "[build] Done: dist/PrintFlowAgentSetup-${VERSION}.exe (signed)"
```

### Step 4: GitHub Actions CI Signing (Future)

```yaml
# .github/workflows/build-installer.yml
- name: Decode signing certificate
  run: |
    echo "${{ secrets.CODE_SIGN_CERT_BASE64 }}" | base64 -d > cert.pfx

- name: Sign executables
  run: |
    signtool sign /f cert.pfx /p "${{ secrets.CODE_SIGN_PASS }}" \
      /tr http://timestamp.sectigo.com /td sha256 /fd sha256 \
      dist/printflow-agent/printflow-agent.exe

- name: Clean up certificate
  if: always()
  run: del cert.pfx
```

### Step 5: Timestamping

Always use RFC 3161 timestamping when signing. Without a timestamp, the signature expires when the certificate expires (1 year). With a timestamp, the signature remains valid indefinitely.

Timestamp servers (free):
- `http://timestamp.sectigo.com`
- `http://timestamp.digicert.com`
- `http://timestamp.globalsign.com`

### Step 6: Distribution Page

Create a simple download page at `printflow.com/download` (or use GitHub Releases page directly for MVP):

```
Download PrintFlow Agent v1.0.0
================================
[Download Installer] (PrintFlowAgentSetup-1.0.0.exe, 42 MB)
SHA-256: abc123...

System Requirements:
- Windows 10 or Windows 11
- 100 MB disk space
- Network connection to dashboard
```

## Todo List

- [ ] Research and purchase OV code signing certificate
- [ ] Install Windows SDK (`signtool.exe`)
- [ ] Test manual signing of a PyInstaller .exe
- [ ] Verify SmartScreen behavior with signed .exe
- [ ] Integrate signing into `build-agent-installer.sh`
- [ ] Integrate signing into Inno Setup config (SignTool directive)
- [ ] Set up GitHub Releases as distribution channel
- [ ] Create `latest.json` for update mechanism
- [ ] Document certificate renewal process
- [ ] (Future) Set up GitHub Actions CI signing workflow
- [ ] (Future) Evaluate Azure Trusted Signing when CI pipeline exists

## Success Criteria

- Signed installer shows "Verified publisher: PrintFlow" in UAC dialog
- SmartScreen does not show blue warning (after reputation builds, or immediately with EV)
- Windows Defender does not flag the .exe
- `signtool verify /pa` passes on all distributed binaries
- Timestamped signatures remain valid after certificate renewal

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| OV cert takes weeks to validate | Delays distribution | Apply early; use first customers as manual-install while waiting |
| Certificate private key leaked | Attacker signs malware as PrintFlow | Store PFX encrypted; rotate if compromised; revoke via CA |
| SmartScreen still warns with OV cert | User confusion | Document "it's normal for first 2 weeks"; upgrade to EV/Azure TS if persistent |
| Timestamp server unreachable during build | Unsigned or un-timestamped binary | Retry; use multiple TS servers in fallback |
| Certificate expires and not renewed | Updates unsigned, SmartScreen blocks | Calendar reminder 30 days before expiry; auto-renewal if CA supports |

## Security Considerations

- PFX file: password-protected, stored outside repo, ACL-restricted
- CI: PFX stored as GitHub encrypted secret, decoded only during sign step, deleted after
- Timestamp ensures signatures outlive certificate validity period
- SHA-256 digest algorithm (not SHA-1, which is deprecated)
- Dual-sign with SHA-1 + SHA-256 only if targeting Windows 7 (not needed for Win10+)
