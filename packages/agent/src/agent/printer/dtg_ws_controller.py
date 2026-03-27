"""DTG MULTIWS workstation controller — selects WS:0/WS:1 via memory patch.

Mechanism (from PrintExp.exe RE):
  CJobProcess+0x90 is a DWORD bitmask controlling enabled workstations.
  Bit 0 = WS:0, Bit 1 = WS:1. Write 1 for WS:0 only, 2 for WS:1 only, 3 for both.

  ThreadWorkstation (VA 0x00421F80) reads this+0x90 in a loop:
    for ws in 0..2:
        if (1 << ws) & this->m_nWSMask: process_ws(ws)

Finding CJobProcess:
  Scan PrintExp.exe's .data+BSS region for a heap pointer whose target
  has a valid bitmask at +0x90 (1-7) and valid flags at +0x78 (0 or 1).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import struct
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# CJobProcess field offsets (from Ghidra/capstone RE of PrintExp.exe v5.7.7.1.12)
_WS_BITMASK_OFFSET = 0x90      # DWORD: WS enable bitmask (1=WS0, 2=WS1, 3=both)
_STATUS_FLAG_OFFSET = 0x78      # DWORD: 0 or 1 (thread running flag)
_CURRENT_WS_OFFSET = 0x100     # PTR: current WS entry pointer

# PrintExp.exe known addresses (32-bit, no ASLR, image base 0x00400000)
_PRINTEXP_IMAGE_BASE = 0x00400000
_DATA_SECTION_RVA = 0x00134000  # .data section start
_BSS_END_ESTIMATE = 0x00137000  # approx end of .data+BSS (before .rsrc)

# Win32 constants
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000

kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None


def _open_process(pid: int) -> Optional[int]:
    """Open process with read+write access."""
    if kernel32 is None:
        return None
    access = PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION
    handle = kernel32.OpenProcess(access, False, pid)
    return handle if handle else None


def _read_dword(handle: int, address: int) -> Optional[int]:
    """Read a 32-bit DWORD from process memory."""
    buf = ctypes.c_uint32()
    read = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(handle, address, ctypes.byref(buf), 4, ctypes.byref(read))
    return buf.value if ok and read.value == 4 else None


def _write_dword(handle: int, address: int, value: int) -> bool:
    """Write a 32-bit DWORD to process memory."""
    buf = struct.pack("<I", value)
    written = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(handle, address, buf, 4, ctypes.byref(written))
    return bool(ok and written.value == 4)


def _is_valid_heap_ptr(val: int) -> bool:
    """Check if a value looks like a valid 32-bit heap pointer."""
    return 0x00100000 <= val <= 0x7FFFFFFF


def _find_cjobprocess(handle: int) -> Optional[int]:
    """Scan PrintExp .data+BSS for a pointer to CJobProcess instance.

    Strategy: read each DWORD in the .data/BSS region. If it looks like
    a heap pointer, read target+0x90 (bitmask) and target+0x78 (flag).
    If bitmask is 1-7 and flag is 0 or 1, it's likely CJobProcess.
    """
    scan_start = _PRINTEXP_IMAGE_BASE + _DATA_SECTION_RVA
    scan_end = _PRINTEXP_IMAGE_BASE + _BSS_END_ESTIMATE
    scan_size = scan_end - scan_start

    # Read entire .data+BSS block at once for speed
    buf = (ctypes.c_byte * scan_size)()
    read = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(handle, scan_start, ctypes.byref(buf), scan_size, ctypes.byref(read))
    if not ok or read.value < scan_size // 2:
        logger.warning("Failed to read .data section at 0x%X", scan_start)
        return None

    candidates = []
    data = bytes(buf[:read.value])

    for i in range(0, len(data) - 4, 4):
        val = struct.unpack_from("<I", data, i)[0]
        if not _is_valid_heap_ptr(val):
            continue

        # Read target+0x90 (WS bitmask) and target+0x78 (status flag)
        bitmask = _read_dword(handle, val + _WS_BITMASK_OFFSET)
        if bitmask is None or bitmask == 0 or bitmask > 7:
            continue

        flag78 = _read_dword(handle, val + _STATUS_FLAG_OFFSET)
        if flag78 is None or flag78 > 1:
            continue

        # Additional check: +0x100 should be 0 or a valid pointer
        ptr100 = _read_dword(handle, val + _CURRENT_WS_OFFSET)
        if ptr100 is not None and (ptr100 == 0 or _is_valid_heap_ptr(ptr100)):
            addr_in_data = scan_start + i
            candidates.append((val, bitmask, flag78, addr_in_data))
            logger.debug(
                "CJobProcess candidate: ptr=0x%X bitmask=%d flag78=%d at data+0x%X",
                val, bitmask, flag78, i,
            )

    if not candidates:
        logger.warning("No CJobProcess candidates found")
        return None

    if len(candidates) == 1:
        addr = candidates[0][0]
        logger.info("CJobProcess found at 0x%X (bitmask=%d)", addr, candidates[0][1])
        return addr

    # Multiple candidates — prefer one with bitmask 3 (dual WS normal)
    for c in candidates:
        if c[1] == 3:
            logger.info("CJobProcess found at 0x%X (bitmask=3, dual WS)", c[0])
            return c[0]

    # Fall back to first candidate
    addr = candidates[0][0]
    logger.info("CJobProcess (best guess) at 0x%X (bitmask=%d)", addr, candidates[0][1])
    return addr


class DTGWorkstationController:
    """Controls WS selection on DTG MULTIWS printers via memory patch."""

    def __init__(self) -> None:
        self._cjob_addr: Optional[int] = None
        self._proc_handle: Optional[int] = None

    def select_workstation(self, pid: int, ws: int) -> bool:
        """Force PrintExp to use a specific workstation.

        Args:
            pid: PrintExp.exe process ID.
            ws: 0 for WS:0, 1 for WS:1, or -1 to restore both.

        Returns:
            True if the patch was applied successfully.
        """
        if sys.platform != "win32":
            logger.error("WS control requires Windows")
            return False

        if ws == -1:
            bitmask = 3  # both WS enabled
        elif ws in (0, 1):
            bitmask = 1 << ws  # 1=WS:0, 2=WS:1
        else:
            logger.error("Invalid WS index: %d", ws)
            return False

        handle = _open_process(pid)
        if not handle:
            logger.error("Cannot open PrintExp process (PID %d)", pid)
            return False

        try:
            # Find CJobProcess instance (cache for subsequent calls)
            if self._cjob_addr is None:
                self._cjob_addr = _find_cjobprocess(handle)
            if self._cjob_addr is None:
                logger.error("CJobProcess instance not found in PrintExp memory")
                return False

            # Write WS bitmask
            target = self._cjob_addr + _WS_BITMASK_OFFSET
            ok = _write_dword(handle, target, bitmask)
            if ok:
                logger.info(
                    "WS bitmask set to %d (WS:%s) at CJobProcess+0x90 (0x%X)",
                    bitmask, ws if ws >= 0 else "both", target,
                )
            else:
                logger.error("WriteProcessMemory failed at 0x%X", target)
            return ok
        finally:
            kernel32.CloseHandle(handle)

    def restore_both(self, pid: int) -> bool:
        """Restore normal dual-WS operation (bitmask=3)."""
        return self.select_workstation(pid, -1)

    def invalidate_cache(self) -> None:
        """Clear cached CJobProcess address (e.g., after PrintExp restart)."""
        self._cjob_addr = None
