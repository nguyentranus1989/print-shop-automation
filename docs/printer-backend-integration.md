# PrintExp Backend Integration Guide

> Deep technical reference for DLL injection backends (DTF and UV).
> Covers memory structures, vtable offsets, and file vector management.

**See also:** [printer-support-matrix.md](./printer-support-matrix.md) for overall feature comparison across all 4 builds (DTG, DTF v5.7.6, DTF v5.8.2, UV).

---

## Overview

The PrintFlow agent controls PrintExp printers via three mechanisms:

1. **TCP 9100** — Raw PRN file injection (works on all 4 builds)
2. **Memory patching / DLL injection** — Filename injection into internal memory structures
   - DTG (x86): WriteProcessMemory approach
   - DTF v5.7.6 (x64): DLL injection via vtable[7]
   - DTF v5.8.2 (x64): DLL injection via vtable[7] (offsets TBD)
   - UV v5.7.9 (x64): DLL injection via vtable[9]
3. **Win32 PostMessage** — UI automation (print/pause/resume/cancel, axis movement) — *not yet wired*

This guide documents the **DLL injection approach** for DTF and UV, which differs significantly between builds.

---

## Architecture Comparison

| Component | DTF v5.7.6 | DTF v5.8.2 | UV v5.7.9.4.5008 |
|-----------|-----------|-----------|------------------|
| **Global pointer offset** | `EXE+0x176B98` | *TBD* | `EXE+0x1D2F10` |
| **CTaskManager access** | `appVt[22]` call | *TBD* | `device_obj+0x70` |
| **AddFile vtable index** | `vtable[7]` | `vtable[7]` | `vtable[9]` |
| **File vector offset** | `+0x28` | *TBD* | `+0x08` |
| **Display vector offset** | `+0x48` | *TBD* | `+0x28` |
| **CTaskInfo struct size** | 0xB08 | *TBD* | 0xCA0 |
| **HSKRipFile creator offset** | `+0x5B0` | *TBD* | `+0x140` |
| **UI refresh message** | `0x7F4` | `0x7F4` (same) | `0x7F4` (same) |

---

## DTF Backend (v5.7.6)

### Global Pointer Location

```c
// PrintExp.exe base address + 0x176B98
// Contains pointer to global app context
void* global_ptr = *(void**)(exe_base + 0x176B98);
```

### CTaskManager Access

Via application vtable:

```c
// From global pointer, dereference to vtable
void** app_vtable = *(void***)(global_ptr);

// Call vtable[22] -> CTaskManager::GetInstance()
typedef void* (*GetTaskManager)(void*);
GetTaskManager get_tm = (GetTaskManager)app_vtable[22];
void* task_mgr = get_tm(global_ptr);
```

### File Addition (AddFile)

```c
// task_mgr is CTaskManager instance
// vtable[7] = AddFile(const char* path_to_prn_file)
typedef void (*AddFile)(void*, const char*);
AddFile add_file = (AddFile)((void**)task_mgr)[7];
add_file(task_mgr, "C:\\path\\to\\file.prn");
```

**Behavior:** AddFile **PREPENDS** the file to the task queue (inserts at index 0).

### Display Vector Population

After AddFile, manually copy the new task info to the display vector:

```c
// File vector at task_mgr+0x28
void** file_vector = *(void***)(task_mgr + 0x28);
if (file_vector && *file_vector) {
  CTaskInfo* new_task = *(CTaskInfo**)file_vector;

  // Display vector at task_mgr+0x48
  void** display_vector = *(void***)(task_mgr + 0x48);

  // Copy to index 0 (prepended)
  *(CTaskInfo**)(display_vector) = new_task;
}
```

### Struct Layout (CTaskInfo)

Size: **0xB08** bytes

| Offset | Field | Type | Purpose |
|--------|-------|------|---------|
| `+0x00` | — | — | Unknown header |
| `+0x5B0` | filename_ptr | `char*` | Points to filename string (e.g., "file.prn") |
| `+0x5B8` | — | — | Other metadata |

---

## UV Backend (v5.7.9.4.5008)

### Discovery Method

Memory scanning + TCC compiler (no Ghidra required):

```bash
# 1. Scan PrintExp.exe for signature patterns (Python memory scanner)
python scan_uv_printexp.py

# 2. Compile and inject via TCC (lightweight C compiler)
pip install tccbox
tcc -o inject_uv.dll inject_uv_printexp.c
```

### Global Pointer Location

```c
// PrintExp.exe base address + 0x1D2F10
// Contains pointer to device context
void* device_obj = *(void**)(exe_base + 0x1D2F10);
```

### CTaskManager Access

Direct structure member access (different from DTF):

```c
// device_obj+0x70 is CTaskManager instance
void* task_mgr = *(void**)(device_obj + 0x70);
```

### File Addition (AddFile)

```c
// task_mgr is CTaskManager instance
// vtable[9] = AddFile(const char* path_to_prn_file)
typedef void (*AddFile)(void*, const char*);
AddFile add_file = (AddFile)((void**)task_mgr)[9];
add_file(task_mgr, "C:\\path\\to\\file.prn");
```

**Behavior:** Same as DTF — AddFile **PREPENDS** (inserts at index 0).

### File Vector Inspection

After AddFile, inspect the file vector to find the new entry:

```c
// File vector at task_mgr+0x08 (UV uses +0x08, NOT +0x28)
void** file_vector = *(void***)(task_mgr + 0x08);

// Read current file count (vector may have expanded)
// new_task = *(CTaskInfo**)file_vector[0] (prepended)
CTaskInfo* new_task = *(CTaskInfo**)file_vector;
```

### Display Vector Population

**CRITICAL:** UV uses a DIFFERENT display vector type. DO NOT copy to the print vector.

```c
// Display vector (UI list) at task_mgr+0x28 (UV uses +0x28)
void** display_vector = *(void***)(task_mgr + 0x28);

// Copy ONLY to display vector, NOT print vector
// Print vector (+0x48 in UV) has different object layout
*(CTaskInfo**)(display_vector) = new_task;
```

**Why?** Copying to the wrong vector causes R6025 pure virtual call error (program crash).

### Struct Layout (CTaskInfo)

Size: **0xCA0** bytes (larger than DTF)

| Offset | Field | Type | Purpose |
|--------|-------|------|---------|
| `+0x00` | — | — | Unknown header |
| `+0x140` | filename_ptr | `char*` | Points to filename string |
| `+0x148` | — | — | Other metadata |

---

## UI Refresh

Both DTF and UV use the **same UI refresh mechanism**:

```c
// Send message to PrintExp main window
PostMessageW(hwnd, WM_USER + 0x7F4, 0, 0);
```

This triggers PrintExp to redraw the job queue UI and show the newly injected job.

---

## Injection Workflow

### 1. DLL Injection Setup

```c
// Find PrintExp process
HANDLE proc = OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_WRITE, FALSE, pid);

// Get PrintExp.exe base address
HMODULE exe_base = GetModuleHandle("PrintExp.exe");  // From target process context
```

### 2. Memory Read Helper

```c
void read_mem(HANDLE proc, void* addr, void* out, size_t len) {
  ReadProcessMemory(proc, addr, out, len, NULL);
}
```

### 3. Memory Write Helper

```c
void write_mem(HANDLE proc, void* addr, void* data, size_t len) {
  WriteProcessMemory(proc, addr, data, len, NULL);
  FlushInstructionCache(proc, addr, len);
}
```

### 4. Pointer Chain Resolution

```c
// For DTF:
//   global_app -> app_vtable[22] -> task_mgr
void* resolve_dtf_task_mgr(HANDLE proc, void* exe_base) {
  void* global_ptr = exe_base + 0x176B98;
  void* app_context;
  read_mem(proc, global_ptr, &app_context, 8);

  void** vtable;
  read_mem(proc, app_context, &vtable, 8);

  void* task_mgr;
  read_mem(proc, vtable[22], &task_mgr, 8);
  return task_mgr;
}

// For UV:
//   device_obj (0x1D2F10) -> [+0x70] -> task_mgr
void* resolve_uv_task_mgr(HANDLE proc, void* exe_base) {
  void* device_obj = exe_base + 0x1D2F10;
  void* device_context;
  read_mem(proc, device_obj, &device_context, 8);

  void* task_mgr;
  read_mem(proc, (void*)((uintptr_t)device_context + 0x70), &task_mgr, 8);
  return task_mgr;
}
```

### 5. File Injection Sequence

```c
// 1. Get task manager pointer (DTF or UV based on version)
void* task_mgr = resolve_dtf_task_mgr(proc, exe_base);  // or UV version

// 2. Call AddFile to queue the job
// (DLL code injected into PrintExp, called via DLL export)
call_addfile(task_mgr, "C:\\path\\to\\file.prn");

// 3. Small delay for AddFile to complete
Sleep(100);

// 4. Diff file vector to find new entry
CTaskInfo* new_task = get_new_task_from_vector(task_mgr);

// 5. Copy to display vector
copy_to_display_vector(task_mgr, new_task);

// 6. Send UI refresh message
PostMessageW(hwnd, WM_USER + 0x7F4, 0, 0);
```

---

## Dangerous Vtable Indices (UV Only)

These vtable indices cause immediate R6025 pure virtual call crash on UV:

| Index | Status | Notes |
|-------|--------|-------|
| `vt[6]` | ⚠️ CRASH | Unknown virtual method |
| `vt[11]` | ⚠️ CRASH | Unknown virtual method |
| `vt[12]` | ⚠️ CRASH | Unknown virtual method |

**Workaround:** Use only well-tested indices (`vt[9]` for AddFile, verified safe).

---

## Debugging Tips

### PrintExp Crashes with R6025

Indicates a pure virtual function call (calling a pure virtual method on deleted object or wrong vtable).

**Common causes:**
- Copied CTaskInfo to wrong vector (print vector instead of display vector)
- Used wrong offset for device_obj or task_mgr
- AddFile not called before copying to display vector

**Solution:**
- Verify offset table at top of integration guide
- Only copy to display vector (not print vector)
- Ensure 100ms delay after AddFile call

### Job Not Appearing in UI

- AddFile succeeded (job in file vector)
- Display vector copy failed silently
- **Solution:** Verify display vector offset, ensure CTaskInfo pointer is valid

### UI Refresh Hangs

- WM_USER + 0x7F4 message sent to wrong window
- **Solution:** Verify PrintExp HWND via EnumWindows

---

## Version Detection

Auto-detect printer type in agent:

```python
# From agent config or memory scan
def detect_version(exe_path: str) -> str:
    with open(exe_path, 'rb') as f:
        # Check file size or PE header version
        # DTF v5.7.6 ~ 8-9 MB
        # UV v5.7.9+ ~ 10-12 MB
        stat = os.stat(exe_path)
        if stat.st_size > 9_500_000:
            return 'uv'
        else:
            return 'dtf'
```

---

## Implementation Files

Reference implementations in DTG_autommation repo:

| File | Purpose |
|------|---------|
| `scripts/inject_uv_printexp.c` | UV DLL injection source |
| `scripts/inject_uv.dll` | Compiled UV injection DLL |
| `scripts/add_to_uv_printexp.py` | Python script calling UV DLL |
| `scripts/scan_uv_printexp.py` | Memory scanner for offset discovery |

---

## DTF v5.8.2 (x64 Unicode) — TBD

For DTF v5.8.2 offset discovery:

1. Run Python memory scanner on actual v5.8.2 executable
2. Search for signature patterns (same method as UV discovery)
3. Identify global pointer (estimate: EXE+0x176B98, same as v5.7.6)
4. Verify vtable indices and offsets
5. Compile and test DLL injection on actual hardware
6. Update offset table in this guide

Expected variance from v5.7.6: ~5% (likely same vtable[7] approach, similar offsets).

---

## Next Steps

1. **Discover DTF v5.8.2 offsets** — Run memory scanner, update offset table
2. **Test on production hardware** — Verify DTF v5.8.2 and UV DLL injection on actual printers
3. **Integrate into PrintFlow agent** — Detect version, call appropriate backend
4. **Wire job control** — Implement Print/Pause/Resume/Cancel (WM_COMMAND stubs)
5. **Error handling** — Graceful fallback if memory offsets shift (version change)
6. **Logging & telemetry** — Track injection success/failure rates
