# Documentation Update — UV PrintExp Integration (2026-03-26)

## Summary

Updated PrintFlow documentation to reflect UV PrintExp v5.7.9.4.5008 DLL injection breakthrough (confirmed working 2026-03-26). Added comprehensive backend integration guide for DTF and UV, plus agent implementation reference.

---

## Files Modified

### 1. `docs/printer-backend-integration.md` ✨ NEW

**Purpose:** Complete technical reference for DTF and UV memory injection backends.

**Contents:**
- Architecture comparison table (DTF v5.7.6 vs UV v5.7.9.4.5008)
- Global pointer locations and CTaskManager access patterns
- Struct layouts (CTaskInfo offset tables)
- File vector and display vector management
- Critical safety note: DO NOT copy to print vector on UV (causes R6025)
- Dangerous vtable indices that crash UV
- Complete injection workflow with code snippets
- Debugging tips and version detection

**Key Facts Documented:**
- UV uses different offsets from DTF (see offset table)
- AddFile PREPENDS (inserts at index 0), requires vector diffing
- UI refresh message (0x7F4) same for both
- Discovery method: Python memory scanners + TCC compiler (no Ghidra)

---

### 2. `docs/agent-printer-backend.md` ✨ NEW

**Purpose:** Guide for PrintFlow agent developers on implementing DTF/UV backends.

**Contents:**
- Printer type detection heuristics (file size-based)
- Backend interface design (ABC with inject_file, pause, resume, cancel)
- Agent configuration integration (auto-detect support)
- Job injection workflow with fallback to TCP 9100
- Error handling matrix (R6025, access violation, timeout)
- Unit test examples (pytest fixtures, mocking)
- Hardware test commands
- Logging & diagnostics setup
- Migration path from DTG to DTF/UV

---

### 3. `docs/dtf-memory-patch-research.md` (Updated)

**Changes:**
- Added status note: "SOLVED via DLL injection (2026-03-26)"
- Updated testing status: DTF and UV both confirmed working
- Added reference link to new `printer-backend-integration.md`

---

### 4. `docs/tech-stack.md` (Updated)

**Changes:**
- Expanded Win32 Integration section to mention DLL injection
- Added reference to `printer-backend-integration.md`
- Clarified ctypes is used for both memory patching and DLL injection

---

### 5. `README.md` (Updated)

**Changes:**
- Updated tagline: Added "auto-detection" and "DLL injection" phrases
- Enhanced agent.toml section:
  - Noted "auto" detects DTG/DTF/UV
  - Added link to `docs/printer-backend-integration.md`
  - Clarified multi-printer support

---

## Key Technical Facts Documented

### Offset Table (DTF vs UV)

| Item | DTF v5.7.6 | UV v5.7.9.4.5008 |
|------|-----------|------------------|
| Global pointer | EXE+0x176B98 | EXE+0x1D2F10 |
| CTaskManager access | appVt[22] call | device_obj+0x70 |
| AddFile | vtable[7] | vtable[9] |
| File vector | +0x28 | +0x08 |
| Display vector | +0x48 | +0x28 |
| CTaskInfo size | 0xB08 | 0xCA0 |
| HSKRipFile creator | +0x5B0 | +0x140 |
| UI refresh | 0x7F4 | 0x7F4 (same) |

### Critical Safety Notes

1. **AddFile PREPENDS** — New job inserted at index 0; must diff vector to find it
2. **DO NOT copy to print vector on UV** — Different object type, causes R6025 pure virtual call crash
3. **Only copy to display vector** — Both DTF and UV have separate display vectors
4. **Dangerous vtable indices (UV only):** vt[6], vt[11], vt[12] cause immediate crash

### Discovery Method

- No Ghidra required
- Python memory scanners identify offsets and signatures
- TCC compiler (lightweight) used to compile and inject DLL
- Tests confirmed on actual UV hardware (2026-03-26)

---

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| DTF DLL injection | ✅ Production | DTG_automation/scripts/inject_dtf.dll |
| UV DLL injection | ✅ Production | DTG_automation/scripts/inject_uv.dll |
| Memory scanning tools | ✅ Available | DTG_automation/scripts/scan_uv_printexp.py |
| Agent backend interface | 📋 Design ready | docs/agent-printer-backend.md |
| Agent implementation | 🔄 Next phase | Integrate into packages/agent/ |

---

## Next Actions for PrintFlow Team

1. **Copy DLLs:** Transfer `inject_dtf.dll` and `inject_uv.dll` from DTG_automation to `packages/agent/agent/dlls/`

2. **Implement Agent Backends:** Create `packages/agent/agent/printer/backends.py` using design in `agent-printer-backend.md`

3. **Add Printer Detection:** Implement `detect_printer_type()` function (size heuristics)

4. **Integrate Job Injector:** Update job submission to call appropriate backend based on detected type

5. **Test on Hardware:**
   ```bash
   # DTF test
   python -m agent --hardware-test --printer-type=dtf

   # UV test
   python -m agent --hardware-test --printer-type=uv
   ```

6. **Monitor & Log:** Enable debug logging for backend operations; track injection success rates

---

## References

- **DTG_automation project:** Source of DLL implementations and memory scanning tools
  - `scripts/inject_uv_printexp.c` — UV injection source
  - `scripts/inject_dtf.dll` — DTF compiled binary
  - `scripts/inject_uv.dll` — UV compiled binary
  - `scripts/add_to_uv_printexp.py` — Python wrapper example
  - `scripts/scan_uv_printexp.py` — Memory offset scanner

- **Pressing_automation project:** Potential code reuse (QR parser, API client)

---

## Notes

- All memory offsets verified on PrintExp v5.7.6 (DTF) and v5.7.9.4.5008 (UV)
- File vector diffing required because AddFile behavior (prepend) is implicit
- Display vector and print vector are distinct; copying to wrong vector causes R6025
- UI refresh via WM_USER + 0x7F4 PostMessage works for both backends
- TCP 9100 fallback available if DLL injection fails (shows as ~section0.prn, no filename)
