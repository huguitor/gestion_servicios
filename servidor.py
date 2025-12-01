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

application = get_wsgi_application()

if __name__ == '__main__':
    try:
        print("=== Servidor Backend LabServicios ===")
        
        print("🔄 Verificando base de datos...")
        call_command('migrate', interactive=False)
        print("✅ Base de datos actualizada.")

        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            print("👤 Creando superusuario por defecto...")
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            print("✅ Superusuario creado: Usuario='admin', Clave='admin123'")
        
        print("✅ Admin Django: http://localhost:8000/admin")
        print("🔑 API Token: http://localhost:8000/api/token/")
        print("⏹️  Presiona Ctrl+C para detener el servidor")
        print("=" * 50)
        serve(application, host='0.0.0.0', port=8000, threads=6)
    except Exception as e:
        traceback.print_exc()
        print("\n❌ Ocurrió un error fatal.")
        input("Presione Enter para salir...")