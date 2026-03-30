# -*- coding: utf-8 -*-
"""
Script de prueba para verificar que el backend Django acepta peticiones sin CSRF
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_obtener_numero():
    """Probar obtener número sin autenticación"""
    print("=" * 60)
    print("🧪 TEST 1: Obtener número de presupuesto sin autenticación")
    print("=" * 60)
    
    # Primero, obtener el ID del comprobante PRES
    response = requests.get(f"{BASE_URL}/comprobantes/?tipo=PRES")
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Response Text (primeros 500 chars): {response.text[:500]}")
    
    if response.status_code == 200:
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ Error al parsear JSON: {e}")
            print(f"Response completo: {response.text}")
            return False
        if isinstance(data, dict) and 'configuraciones' in data:
            configs = data['configuraciones']
        else:
            configs = data
            
        if configs and len(configs) > 0:
            comprobante_id = configs[0]['id']
            print(f"✅ Comprobante encontrado: ID={comprobante_id}")
            
            # Intentar obtener número
            response = requests.post(
                f"{BASE_URL}/comprobantes/{comprobante_id}/obtener_siguiente_numero/"
            )
            
            print(f"\n📡 Status Code: {response.status_code}")
            print(f"📄 Response:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            
            if response.status_code == 200:
                print("\n✅ ¡ÉXITO! Se pudo obtener número sin autenticación")
                return True
            else:
                print("\n❌ ERROR: No se pudo obtener número")
                return False
        else:
            print("❌ No hay comprobantes configurados")
            return False
    else:
        print(f"❌ Error al obtener comprobantes: {response.status_code}")
        return False


def test_crear_presupuesto():
    """Probar crear presupuesto sin autenticación"""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Crear presupuesto sin autenticación")
    print("=" * 60)
    
    # Datos de prueba
    datos = {
        "cliente": 1,  # Asume que existe un cliente con ID 1
        "valido_hasta": "2026-01-15",
        "observaciones": "Presupuesto de prueba desde script",
        "condiciones_comerciales": "Condiciones de prueba",
        "iva_porcentaje": 21.0,
        "estado": "borrador",
        "items": [
            {
                "servicio": 1,  # Solo servicio, sin producto
                "codigo": "TEST001",
                "descripcion": "Servicio de prueba",
                "cantidad": 1,
                "precio_unitario": 1000.0
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/presupuestos/",
        json=datos,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n📡 Status Code: {response.status_code}")
    
    if response.status_code in [200, 201]:
        print(f"📄 Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        print("\n✅ ¡ÉXITO! Se pudo crear presupuesto sin autenticación")
        return True
    else:
        print(f"📄 Response:")
        try:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except:
            print(response.text)
        print("\n❌ ERROR: No se pudo crear presupuesto")
        return False


if __name__ == "__main__":
    print("\n🚀 INICIANDO PRUEBAS DE BACKEND DJANGO\n")
    
    # Test 1
    test1_ok = test_obtener_numero()
    
    # Test 2
    test2_ok = test_crear_presupuesto()
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"Test 1 (Obtener número): {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"Test 2 (Crear presupuesto): {'✅ PASS' if test2_ok else '❌ FAIL'}")
    print("=" * 60)
    
    if test1_ok and test2_ok:
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print("✅ El backend está listo para usar con Tkinter")
    else:
        print("\n⚠️ Algunas pruebas fallaron")
        print("Por favor revisa los errores arriba")
