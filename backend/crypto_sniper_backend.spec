# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — empaqueta el backend FastAPI en un ejecutable standalone.
# Build:  cd backend && pyinstaller --noconfirm --clean crypto_sniper_backend.spec
# Salida: backend/dist/crypto_sniper_backend/crypto_sniper_backend.exe

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = []
for pkg in ('uvicorn', 'fastapi', 'starlette', 'anthropic', 'motor', 'pymongo',
            'pydantic', 'pydantic_settings', 'pandas', 'numpy', 'dotenv',
            'engine', 'exchanges'):
    hidden += collect_submodules(pkg)

datas = []
datas += collect_data_files('anthropic')

a = Analysis(
    ['server.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='crypto_sniper_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='crypto_sniper_backend',
)
