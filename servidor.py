# /gestion/servidor.py - VERSIÓN CON REPARACIÓN
import os
import sys
import traceback
from waitress import serve
from django.core.management import call_command
import sqlite3  # ← AGREGADO PARA REPARACIÓN
from pathlib import Path


# Agrega el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_general.settings')


from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()


def reparar_numeracion_comprobantes():
    """
    Repara automáticamente el error 'proximo_numero' = 'proximo_numero'
    Se ejecuta antes de iniciar el servidor
    """
    print("🔧 Verificando y reparando numeración de comprobantes...")
    
    # Ruta de la base de datos (ajustar según tu configuración)
    db_path = 'db.sqlite3'  # ← Esta es la ruta RELATIVA desde donde se ejecuta el .exe
    
    if not os.path.exists(db_path):
        print("⚠️  No se encontró db.sqlite3, continuando...")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Verificar si existe la tabla
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comprobantes_comprobante';")
        if not cursor.fetchone():
            print("✅ Tabla de comprobantes no existe (primera ejecución)")
            conn.close()
            return True
        
        # 2. Buscar problemas
        cursor.execute("""
            SELECT id, tipo, serie, proximo_numero, numero_inicial, numero_final 
            FROM comprobantes_comprobante;
        """)
        registros = cursor.fetchall()
        
        reparaciones = 0
        for registro in registros:
            id_reg, tipo, serie, proximo_numero, numero_inicial, numero_final = registro
            
            necesita_reparacion = False
            nuevo_valor = None
            
            # Caso 1: proximo_numero es string 'proximo_numero' o similar
            if isinstance(proximo_numero, str):
                valor_limpio = proximo_numero.strip().lower()
                if valor_limpio in ['proximo_numero', 'proximo numero', 'próximo número']:
                    print(f"   ⚠️  {tipo}-{serie}: '{proximo_numero}' → {numero_inicial}")
                    necesita_reparacion = True
                    nuevo_valor = numero_inicial if numero_inicial else 1
            
            # Caso 2: String no numérico
            elif isinstance(proximo_numero, str):
                try:
                    float(proximo_numero.strip())
                except ValueError:
                    print(f"   ⚠️  {tipo}-{serie}: No es número válido '{proximo_numero}' → {numero_inicial}")
                    necesita_reparacion = True
                    nuevo_valor = numero_inicial if numero_inicial else 1
            
            # Caso 3: Fuera de rango
            elif isinstance(proximo_numero, (int, float)):
                if proximo_numero < numero_inicial:
                    print(f"   ⚠️  {tipo}-{serie}: {proximo_numero} < {numero_inicial} → {numero_inicial}")
                    necesita_reparacion = True
                    nuevo_valor = numero_inicial
                elif proximo_numero > numero_final:
                    print(f"   ⚠️  {tipo}-{serie}: {proximo_numero} > {numero_final} → {numero_final}")
                    necesita_reparacion = True
                    nuevo_valor = numero_final
            
            # Aplicar reparación
            if necesita_reparacion and nuevo_valor is not None:
                cursor.execute(
                    "UPDATE comprobantes_comprobante SET proximo_numero = ? WHERE id = ?",
                    (nuevo_valor, id_reg)
                )
                reparaciones += 1
        
        if reparaciones > 0:
            conn.commit()
            print(f"✅ {reparaciones} configuraciones de comprobantes reparadas")
        else:
            print("✅ No se encontraron problemas de numeración")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error en reparación: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        print("=" * 60)
        print("🚀 BACKEND LAB SERVICIOS - SISTEMA DE GESTIÓN")
        print("=" * 60)
        
        # ========== REPARACIÓN AUTOMÁTICA ==========
        reparar_numeracion_comprobantes()
        # ===========================================
       
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