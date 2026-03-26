# Agent — Printer Backend Implementation

> Guide for PrintFlow agent developers on calling DTF and UV injection backends.

---

## Quick Reference

| Printer Type | Detection | Memory Backend | DLL Source | Status |
|--------------|-----------|-----------------|------------|--------|
| DTG | Exe name + version | WriteProcessMemory | N/A | Production |
| DTF | File size ~8-9MB | DLL injection (vtable[7]) | DTG_automation/scripts/inject_dtf.dll | Production (2026-03-26) |
| UV | File size >9.5MB | DLL injection (vtable[9]) | DTG_automation/scripts/inject_uv.dll | Production (2026-03-26) |

---

## Printer Type Detection

Add to `packages/agent/agent/printer/detector.py`:

```python
import os
from pathlib import Path
from enum import Enum

class PrinterType(str, Enum):
    DTG = "dtg"
    DTF = "dtf"
    UV = "uv"
    UNKNOWN = "unknown"

def detect_printer_type(exe_path: str) -> PrinterType:
    """Auto-detect printer type from PrintExp.exe size."""
    try:
        stat = os.stat(exe_path)
        size_mb = stat.st_size / (1024 * 1024)

        # Heuristics based on known builds
        if size_mb > 9.5:
            return PrinterType.UV  # v5.7.9.4.5008
        elif 8.0 <= size_mb <= 9.5:
            return PrinterType.DTF  # v5.7.6
        else:
            return PrinterType.DTG  # 32-bit or earlier
    except Exception:
        return PrinterType.UNKNOWN
```

---

## Backend Interface Design

Create `packages/agent/agent/printer/backends.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class BackendConfig:
    exe_path: str
    exe_base: int  # Base address of PrintExp.exe
    tcp_port: int = 9100

class PrinterBackend(ABC):
    """Base class for printer control backends."""

    @abstractmethod
    def inject_file(self, prn_path: str) -> bool:
        """Inject a .prn file into PrintExp queue."""
        pass

    @abstractmethod
    def get_status(self) -> dict:
        """Get current printer status."""
        pass

    @abstractmethod
    def pause(self) -> bool:
        """Pause current job."""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """Resume paused job."""
        pass

    @abstractmethod
    def cancel(self) -> bool:
        """Cancel current job."""
        pass

class DTFBackend(PrinterBackend):
    """DTF PrintExp v5.7.6 backend — uses vtable[7] for AddFile."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self.dll_path = self._get_dtf_dll()

    def _get_dtf_dll(self) -> Path:
        """Return path to DTF injection DLL."""
        # Load from DTG_automation shared location or embedded resource
        dtf_dll = Path(__file__).parent / "dlls" / "inject_dtf.dll"
        if not dtf_dll.exists():
            # Fallback to DTG_automation repo
            dtf_dll = Path("../../../DTG_autommation/scripts/inject_dtf.dll")
        return dtf_dll

    def inject_file(self, prn_path: str) -> bool:
        """Inject via DLL with vtable[7] AddFile."""
        try:
            # Call DLL export: inject_file_dtf(exe_base, prn_path)
            # Returns True on success
            return self._call_dll_export(
                func_name="inject_file_dtf",
                args=(self.config.exe_base, prn_path)
            )
        except Exception as e:
            logger.error(f"DTF injection failed: {e}")
            return False

    def _call_dll_export(self, func_name: str, args: tuple) -> bool:
        """Call DLL export function via ctypes."""
        # Implementation details in agent package
        pass

class UVBackend(PrinterBackend):
    """UV PrintExp v5.7.9.4.5008 backend — uses vtable[9] for AddFile."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self.dll_path = self._get_uv_dll()

    def _get_uv_dll(self) -> Path:
        """Return path to UV injection DLL."""
        uv_dll = Path(__file__).parent / "dlls" / "inject_uv.dll"
        if not uv_dll.exists():
            # Fallback to DTG_automation repo
            uv_dll = Path("../../../DTG_autommation/scripts/inject_uv.dll")
        return uv_dll

    def inject_file(self, prn_path: str) -> bool:
        """Inject via DLL with vtable[9] AddFile."""
        try:
            # Call DLL export: inject_file_uv(exe_base, prn_path)
            # Returns True on success
            return self._call_dll_export(
                func_name="inject_file_uv",
                args=(self.config.exe_base, prn_path)
            )
        except Exception as e:
            logger.error(f"UV injection failed: {e}")
            return False

    def _call_dll_export(self, func_name: str, args: tuple) -> bool:
        """Call DLL export function via ctypes."""
        pass
```

---

## Agent Configuration Integration

Update `packages/agent/agent/config.py`:

```python
from printer.detector import detect_printer_type

@dataclass
class PrintExpConfig:
    exe_path: str
    tcp_port: int = 9100
    auto_detect: bool = True
    printer_type: str = "auto"  # "auto", "dtg", "dtf", "uv"

    def get_printer_type(self) -> str:
        """Resolve printer type (auto-detect if 'auto')."""
        if self.auto_detect or self.printer_type == "auto":
            return detect_printer_type(self.exe_path).value
        return self.printer_type
```

---

## Job Injection Workflow

In `packages/agent/agent/jobs/injector.py`:

```python
import logging
from pathlib import Path
from printer.backends import DTFBackend, UVBackend, BackendConfig
from printer.detector import PrinterType

logger = logging.getLogger(__name__)

class JobInjector:
    """Injects jobs into PrintExp via appropriate backend."""

    def __init__(self, exe_path: str, exe_base: int, tcp_port: int = 9100):
        self.exe_path = exe_path
        self.exe_base = exe_base
        self.tcp_port = tcp_port
        self.printer_type = detect_printer_type(exe_path)

        config = BackendConfig(
            exe_path=exe_path,
            exe_base=exe_base,
            tcp_port=tcp_port
        )

        if self.printer_type == PrinterType.DTF:
            self.backend = DTFBackend(config)
        elif self.printer_type == PrinterType.UV:
            self.backend = UVBackend(config)
        else:
            raise ValueError(f"Unsupported printer type: {self.printer_type}")

        logger.info(f"JobInjector initialized for {self.printer_type.value} PrintExp")

    def inject(self, prn_path: str) -> bool:
        """
        Inject a PRN file into PrintExp queue.

        Args:
            prn_path: Absolute path to .prn file

        Returns:
            True if injection succeeded, False otherwise
        """
        prn_path = str(Path(prn_path).absolute())

        if not Path(prn_path).exists():
            logger.error(f"PRN file not found: {prn_path}")
            return False

        # Attempt memory injection first (DLL backend)
        if self.backend.inject_file(prn_path):
            logger.info(f"Injected {prn_path} via {self.printer_type.value} backend")
            return True

        # Fallback: TCP 9100 injection (basic, no filename)
        logger.warning(
            f"{self.printer_type.value} DLL injection failed, "
            f"falling back to TCP 9100 (job will show as ~section0.prn)"
        )
        return self._inject_via_tcp(prn_path)

    def _inject_via_tcp(self, prn_path: str) -> bool:
        """Fallback: inject via raw TCP (no filename injection)."""
        try:
            with open(prn_path, 'rb') as f:
                data = f.read()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', self.tcp_port))
            sock.sendall(data)
            sock.close()
            return True
        except Exception as e:
            logger.error(f"TCP injection failed: {e}")
            return False
```

---

## Error Handling

### DLL Not Found

```python
class MissingDLLError(Exception):
    """Raised when injection DLL is not available."""
    pass

# In backend initialization:
if not self.dll_path.exists():
    raise MissingDLLError(
        f"Injection DLL not found at {self.dll_path}. "
        f"Ensure DTG_autommation repo is available."
    )
```

### Memory Injection Failures

Expected error cases:

| Error | Cause | Mitigation |
|-------|-------|-----------|
| `R6025 pure virtual call` | Copied to wrong display vector (UV) | Verify offset table, use only tested indices |
| `Access violation` | Wrong memory offset or base address | Log exe_base, validate against known versions |
| `DLL injection timeout` | AddFile hanging (corrupted queue) | Add timeout, graceful fallback to TCP |
| `Job not appearing in UI` | UI refresh message failed | Verify PostMessageW HWND, retry refresh |

---

## Testing

### Unit Tests

```python
# tests/test_agent/test_backends.py

import pytest
from printer.backends import DTFBackend, UVBackend, BackendConfig
from unittest.mock import patch, MagicMock

@pytest.fixture
def dtf_backend():
    config = BackendConfig(exe_path="PrintExp.exe", exe_base=0x400000)
    return DTFBackend(config)

@pytest.fixture
def uv_backend():
    config = BackendConfig(exe_path="PrintExp.exe", exe_base=0x140000000)
    return UVBackend(config)

def test_dtf_inject_file_success(dtf_backend):
    """Test successful DTF file injection."""
    with patch.object(dtf_backend, '_call_dll_export', return_value=True):
        result = dtf_backend.inject_file("C:\\test.prn")
        assert result is True

def test_uv_inject_file_success(uv_backend):
    """Test successful UV file injection."""
    with patch.object(uv_backend, '_call_dll_export', return_value=True):
        result = uv_backend.inject_file("C:\\test.prn")
        assert result is True

def test_injection_fallback_to_tcp(job_injector):
    """Test fallback to TCP when DLL injection fails."""
    job_injector.backend.inject_file = MagicMock(return_value=False)
    with patch.object(job_injector, '_inject_via_tcp', return_value=True):
        result = job_injector.inject("C:\\test.prn")
        assert result is True
```

### Hardware Tests

```bash
# On a PC with PrintExp running:
python -m agent --hardware-test

# Specific backend test:
python -m agent --hardware-test --printer-type=uv
python -m agent --hardware-test --printer-type=dtf
```

---

## Logging & Diagnostics

Enable detailed logging for backend operations:

```python
# In agent startup:
import logging
logging.getLogger("agent.printer.backends").setLevel(logging.DEBUG)

# Sample output:
# [DEBUG] DTFBackend._call_dll_export: Calling inject_file_dtf(0x400000, C:\test.prn)
# [DEBUG] DTFBackend: DLL export returned True
# [INFO] JobInjector: Injected C:\test.prn via dtf backend
```

---

## Migration Path (DTG to DTF/UV)

1. Deploy new `inject_dtf.dll` and `inject_uv.dll` to `packages/agent/agent/dlls/`
2. Update agent config: `printer.type = "auto"`
3. Agent auto-detects on startup
4. Log printer type for diagnostics
5. Monitor injection success rates per printer type
6. Phase out DTG WriteProcessMemory approach (if applicable)

---

## References

- [printer-backend-integration.md](./printer-backend-integration.md) — Full technical details on offsets, vtables, struct layouts
- DTG_automation repo: `scripts/inject_dtf.dll`, `scripts/inject_uv.dll` — Compiled binaries
- DTG_automation repo: `scripts/inject_uv_printexp.c`, `scripts/add_to_uv_printexp.py` — Reference implementations
