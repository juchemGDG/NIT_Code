# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

project_root = os.path.abspath('.')
entry_script = os.path.join('release', 'launcher.py')

logo_path = os.path.join('nit_code', 'logo.png')
datas = []
if os.path.exists(logo_path):
    datas.append((logo_path, 'nit_code'))

a = Analysis(
    [entry_script],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.Qsci',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NIT_Code',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NIT_Code',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='NIT_Code.app',
        icon=None,
        bundle_identifier='de.nit.nitcode',
        info_plist={
            'CFBundleName': 'NIT_Code',
            'CFBundleDisplayName': 'NIT_Code',
            'CFBundleShortVersionString': '1.0.1',
            'CFBundleVersion': '1.0.1',
        },
    )
