
import os
import django
from decimal import Decimal

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_general.settings')
django.setup()

from comprobantes.models import Comprobante
from presupuestos.models import Presupuesto
from clientes.models import Cliente
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

def probar_limites():
    print("--- Iniciando prueba de límites de presupuesto ---")
    
    # 1. Crear o buscar un usuario para la prueba
    user, _ = User.objects.get_or_create(username='test_user', defaults={'email': 'test@test.com'})
    
    # 2. Crear un cliente de prueba
    cliente, _ = Cliente.objects.get_or_create(
        documento="20123456789", 
        defaults={'nombre': 'Cliente Test', 'apellido': 'Límite'}
    )

    # 3. Crear un comprobante con un rango MUY PEQUEÑO para forzar el error rápido
    # Rango: 100 al 101 (Solo permite 2 presupuestos: el 100 y el 101)
    comprobante, created = Comprobante.objects.get_or_create(
        tipo="PRES",
        serie="TEST1",
        defaults={
            'numero_inicial': 100,
            'numero_final': 101,
            'numero_comienzo': 100,
            'numero': 0
        }
    )
    
    # Asegurarnos que esté limpio para la prueba si ya existía
    if not created:
        comprobante.numero_inicial = 100
        comprobante.numero_final = 101
        comprobante.numero_comienzo = 100
        comprobante.save()
        # Borrar presupuestos viejos de este comprobante para test limpio
        Presupuesto.objects.filter(comprobante=comprobante).delete()

    print(f"Comprobante configurado: Serie {comprobante.serie}, Rango {comprobante.numero_inicial}-{comprobante.numero_final}")

    # 4. Intentar crear el PRIMER presupuesto (Debería ser el 100) -> OK
    try:
        p1 = Presupuesto(cliente=cliente, creado_por=user, comprobante=comprobante)
        p1.save()
        print(f"[OK] Presupuesto 1 creado con exito: Numero {p1.numero}")
    except Exception as e:
        print(f"[ERROR] Error inesperado creando presupuesto 1: {e}")

    # 5. Intentar crear el SEGUNDO presupuesto (Debería ser el 101) -> OK (Límite exacto)
    try:
        p2 = Presupuesto(cliente=cliente, creado_por=user, comprobante=comprobante)
        p2.save()
        print(f"[OK] Presupuesto 2 creado con exito: Numero {p2.numero}")
    except Exception as e:
        print(f"[ERROR] Error inesperado creando presupuesto 2: {e}")

    # 6. Intentar crear el TERCER presupuesto (Debería ser el 102) -> ERROR ESPERADO
    print("Intentando crear presupuesto fuera de rango (esperando error)...")
    try:
        p3 = Presupuesto(cliente=cliente, creado_por=user, comprobante=comprobante)
        p3.save()
        print(f"[FALLO] Se creo el presupuesto {p3.numero} y NO DEBERIA.")
    except ValidationError as e:
        print(f"[EXITO] El sistema bloqueo la creacion correctamente.")
        print(f"   Mensaje de error recibido: {e}")
    except Exception as e:
        print(f"[WARNING] Error recibido pero no es ValidationError: {type(e)} - {e}")

if __name__ == "__main__":
    probar_limites()
