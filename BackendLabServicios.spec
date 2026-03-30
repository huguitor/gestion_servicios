# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['servidor.py'],
    pathex=[],
    binaries=[],
    datas=[('manage.py', '.'), ('sistema_general', 'sistema_general'), ('categorias', 'categorias'), ('clientes', 'clientes'), ('comprobantes', 'comprobantes'), ('configuracion', 'configuracion'), ('impuestos', 'impuestos'), ('marcas', 'marcas'), ('presupuestos', 'presupuestos'), ('productos', 'productos'), ('proveedores', 'proveedores'), ('remitos', 'remitos'), ('media', 'media'), ('staticfiles', 'staticfiles')],
    hiddenimports=['django', 'waitress', 'rest_framework', 'corsheaders', 'whitenoise', 'whitenoise.middleware', 'django_filters', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'django.contrib.admin'],
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
