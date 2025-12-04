# /gestion/servidor.py
import os
import sys
import traceback
from waitress import serve
from django.core.management import call_command


# Agrega el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_general.settings')


from django.core.wsgi import get_wsgi_application
from pathlib import Path


application = get_wsgi_application()


if __name__ == '__main__':
    try:
        print("=" * 60)
        print("🚀 BACKEND LAB SERVICIOS - SISTEMA DE GESTIÓN")
        print("=" * 60)
       
        # ========== DEBUG CRÍTICO ==========
        import django
        django.setup()
        from django.conf import settings
        
        print(f"\n🔍 CONFIGURACIÓN CRÍTICA:")
        print(f"   DEBUG mode: {settings.DEBUG}")
        print(f"   MEDIA_ROOT: {settings.MEDIA_ROOT}")
        print(f"   MEDIA_URL: {settings.MEDIA_URL}")
        
        # Verificar que MEDIA_ROOT existe
        media_path = Path(settings.MEDIA_ROOT)
        print(f"   MEDIA_ROOT existe: {media_path.exists()}")
        
        if not media_path.exists():
            print("   ⚠️ Creando MEDIA_ROOT...")
            media_path.mkdir(parents=True, exist_ok=True)
        
        # Crear subcarpetas críticas
        subcarpetas = [
            'config/logos',
            'config/publicidad',
            'presupuestos/adjuntos',
            'presupuestos/pdfs',
            'productos/fotos',
            'productos/planos',
            'servicios/imagenes',
            'servicios/adjuntos'
        ]
        
        for carpeta in subcarpetas:
            (media_path / carpeta).mkdir(parents=True, exist_ok=True)
        # ===================================
       
        print("🔄 Verificando base de datos...")
        call_command('migrate', interactive=False)
        print("✅ Base de datos actualizada.")


        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            print("👤 Creando superusuario por defecto...")
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            print("✅ Superusuario creado: Usuario='admin', Clave='admin123'")
       
        print("\n" + "=" * 60)
        print("✅ Servidor listo!")
        print("📌 Accesos manuales:")
        print("   • Admin: http://localhost:8000/admin")
        print("   • API: http://localhost:8000/api/")
        print("   • Media: http://localhost:8000/media/")
        print("⏹️  Presiona Ctrl+C para detener")
        print("=" * 60)
       
        # Iniciar servidor
        serve(application, host='127.0.0.1', port=8000, threads=6)
       
    except Exception as e:
        traceback.print_exc()
        print("\n❌ Ocurrió un error fatal.")
        input("Presione Enter para salir...")