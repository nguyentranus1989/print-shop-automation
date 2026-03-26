# DTF Memory Patch Research

**Status:** SOLVED via DLL injection (2026-03-26). See [printer-backend-integration.md](./printer-backend-integration.md) for current integration guide.

## Problem
DTF PrintExp (64-bit) doesn't show preview BMP or correct filename when files are injected via TCP 9100. Shows `~section0.prn` with "No PreView".

## DTG vs DTF Architecture

### DTG (32-bit, works correctly)
- **Process:** PrintExp.exe handles TCP 9100 directly
- **Patch target:** DeviceManager.dll at offset `0x016CDB`
- **Original string:** `rip.prn` (inside format `%s\rip.prn`)
- **Patch to:** actual filename (e.g., `1.prn`)
- **Result:** File appears with correct name, BMP preview generated

### DTF (64-bit, needs fix)
- **Process:** NWReceive.exe (separate process) handles TCP 9100
- **Format string:** `%s\~section%d.prn` at offset `0x005A73` in NWReceive.exe
- **Also found in:** PrintExp_X64.exe at `0x1178E3`
- **`%s`** = TEMP_PATH (C:\Hstemp)
- **`%d`** = section counter (0, 1, 2...)

## Proposed DTF Fix
1. Find NWReceive.exe PID
2. Find base address of NWReceive.exe
3. Patch `~section%d.prn` (14 bytes) at offset `0x005A73` with `<name>.prn` + null padding
4. Send file via TCP 9100
5. NWReceive writes file as `{TEMP}\<name>.prn` instead of `{TEMP}\~section0.prn`
6. PrintExp picks up the file with correct name, generates BMP preview

## Key Difference from DTG
- DTG patches DeviceManager.dll (loaded in PrintExp.exe process)
- DTF patches NWReceive.exe (separate process)
- DTF offset is `0x005A73`, DTG offset is `0x016CDB`
- DTF needs 14 bytes overwritten, DTG needs ~10 bytes

## Files Reference
- DTG DeviceManager.dll: 114,176 bytes
- DTF NWReceive.exe: 84,480 bytes
- DTF also has vNWReceive.exe (same offsets) - virtual/alternative version

## BMP Generation
PrintExp generates BMP preview in the SAME folder as the PRN file.
- Pattern `%s.bmp` found in TaskCWC.dll and PrintExp_X64.exe
- Strips .prn extension, adds .bmp
- So `C:\Hstemp\1.prn` -> `C:\Hstemp\1.bmp`

## Testing Status
- DTG memory patch: CONFIRMED working (WriteProcessMemory succeeded)
- DTG TCP 9100: Connection reset (no hardware on dev PC)
- DTF memory patch: CONFIRMED working via DLL injection (2026-03-26)
- UV memory patch: CONFIRMED working via DLL injection (2026-03-26)

## See Also
- [printer-backend-integration.md](./printer-backend-integration.md) — Full integration guide for DTF & UV backends with offset tables, struct layouts, and injection workflow
