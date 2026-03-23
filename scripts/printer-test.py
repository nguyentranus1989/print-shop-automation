"""PrintFlow Printer Test — run on the PC connected to the printer.

Tests all automation methods against a LIVE PrintExp instance.
No dependencies except Python 3.10+ standard library + pycryptodome.

Install: pip install pycryptodome
Usage:   python printer-test.py

This script will:
1. Detect which PrintExp is running (DTG/DTF/UV)
2. Check TCP port 9100
3. Check HSRP port 5678 (if DTF/UV)
4. Extract WM_COMMAND button IDs
5. Try injecting a test file (if you provide one)
6. Try sending movement commands
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import socket
import struct
import subprocess
import sys
import time


# === DETECT PRINTEXP ===

def find_printexp():
    """Find running PrintExp process."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PrintExp.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True
        )
        if "PrintExp.exe" in result.stdout:
            return {"exe": "PrintExp.exe", "arch": "32-bit", "type": "DTG"}
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PrintExp_X64.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True
        )
        if "PrintExp_X64.exe" in result.stdout:
            return {"exe": "PrintExp_X64.exe", "arch": "64-bit", "type": "DTF_or_UV"}
    except Exception:
        pass

    return None


def detect_printer_type(printexp_dir):
    """Detect DTG vs DTF vs UV from files."""
    if not printexp_dir:
        return "unknown"

    has_kremote = os.path.exists(os.path.join(printexp_dir, "KRemoteMonitor.dll"))
    has_craft = os.path.exists(os.path.join(printexp_dir, "CraftFlow.dll"))

    if not has_kremote:
        return "DTG"
    elif has_craft:
        return "UV"
    else:
        return "DTF"


# === PORT CHECKS ===

def check_port(host, port, timeout=2):
    """Check if a TCP port is listening."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# === WM_COMMAND ===

def find_printexp_window():
    """Find PrintExp window handle."""
    user32 = ctypes.windll.user32
    results = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lp):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "PrintExp" in buf.value:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                results.append((hwnd, buf.value, cls.value))
        return True

    user32.EnumWindows(cb, 0)
    return results


def get_button_ids(hwnd):
    """Extract all button control IDs from PrintExp window."""
    user32 = ctypes.windll.user32
    buttons = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(child_hwnd, lp):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child_hwnd, cls, 256)
        txt = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(child_hwnd, txt, 256)
        cid = user32.GetDlgCtrlID(child_hwnd)
        en = user32.IsWindowEnabled(child_hwnd)
        vis = user32.IsWindowVisible(child_hwnd)

        if txt.value and "Button" in cls.value and cid < 65000:
            buttons.append({
                "id": cid,
                "text": txt.value,
                "enabled": bool(en),
                "visible": bool(vis),
            })
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return buttons


def send_wm_command(hwnd, ctrl_id):
    """Send WM_COMMAND to PrintExp."""
    user32 = ctypes.windll.user32
    WM_COMMAND = 0x0111
    return user32.PostMessageW(hwnd, WM_COMMAND, ctrl_id, 0)


# === TCP 9100 ===

def test_tcp9100(prn_path=None):
    """Test TCP 9100 file injection (DTG only)."""
    if not check_port("127.0.0.1", 9100):
        return {"status": "port_closed", "message": "Port 9100 not listening"}

    if not prn_path:
        return {"status": "port_open", "message": "Port 9100 listening — provide PRN file to test injection"}

    if not os.path.exists(prn_path):
        return {"status": "file_not_found", "message": f"PRN file not found: {prn_path}"}

    file_size = os.path.getsize(prn_path)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect(("127.0.0.1", 9100))

        sent = 0
        with open(prn_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)

        sock.close()
        return {
            "status": "sent",
            "bytes_sent": sent,
            "file_size": file_size,
            "complete": sent == file_size,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "bytes_sent": sent}


# === HSRP ===

def test_hsrp():
    """Test HSRP protocol on port 5678."""
    if not check_port("127.0.0.1", 5678):
        return {"status": "port_closed", "message": "Port 5678 not listening. Set PLATFORM_CONFIG ENABLE=1 in Project.ini"}

    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad

        KEY = b"Hs_Encrypt\x00\x00\x00\x00\x00\x00"
        IV = b"\x00" * 16

        # Build heartbeat
        header = b"HSRP" + struct.pack("<HHHH", 0, 0x0FFF, 0, 0) + b"\x00" * 8 + struct.pack("<I", 0)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("127.0.0.1", 5678))
        sock.sendall(header)

        # Try status query (cmd=2)
        payload = json.dumps({"CMD_ID": "10", "TASK_ID": "1", "PROCESS_ID": "0", "PRINT_TASK_ID": "1", "TYPE": "0"}).encode()
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        encrypted = cipher.encrypt(pad(payload, 16))

        cmd_header = b"HSRP" + struct.pack("<HH", 0, 2) + struct.pack("<H", 0) + b"\x00" * 10 + struct.pack("<I", len(encrypted))
        sock.sendall(cmd_header + encrypted)

        sock.settimeout(3)
        try:
            resp = sock.recv(4096)
            if resp[:4] == b"HSRP":
                r_len = struct.unpack_from("<I", resp, 20)[0]
                return {"status": "connected", "response_size": len(resp), "body_size": r_len, "message": "HSRP protocol working"}
        except socket.timeout:
            return {"status": "connected_no_response", "message": "Connected but no response to cmd=2"}

        sock.close()
    except ImportError:
        return {"status": "missing_dep", "message": "pip install pycryptodome"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# === MAIN ===

def main():
    print("=" * 60)
    print("  PrintFlow Printer Test")
    print("=" * 60)

    # 1. Detect PrintExp
    print("\n[1] PrintExp Detection")
    info = find_printexp()
    if info:
        print(f"  FOUND: {info['exe']} ({info['arch']})")
    else:
        print("  NOT RUNNING — start PrintExp first!")
        return

    # 2. Find PrintExp directory (from running process)
    print("\n[2] Printer Type Detection")
    # Try common paths
    for d in [
        r"C:\PrintExp",
        os.path.expanduser(r"~\Projects\DTG_autommation\PrintExp_5.7.7.1.12_MULTIWS"),
        os.path.expanduser(r"~\Projects\DTG_autommation\DTF_PrintExp_X64_V5.7.6.5.103.BS"),
        os.path.expanduser(r"~\Projects\DTG_autommation\UV_PrintExp_x64_V5.7.9.4.5008.BS_20240325-102100"),
    ]:
        if os.path.exists(d):
            ptype = detect_printer_type(d)
            print(f"  Type: {ptype} (from {d})")
            break
    else:
        ptype = "DTG" if info["arch"] == "32-bit" else "DTF_or_UV"
        print(f"  Type: {ptype} (guessed from architecture)")

    # 3. Check ports
    print("\n[3] Port Status")
    ports = {
        9100: "Raw Print (TCP 9100)",
        5001: "Mainboard Control",
        5678: "HSRP Command (Platform)",
        5679: "HSRP PRN Data (Platform)",
    }
    for port, desc in ports.items():
        status = "LISTENING" if check_port("127.0.0.1", port) else "CLOSED"
        print(f"  {port}: {status} — {desc}")

    # 4. Find window and buttons
    print("\n[4] Window & Button IDs")
    windows = find_printexp_window()
    if windows:
        hwnd, title, cls = windows[0]
        print(f"  Window: \"{title}\" (HWND=0x{hwnd:08X}, class={cls})")

        buttons = get_button_ids(hwnd)
        movement = [b for b in buttons if b["text"] in ["Left", "Right", "Ahead", "Back"] or
                    any(k in b["text"] for k in ["左移", "右移", "进料", "退料"])]
        controls = [b for b in buttons if b["text"] in ["Print", "Pause", "Cancel", "Check"] or
                    any(k in b["text"] for k in ["打印", "暂停", "取消"])]
        enabled_buttons = [b for b in buttons if b["enabled"]]

        print(f"  Total buttons: {len(buttons)}")
        print(f"  Enabled buttons: {len(enabled_buttons)}")
        print(f"  Movement buttons:")
        for b in movement:
            e = "ENABLED" if b["enabled"] else "DISABLED"
            print(f"    ID={b['id']:<8} {e:<10} \"{b['text']}\"")
        print(f"  Control buttons:")
        for b in controls:
            e = "ENABLED" if b["enabled"] else "DISABLED"
            print(f"    ID={b['id']:<8} {e:<10} \"{b['text']}\"")
    else:
        print("  Window not found")

    # 5. Test TCP 9100
    print("\n[5] TCP 9100 Test")
    result = test_tcp9100()
    print(f"  {result['status']}: {result['message']}")

    # 6. Test HSRP
    print("\n[6] HSRP Protocol Test")
    result = test_hsrp()
    print(f"  {result['status']}: {result['message']}")

    # 7. Test mainboard connection
    print("\n[7] Mainboard Connection")
    if check_port("192.168.127.10", 5001):
        print("  CONNECTED — mainboard reachable on 192.168.127.10:5001!")
    else:
        print("  NOT CONNECTED — 192.168.127.10:5001 unreachable")

    # Summary
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  PrintExp: {info['exe']} ({ptype})")
    print(f"  Mainboard: {'CONNECTED' if check_port('192.168.127.10', 5001) else 'NOT CONNECTED'}")
    print(f"  Port 9100: {'OPEN' if check_port('127.0.0.1', 9100) else 'CLOSED'}")
    print(f"  Port 5678: {'OPEN' if check_port('127.0.0.1', 5678) else 'CLOSED'}")
    if windows:
        print(f"  Buttons enabled: {len(enabled_buttons)}/{len(buttons)}")
    print()
    print("  To test file injection, run:")
    print("    python printer-test.py --inject C:\\path\\to\\file.prn")
    print()
    print("  To test movement (CAREFUL — printer will move!):")
    print("    python printer-test.py --move left")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--inject" and len(sys.argv) > 2:
        print(f"Injecting: {sys.argv[2]}")
        result = test_tcp9100(sys.argv[2])
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--move" and len(sys.argv) > 2:
        direction = sys.argv[2]
        windows = find_printexp_window()
        if windows:
            hwnd = windows[0][0]
            buttons = get_button_ids(hwnd)
            match = [b for b in buttons if direction.lower() in b["text"].lower()]
            if match:
                btn = match[0]
                print(f"Sending {direction} (ID={btn['id']}, enabled={btn['enabled']})")
                result = send_wm_command(hwnd, btn["id"])
                print(f"Result: {result}")
            else:
                print(f"Button '{direction}' not found")
        else:
            print("PrintExp window not found")
    else:
        main()
