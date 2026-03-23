# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for printflow-dashboard.
--onedir mode with Jinja2 templates and static files bundled as datas.
Console mode: service logs.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

DASHBOARD_SRC = str(ROOT / "packages" / "dashboard" / "src")
COMMON_SRC = str(ROOT / "packages" / "common" / "src")

# Dashboard ships Jinja2 templates and a static CSS file — bundle them
DASHBOARD_PKG = ROOT / "packages" / "dashboard" / "src" / "dashboard"

block_cipher = None

a = Analysis(
    [str(DASHBOARD_PKG / "main.py")],
    pathex=[DASHBOARD_SRC, COMMON_SRC],
    binaries=[],
    datas=[
        # (source_path, dest_dir_inside_bundle)
        (str(DASHBOARD_PKG / "templates"), "dashboard/templates"),
        (str(DASHBOARD_PKG / "static"), "dashboard/static"),
    ],
    hiddenimports=[
        # pycryptodome
        "Crypto",
        "Crypto.Cipher",
        "Crypto.Cipher.AES",
        "Crypto.Util",
        "Crypto.Util.Padding",
        "Crypto.Random",
        # Pydantic v2
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
        "starlette.staticfiles",
        "starlette.templating",
        # uvicorn
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
        # Jinja2
        "jinja2",
        "jinja2.ext",
        # SQLAlchemy + Alembic
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.orm",
        "alembic",
        # httpx for agent polling
        "httpx",
        "anyio",
        "anyio._backends._asyncio",
        # Standard lib
        "tomllib",
        "multiprocessing",
        "email.mime.text",
        "email.mime.multipart",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    exclude_binaries=True,
    name="printflow-dashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
    name="printflow-dashboard",
)
