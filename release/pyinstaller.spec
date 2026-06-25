# -*- mode: python ; coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(SPECPATH, ".."))
from nit_code.config import APP_VERSION

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# mpremote/esptool werden nur per Subprozess ("App -m mpremote ...") genutzt und
# daher von der statischen Analyse NICHT gefunden. Ohne explizites Einsammeln
# fehlen sie im Bundle ("No module named mpremote"). Komplett mitnehmen.
tool_datas, tool_binaries, tool_hiddenimports = [], [], []
for _pkg in ("mpremote", "esptool", "serial", "serial.tools"):
    _d, _b, _h = collect_all(_pkg)
    tool_datas += _d
    tool_binaries += _b
    tool_hiddenimports += _h

# In PyInstaller-Specs ist __file__ nicht zuverlässig verfügbar.
cwd = os.getcwd()
if os.path.exists(os.path.join(cwd, 'release', 'launcher.py')):
    project_root = cwd
    spec_dir = os.path.join(cwd, 'release')
elif os.path.exists(os.path.join(cwd, 'launcher.py')):
    spec_dir = cwd
    project_root = os.path.abspath(os.path.join(cwd, '..'))
else:
    project_root = cwd
    spec_dir = os.path.join(cwd, 'release')

entry_script = os.path.join(spec_dir, 'launcher.py')

logo_path = os.path.join(project_root, 'nit_code', 'logo.png')
datas = []
if os.path.exists(logo_path):
    datas.append((logo_path, 'nit_code'))

# Offline-Assets (z. B. mermaid.min.js für die Ablauf-Vorschau) mitnehmen.
assets_dir = os.path.join(project_root, 'nit_code', 'assets')
if os.path.isdir(assets_dir):
    datas.append((assets_dir, os.path.join('nit_code', 'assets')))

icon_file = None
if sys.platform == 'win32' and os.path.exists(logo_path):
    from PIL import Image
    ico_path = os.path.join(spec_dir, 'NIT_Code.ico')
    if not os.path.exists(ico_path):
        img = Image.open(logo_path).convert('RGBA')
        img.save(ico_path, format='ICO',
                 sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    if os.path.exists(ico_path):
        icon_file = ico_path
elif sys.platform == 'darwin' and os.path.exists(logo_path):
    import subprocess, tempfile
    icns_path = os.path.join(spec_dir, 'NIT_Code.icns')
    if not os.path.exists(icns_path):
        iconset_dir = os.path.join(tempfile.mkdtemp(), 'NIT_Code.iconset')
        os.makedirs(iconset_dir)
        for size in [16, 32, 128, 256, 512]:
            subprocess.run(['sips', '-z', str(size), str(size), logo_path,
                            '--out', os.path.join(iconset_dir, f'icon_{size}x{size}.png')],
                           capture_output=True)
            double = size * 2
            subprocess.run(['sips', '-z', str(double), str(double), logo_path,
                            '--out', os.path.join(iconset_dir, f'icon_{size}x{size}@2x.png')],
                           capture_output=True)
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', icns_path], check=True)
    if os.path.exists(icns_path):
        icon_file = icns_path

a = Analysis(
    [entry_script],
    pathex=[project_root],
    binaries=tool_binaries,
    datas=datas + tool_datas,
    hiddenimports=[
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.Qsci',
        'mpremote',
        'mpremote.main',
        'esptool',
        # truststore lädt seine Backends (_windows/_macos/_openssl) erst zur
        # Laufzeit plattformabhängig nach – statisch findet PyInstaller sie nicht.
        'truststore',
        'truststore._windows',
        'truststore._macos',
        'truststore._openssl',
    ] + tool_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 'cryptography' wird nur von espsecure (ESP-Secure-Boot-Signierung) benötigt,
    # das NIT_Code nicht verwendet. Ihr Rust-Binärteil (_rust.abi3.so) wird von
    # mehreren Virenscannern fälschlich als 'OSX/CrossC2' gemeldet (Fehlalarm).
    # Ausschluss entfernt die Datei und damit den Fehlalarm – ohne Funktionsverlust.
    excludes=['cryptography', 'espsecure', 'espefuse'],
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
    icon=icon_file,
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
        icon=icon_file,
        bundle_identifier='de.nit.nitcode',
        info_plist={
            'CFBundleName': 'NIT_Code',
            'CFBundleDisplayName': 'NIT_Code',
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
        },
    )
