# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置
使用方法: pyinstaller PowerSupplyController.spec
"""

import sys
import os

project_root = os.path.abspath(".")
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from version import APP_NAME, APP_VERSION

platform_name = "windows" if sys.platform.startswith("win") else "linux"
artifact_name = f"{APP_NAME}-v{APP_VERSION}-{platform_name}"

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[src_dir],
    binaries=[],
    datas=[('src/icon.ico', '.')],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=artifact_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/icon.ico',
)
