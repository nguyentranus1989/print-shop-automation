"""Test DTF injection: patch NWReceive.exe memory + send file via TCP 9100.

Run as Administrator:
  powershell -Command "Start-Process python -ArgumentList 'scripts/test-dtf-inject.py' -Verb RunAs"
"""

import ctypes
import ctypes.wintypes as wt
import socket
import os
import sys

kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

PROCESS_ALL_ACCESS = 0x001FFFFF
TH32CS_SNAPPROCESS = 0x00000002
LIST_MODULES_ALL = 0x03


class MODULEINFO(ctypes.Structure):
    _fields_ = [('lpBaseOfDll', ctypes.c_void_p),
                ('SizeOfImage', ctypes.c_ulong),
                ('EntryPoint', ctypes.c_void_p)]

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong), ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                ('th32ModuleID', ctypes.c_ulong), ('cntThreads', ctypes.c_ulong),
                ('th32ParentProcessID', ctypes.c_ulong), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', ctypes.c_ulong), ('szExeFile', ctypes.c_char * 260)]


def find_pid(name_fragment):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    if not kernel32.Process32First(snap, ctypes.byref(entry)):
        kernel32.CloseHandle(snap)
        return None
    while True:
        n = entry.szExeFile.decode('ascii', errors='replace').lower()
        if name_fragment.lower() in n:
            pid = entry.th32ProcessID
            kernel32.CloseHandle(snap)
            return pid
        if not kernel32.Process32Next(snap, ctypes.byref(entry)):
            break
    kernel32.CloseHandle(snap)
    return None


def find_module_base(pid, module_name):
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        print(f"  OpenProcess failed for PID {pid}: error {ctypes.GetLastError()}")
        return None, None

    # Use HMODULE array (platform pointer size)
    HMODULE = ctypes.c_void_p
    modules = (HMODULE * 1024)()
    needed = ctypes.c_ulong()
    result = psapi.EnumProcessModulesEx(handle, ctypes.byref(modules), ctypes.sizeof(modules), ctypes.byref(needed), LIST_MODULES_ALL)

    if not result:
        kernel32.CloseHandle(handle)
        return None, None

    count = needed.value // ctypes.sizeof(HMODULE)
    for i in range(count):
        mod = modules[i]
        if mod is None:
            continue
        name = ctypes.create_unicode_buffer(260)
        # Cast module handle to proper type for the API call
        psapi.GetModuleFileNameExW(handle, ctypes.c_void_p(mod), name, 260)
        if module_name.lower() in name.value.lower():
            info = MODULEINFO()
            psapi.GetModuleInformation(handle, ctypes.c_void_p(mod), ctypes.byref(info), ctypes.sizeof(info))
            kernel32.CloseHandle(handle)
            return info.lpBaseOfDll, info.SizeOfImage

    kernel32.CloseHandle(handle)
    return None, None


def patch_memory(pid, address, data):
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return False
    # Change memory protection to writable (.rdata is read-only by default)
    PAGE_READWRITE = 0x04
    old_protect = ctypes.c_ulong()
    kernel32.VirtualProtectEx(handle, ctypes.c_void_p(address), len(data), PAGE_READWRITE, ctypes.byref(old_protect))
    # Write
    written = ctypes.c_size_t(0)
    buf = ctypes.create_string_buffer(data)
    result = kernel32.WriteProcessMemory(handle, ctypes.c_void_p(address), buf, len(data), ctypes.byref(written))
    # Restore original protection
    kernel32.VirtualProtectEx(handle, ctypes.c_void_p(address), len(data), old_protect.value, ctypes.byref(old_protect))
    kernel32.CloseHandle(handle)
    return bool(result)


def read_memory(pid, address, size):
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return None
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    result = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read))
    kernel32.CloseHandle(handle)
    return buf.raw if result else None


# =========================================================================
print("=" * 60)
print("  DTF PrintExp — Memory Patch + TCP 9100 Injection Test")
print("=" * 60)

# Check admin
is_admin = ctypes.windll.shell32.IsUserAnAdmin()
print(f"\nAdmin: {bool(is_admin)}")
if not is_admin:
    print("ERROR: Must run as Administrator!")
    input("Press Enter to exit...")
    sys.exit(1)

# Find NWReceive.exe
nw_pid = find_pid("nwreceive")
if not nw_pid:
    print("ERROR: NWReceive.exe not running. Start PrintExp first.")
    input("Press Enter to exit...")
    sys.exit(1)
print(f"NWReceive.exe PID: {nw_pid}")

# Find base address
nw_base, nw_size = find_module_base(nw_pid, "NWReceive.exe")
if not nw_base:
    print("ERROR: Could not find NWReceive.exe module base")
    input("Press Enter to exit...")
    sys.exit(1)
print(f"NWReceive.exe base: 0x{nw_base:016X} (size: {nw_size})")

# The file offset 0x005A73 maps to RVA 0x006A73 (in .rdata section)
# RVA = section_VA + (file_offset - section_raw_offset) = 0x6000 + (0x5A73 - 0x5000) = 0x6A73
RVA_OFFSET = 0x006A73
target = nw_base + RVA_OFFSET
current = read_memory(nw_pid, target, 20)
if current:
    print(f"Current at 0x{target:016X}: {repr(current)}")
else:
    print("WARNING: Could not read memory at target offset")

# Patch filename
job_name = "test_dtf.prn"
# Original: ~section%d.prn (14 bytes)
patch = job_name.encode('ascii') + b'\x00' * (14 - len(job_name))
print(f"\nPatching to: {repr(patch)}")

ok = patch_memory(nw_pid, target, patch)
print(f"Patch result: {'OK' if ok else 'FAILED'}")

# Verify
verify = read_memory(nw_pid, target, 20)
if verify:
    print(f"After patch:  {repr(verify)}")

# Check TCP 9100
print(f"\nChecking TCP 9100...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    sock.connect(('127.0.0.1', 9100))
    print("TCP 9100: CONNECTED")
    sock.close()
except Exception as e:
    print(f"TCP 9100: FAILED ({e})")
    print("\nMemory patch was applied but cannot send file (no TCP 9100).")
    print("On a machine with the printer connected, the full flow would work.")
    input("Press Enter to exit...")
    sys.exit(0)

# Send file
prn_path = input("\nPRN file path (or Enter to skip): ").strip()
if not prn_path:
    print("Skipped file send. Memory patch was applied.")
    input("Press Enter to exit...")
    sys.exit(0)

if not os.path.exists(prn_path):
    print(f"File not found: {prn_path}")
    input("Press Enter to exit...")
    sys.exit(1)

size = os.path.getsize(prn_path)
print(f"Sending {prn_path} ({size:,} bytes)...")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(120)
sock.connect(('127.0.0.1', 9100))

sent = 0
with open(prn_path, 'rb') as f:
    while True:
        chunk = f.read(65536)
        if not chunk:
            break
        sock.sendall(chunk)
        sent += len(chunk)
        pct = int(sent / size * 100)
        print(f"\r  {pct}% ({sent:,} / {size:,})", end='', flush=True)

sock.close()
print(f"\nDone! Sent {sent:,} bytes.")
print(f'Check PrintExp — should show "{job_name}" with preview!')
input("Press Enter to exit...")
