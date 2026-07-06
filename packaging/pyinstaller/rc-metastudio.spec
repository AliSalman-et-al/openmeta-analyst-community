# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/rc_metastudio/launch.py'],
    pathex=['src/rc_metastudio', 'src/rc_metastudio/forms'],
    binaries=[],
    datas=[],
    hiddenimports=['icons_rc', 'rpy2.robjects', 'rpy2.rinterface'],
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
    [],
    exclude_binaries=True,
    name='RCMetaStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src\\rc_metastudio\\images\\rc-metastudio-app-icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RCMetaStudio',
)
