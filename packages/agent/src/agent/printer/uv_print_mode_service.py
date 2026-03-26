"""UV print mode service — applies direction + mirror + ink presets.

Wraps the logic from DTG_autommation/scripts/uv_print_mode.py for use
by the agent API. Modifies DebugParam.ini and CTaskInfo memory directly.
"""

from __future__ import annotations

import configparser
import logging
import os
import struct
from typing import Any

logger = logging.getLogger(__name__)

# Ink channel indices
COLOR_CHANNELS = [0, 1, 2, 3, 4, 5]
WHITE_CHANNELS = [6, 7]
VARNISH_CHANNELS = [8]

CHANNEL_NAMES = {
    0: "Cyan", 1: "Magenta", 2: "Yellow", 3: "Black",
    4: "Light Cyan", 5: "Light Magenta",
    6: "White 1", 7: "White 2", 8: "Varnish",
}

# CTaskInfo memory offsets (UV v5.7.9)
MULTI_INK_OFFSET = 0x708
DEVICE_RVA = 0x1D2F10
TASKMGR_OFFSET = 0x70
FILE_VEC_BEGIN = 0x08
FILE_VEC_END = 0x10

PRESETS: dict[str, dict[str, Any]] = {
    "forward-color": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS, "disable": WHITE_CHANNELS + VARNISH_CHANNELS,
        "desc": "Forward, color only",
    },
    "forward-white": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS, "disable": VARNISH_CHANNELS,
        "desc": "Forward, color + white",
    },
    "forward-varnish": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS + VARNISH_CHANNELS, "disable": WHITE_CHANNELS,
        "desc": "Forward, color + varnish",
    },
    "forward-white-varnish": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS + VARNISH_CHANNELS, "disable": [],
        "desc": "Forward, all ink",
    },
    "forward-mirror-color": {
        "y_dir": 0, "mirror_h": 1, "mirror_v": 0,
        "enable": COLOR_CHANNELS, "disable": WHITE_CHANNELS + VARNISH_CHANNELS,
        "desc": "Forward mirror, color only",
    },
    "forward-mirror-white": {
        "y_dir": 0, "mirror_h": 1, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS, "disable": VARNISH_CHANNELS,
        "desc": "Forward mirror, color + white",
    },
    "forward-mirror-white-varnish": {
        "y_dir": 0, "mirror_h": 1, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS + VARNISH_CHANNELS, "disable": [],
        "desc": "Forward mirror, all ink",
    },
    "reverse-color": {
        "y_dir": 1, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS, "disable": WHITE_CHANNELS + VARNISH_CHANNELS,
        "desc": "Reverse, color only",
    },
    "reverse-white": {
        "y_dir": 1, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS, "disable": VARNISH_CHANNELS,
        "desc": "Reverse, color + white",
    },
    "reverse-white-varnish": {
        "y_dir": 1, "mirror_h": 0, "mirror_v": 0,
        "enable": COLOR_CHANNELS + WHITE_CHANNELS + VARNISH_CHANNELS, "disable": [],
        "desc": "Reverse, all ink",
    },
    "white-only": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": WHITE_CHANNELS, "disable": COLOR_CHANNELS + VARNISH_CHANNELS,
        "desc": "White ink only",
    },
    "varnish-only": {
        "y_dir": 0, "mirror_h": 0, "mirror_v": 0,
        "enable": VARNISH_CHANNELS, "disable": COLOR_CHANNELS + WHITE_CHANNELS,
        "desc": "Varnish only",
    },
}


class UVPrintModeService:
    """Manages UV print mode presets — direction, mirror, and ink channels."""

    def __init__(self, printexp_dir: str) -> None:
        self._debug_param = os.path.join(printexp_dir, "Data", "DebugParam.ini")
        self._temp_ini = os.path.join(printexp_dir, "Data", "Temp.ini")

    def get_presets(self) -> list[dict[str, str]]:
        """Return list of available presets with name and description."""
        return [
            {"name": name, "desc": p["desc"]}
            for name, p in PRESETS.items()
        ]

    def get_current_mode(self) -> dict[str, Any]:
        """Read current direction/mirror settings from INI."""
        d = self._read_debug_param()
        dir_name = {0: "Forward", 1: "Reverse"}.get(d["y_dir"], "Unknown")
        mirror = "None"
        if d["mirror_h"] and d["mirror_v"]:
            mirror = "Both"
        elif d["mirror_h"]:
            mirror = "Horizontal"
        elif d["mirror_v"]:
            mirror = "Vertical"

        # Try to detect which preset matches
        active_preset = None
        for name, p in PRESETS.items():
            if (p["y_dir"] == d["y_dir"] and
                    p["mirror_h"] == d["mirror_h"] and
                    p["mirror_v"] == d["mirror_v"]):
                active_preset = name
                break

        return {
            "direction": dir_name,
            "mirror": mirror,
            "y_dir": d["y_dir"],
            "mirror_h": d["mirror_h"],
            "mirror_v": d["mirror_v"],
            "active_preset": active_preset,
            "speed": self._read_speed(),
        }

    def apply_preset(self, preset_name: str) -> dict[str, Any]:
        """Apply a named preset (direction + mirror + ink channels)."""
        if preset_name not in PRESETS:
            return {"success": False, "error": f"Unknown preset: {preset_name}"}

        p = PRESETS[preset_name]

        # 1. Write direction/mirror to INI
        self._write_debug_param(
            y_dir=p["y_dir"], mirror_h=p["mirror_h"], mirror_v=p["mirror_v"]
        )

        # 2. Set ink channels via memory write (if PrintExp is running)
        ink_result = self._apply_ink_channels(p["enable"], p["disable"])

        return {
            "success": True,
            "preset": preset_name,
            "desc": p["desc"],
            "ink_applied": ink_result,
        }

    def _read_debug_param(self) -> dict[str, int]:
        cp = configparser.ConfigParser()
        cp.read(self._debug_param)
        s = "DEBUG_PARAM"
        return {
            "y_dir": cp.getint(s, "Y_PRINT_DIR", fallback=0),
            "mirror_h": cp.getint(s, "MIRROR_HOR", fallback=0),
            "mirror_v": cp.getint(s, "MIRROR_VER", fallback=0),
        }

    def _read_speed(self) -> int:
        cp = configparser.ConfigParser()
        try:
            cp.read(self._temp_ini, encoding="utf-8-sig")
        except Exception:
            return 100
        return cp.getint("PRINT_SPEED", "PRINT_SPEED_PERCENT", fallback=100)

    def _write_debug_param(
        self, y_dir: int, mirror_h: int, mirror_v: int
    ) -> None:
        # Read existing to preserve x_dir and origin
        cp = configparser.ConfigParser()
        cp.read(self._debug_param)
        s = "DEBUG_PARAM"
        x_dir = cp.getint(s, "X_PRINT_DIR", fallback=2)
        origin = cp.getint(s, "ORIGIN_POS", fallback=0)

        with open(self._debug_param, "w") as f:
            f.write("[DEBUG_PARAM]\n")
            f.write(f"X_PRINT_DIR={x_dir}\n")
            f.write(f"Y_PRINT_DIR={y_dir}\n")
            f.write(f"MIRROR_HOR={mirror_h}\n")
            f.write(f"MIRROR_VER={mirror_v}\n")
            f.write(f"ORIGIN_POS={origin}\n")

        logger.info("DebugParam.ini: y_dir=%d mirror_h=%d mirror_v=%d",
                     y_dir, mirror_h, mirror_v)

    def _apply_ink_channels(
        self, enable: list[int], disable: list[int]
    ) -> bool:
        """Write ink channel settings to CTaskInfo memory. Returns True if applied."""
        try:
            import ctypes
            import ctypes.wintypes as wt
            import subprocess
        except ImportError:
            return False

        # Find PrintExp PID
        r = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq PrintExp_X64.exe',
             '/NH', '/FO', 'CSV'],
            capture_output=True, text=True
        )
        pid = None
        for line in r.stdout.strip().split('\n'):
            if 'PrintExp' in line:
                pid = int(line.strip('"').split('","')[1])
                break
        if not pid:
            logger.warning("PrintExp not running — ink channels not set")
            return False

        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        access = 0x0010 | 0x0020 | 0x0008 | 0x0400
        proc = k32.OpenProcess(access, False, pid)
        if not proc:
            logger.error("Cannot open PrintExp process")
            return False

        try:
            # Get EXE base
            exe_base = self._get_module_base(proc, psapi, "PrintExp_X64.exe")
            if not exe_base:
                return False

            # Walk to task list
            tasks = self._get_task_addresses(proc, k32, exe_base)
            for task_addr in tasks:
                for ch in enable:
                    val = struct.pack('<f', 1.0)
                    self._write_mem(proc, k32, task_addr + MULTI_INK_OFFSET + ch * 4, val)
                for ch in disable:
                    val = struct.pack('<f', 0.0)
                    self._write_mem(proc, k32, task_addr + MULTI_INK_OFFSET + ch * 4, val)

            logger.info("Ink channels set for %d tasks", len(tasks))
            return len(tasks) > 0
        finally:
            k32.CloseHandle(proc)

    @staticmethod
    def _get_module_base(proc, psapi, module_name: str) -> int | None:
        import ctypes
        import ctypes.wintypes as wt

        class MODULEINFO(ctypes.Structure):
            _fields_ = [
                ("lpBaseOfDll", ctypes.c_void_p),
                ("SizeOfImage", wt.DWORD),
                ("EntryPoint", ctypes.c_void_p),
            ]

        hMods = (wt.HMODULE * 1024)()
        cb = wt.DWORD()
        psapi.EnumProcessModulesEx(proc, ctypes.byref(hMods), ctypes.sizeof(hMods), ctypes.byref(cb), 3)
        for i in range(cb.value // ctypes.sizeof(wt.HMODULE)):
            buf = ctypes.create_string_buffer(260)
            psapi.GetModuleBaseNameA(proc, wt.HMODULE(hMods[i]), buf, 260)
            if module_name.lower() in buf.value.decode('ascii', 'ignore').lower():
                info = MODULEINFO()
                psapi.GetModuleInformation(proc, wt.HMODULE(hMods[i]), ctypes.byref(info), ctypes.sizeof(info))
                return info.lpBaseOfDll
        return None

    @staticmethod
    def _get_task_addresses(proc, k32, exe_base: int) -> list[int]:
        import ctypes
        import struct as _struct

        def _read_u64(addr: int) -> int:
            buf = ctypes.create_string_buffer(8)
            rd = ctypes.c_size_t(0)
            ok = k32.ReadProcessMemory(proc, ctypes.c_void_p(addr), buf, 8, ctypes.byref(rd))
            return _struct.unpack('<Q', buf.raw)[0] if ok and rd.value == 8 else 0

        dev = _read_u64(exe_base + DEVICE_RVA)
        if not dev:
            return []
        tm = _read_u64(dev + TASKMGR_OFFSET)
        if not tm:
            return []
        fb = _read_u64(tm + FILE_VEC_BEGIN)
        fe = _read_u64(tm + FILE_VEC_END)
        count = (fe - fb) // 8 if fb and fe and fe >= fb else 0
        return [_read_u64(fb + i * 8) for i in range(count)]

    @staticmethod
    def _write_mem(proc, k32, addr: int, data: bytes) -> bool:
        import ctypes
        written = ctypes.c_size_t(0)
        return bool(k32.WriteProcessMemory(
            proc, ctypes.c_void_p(addr), data, len(data), ctypes.byref(written)
        ))
