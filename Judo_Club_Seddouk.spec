# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['serveur.py'],
    pathex=[],
    binaries=[],
    datas=[('index.html', '.'), ('Fiche de renseignement Judo Club Seddouk.html', '.'), ('Badge_B3_Judo_Club_Seddouk_115x94mm.html', '.'), ('Badge_B3_Judo_Club_Seddouk_115x94mm-recto.html', '.')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'clr_loader', 'pythonnet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Judo_Club_Seddouk',
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
)
