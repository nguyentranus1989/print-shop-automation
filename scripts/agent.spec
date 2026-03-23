# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for printflow-agent.
--onedir mode: faster startup, easier asset access.
Console mode: keeps log output visible for debugging/NSSM service logs.
"""

import sys
from pathlib import Path

# Resolve workspace root (one level above scripts/)
ROOT = Path(SPECPATH).parent

# Source trees for workspace packages
AGENT_SRC = str(ROOT / "packages" / "agent" / "src")
COMMON_SRC = str(ROOT / "packages" / "common" / "src")

block_cipher = None

a = Analysis(
    # Entry script — importable from AGENT_SRC
    [str(ROOT / "packages" / "agent" / "src" / "agent" / "main.py")],
    pathex=[AGENT_SRC, COMMON_SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        # pycryptodome — PyInstaller can't find Crypto.Cipher.* automatically
        "Crypto",
        "Crypto.Cipher",
        "Crypto.Cipher.AES",
        "Crypto.Util",
        "Crypto.Util.Padding",
        "Crypto.Random",
        # Pydantic v2 internals
        "pydantic",
        "pydantic.deprecated",
        "pydantic.deprecated.class_validators",
        "pydantic.deprecated.config",
        "pydantic_core",
        # FastAPI / Starlette
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.responses",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.websockets",
        # uvicorn + optional transports
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "httptools",
        "httptools.parser",
        "websockets",
        "websockets.legacy",
        "websockets.legacy.server",
        # SQLAlchemy dialects (sqlite is the default)
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.orm",
        # Standard lib extras sometimes missed
        "tomllib",
        "multiprocessing",
        "email.mime.text",
        "email.mime.multipart",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dashboard-only deps — keep agent binary lean
        "jinja2",
        "alembic",
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "PIL",
        "cv2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # --onedir: binaries stay in _internal/
    name="printflow-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,        # skip UPX — AV false-positives, minimal gain
    console=True,     # keep console: service logs are critical for ops
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="printflow-agent",
)
