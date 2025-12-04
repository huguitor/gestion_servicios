import os
import subprocess
import sys
import glob

print("🔨 CREANDO .EXE DE DJANGO - BACKEND LAB SERVICIOS")
print("=" * 60)

# Instalar waitress si no está
try:
    import waitress
    print("✅ Waitress ya instalado")
except ImportError:
    print("📦 Instalando waitress...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "waitress"])

# Detectar apps Django automáticamente (carpetas con __init__.py)
print("\n🔍 Detectando apps Django...")
apps = []
for item in os.listdir('.'):
    if os.path.isdir(item):
        if os.path.exists(os.path.join(item, '__init__.py')):
            # Excluir carpetas especiales
            if item not in ['sistema_general', 'media', 'staticfiles', 'data', 'dist', '__pycache__']:
                apps.append(item)
                print(f"  ✓ {item}")

if not apps:
    # Lista manual si falla la detección
    apps = [
        'configuracion', 'clientes', 'proveedores', 'productos',
        'presupuestos', 'comprobantes', 'categorias', 'marcas', 'impuestos'
    ]
    print("  ⚠️ Usando lista manual de apps")

print(f"\n📦 Total de apps detectadas: {len(apps)}")

# Comando de compilación
comando = [
    'pyinstaller',
    '--onefile',
    '--console',
    '--name=BackendLabServicios',
    '--clean',
    '--noconfirm',
    '--hidden-import=django',
    '--hidden-import=waitress',
    '--hidden-import=rest_framework',
    '--hidden-import=corsheaders',
    '--hidden-import=whitenoise',
    '--hidden-import=whitenoise.middleware',  # ← AGREGAR ESTO
    '--hidden-import=django_filters',
    '--hidden-import=django.contrib.auth',
    '--hidden-import=django.contrib.contenttypes',
    '--hidden-import=django.contrib.sessions',
    '--hidden-import=django.contrib.messages',
    '--hidden-import=django.contrib.staticfiles',
    '--hidden-import=django.contrib.admin',
    '--add-data=manage.py;.',
    '--add-data=sistema_general;sistema_general',
]

# Agregar apps detectadas
for app in apps:
    if os.path.exists(app):
        comando.append(f'--add-data={app};{app}')

# Agregar media y staticfiles
if os.path.exists('media'):
    comando.append('--add-data=media;media')
    print("  ✓ Incluyendo: media/")
if os.path.exists('staticfiles'):
    comando.append('--add-data=staticfiles;staticfiles')
    print("  ✓ Incluyendo: staticfiles/")

# Archivo principal
comando.append('servidor.py')

# Ejecutar
print(f"\n⚙️  Compilando {len(apps)} apps... (esto puede tardar varios minutos)")
print("   Por favor, tené paciencia...")
subprocess.run(comando)

print("\n" + "=" * 60)
print("✅ ¡.EXE CREADO EXITOSAMENTE!")
print("=" * 60)
print(f"\n📂 Ejecutable: dist/BackendLabServicios.exe")
print(f"📁 Datos persistentes: data/ (se crea automáticamente)")
print(f"💾 Base de datos: data/database.sqlite3")
print(f"🖼️  Archivos subidos: data/media/")
print(f"\n🎯 PARA USAR:")
print(f"   1. Copia BackendLabServicios.exe a cualquier carpeta")
print(f"   2. Haz doble click para ejecutar")
print(f"   3. Se abrirá el navegador en http://localhost:8000")
print(f"   4. Los datos NO se borran al cerrar")
print(f"\n🐛 Para debug: Si hay errores, se verán en la ventana negra")