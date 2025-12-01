# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['servidor.py'],
    pathex=[],
    binaries=[],
    datas=[('db.sqlite3', '.'), ('media', 'media'), ('staticfiles', 'staticfiles'), ('sistema_general', 'sistema_general')],
    hiddenimports=['django.core.handlers.wsgi', 'waitress', 'whitenoise', 'whitenoise.middleware'],
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
    name='BackendLabServicios',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
