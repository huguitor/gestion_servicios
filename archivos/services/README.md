# 🧱 Arquitectura de Servicios de Archivos — VERSIÓN PRO

**Última actualización:** Junio 3, 2026

---

## ⚡ Reglas de Oro (CRÍTICAS)

### ❌ Prohibido
```python
# ❌ NUNCA usar default_storage fuera de file_storage.py
from django.core.files.storage import default_storage
default_storage.save(...)  # ❌ NO

# ❌ NUNCA usar .url directamente
obj.archivo.url  # ❌ NO

# ❌ NUNCA validar archivo en serializer
def validate_archivo(self, value):
    # ❌ validar tamaño/extensión aquí
```

### ✅ OBLIGATORIO
```python
# ✅ Siempre vía FileStorage
from archivos.services import FileStorage
url = FileStorage.url(storage_path)  # ✅ SÍ

# ✅ Siempre vía FileService.upload()
from archivos.services import FileService
result = FileService.upload(file_obj, tipo=tipo_obj)  # ✅ SÍ

# ✅ Serializer solo persiste, no valida lógica
def validate_archivo(self, value):
    if not value:
        return value
    # ✅ SOLO eso. Validación pesada en FileService
```

---

## 📦 Estructura

```
services/
├── __init__.py              ← Importaciones públicas
├── file_validator.py        ← Validaciones (tamaño, extensión, MIME)
├── file_analyzer.py         ← Análisis técnico (MIME real, checksum)
├── file_storage.py          ← ABSTRACCIÓN ÚNICA (¡SIN FUGAS!)
├── file_service.py          ← Orquestación central
└── README.md
```

---

## 🎯 Arquitectura: Un Solo Punto de Entrada

```
Frontend
   ↓
API endpoint
   ↓
FileService.upload()  ← ⭐ PUNTO ÚNICO DE ENTRADA
   ├─ FileValidator.validate_all()
   ├─ FileAnalyzer.analyze()
   ├─ FileStorage.save()
   └─ Archivo.create() + ArchivoRelacion.create()
   ↓
Database + Storage
```

### Por qué un solo punto

- ✅ Eliminadas validaciones duplicadas
- ✅ Lógica centralizada
- ✅ Transacciones atómicas
- ✅ Error handling consistente
- ✅ Auditoría y logs en un lugar

---

## 🚀 Flujo de Uso

### 1. Upload simple (desde cualquier endpoint)

```python
from archivos.services import FileService
from django.contrib.contenttypes.models import ContentType

# En la view
result = FileService.upload(
    file_obj=request.FILES["archivo"],
    tipo=tipo_instance,  # TipoArchivo
    content_type=ContentType.objects.get(model="producto"),
    object_id=42,
    usuario=request.user,
)

# Retorna:
# {
#     "archivo_id": 1,
#     "archivo_url": "/media/archivos/imagenes/foto.jpg",
#     "relacion_id": 5,
#     "mime_type": "image/jpeg",
#     "extension": "jpg",
#     "checksum": "abc123def456...",
#     "tamaño_bytes": 1024000,
# }
```

### 2. Obtener URL de un archivo (desde serializer)

```python
from archivos.services import FileStorage

class ArchivoSerializer(serializers.ModelSerializer):
    archivo_url = serializers.SerializerMethodField()
    
    def get_archivo_url(self, obj):
        """CORRECTO: vía FileStorage, no obj.archivo.url"""
        if not obj.archivo:
            return None
        return FileStorage.url(obj.archivo.name)
```

### 3. Validar antes de upload (si necesitas)

```python
from archivos.services import FileService

# Solo validación (sin análisis)
result = FileService.validate_file(file_obj)

if not result["is_valid"]:
    print(f"Errores: {result['errors']}")
```

### 4. Analizar sin validar (admin)

```python
from archivos.services import FileService

# Solo análisis, sin validaciones
metadata = FileService.analyze_file(file_obj)

print(f"MIME: {metadata['mime_type']}")
print(f"Checksum: {metadata['checksum']}")
```

---

## 🔒 Seguridad

- ✅ MIME detectado con **python-magic** (no solo extensión)
- ✅ Checksum **SHA256** para deduplicación e integridad
- ✅ Validaciones **centralizadas** (sin duplicación)
- ✅ Storage **agnóstico** (local/S3/MinIO intercambiables)
- ✅ Transacciones **atómicas** (si falla algo, rollback)

---

## 🔄 Flujo de Upload Completo

### Request
```
POST /api/archivos/upload_simple/

{
    "archivo": <file>,
    "tipo": 1,
    "content_type": "producto",
    "object_id": 42,
}
```

### View procesa así:

```python
@action(detail=False, methods=["post"])
def upload_simple(self, request):
    # 1. Validar request data con serializer
    serializer = ArchivoUploadSimpleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # Valida inputs
    
    # 2. Llamar FileService.upload()
    result = FileService.upload(
        file_obj=serializer.validated_data["archivo"],
        tipo=serializer.validated_data["tipo"],
        content_type=serializer.validated_data["content_type_obj"],
        object_id=serializer.validated_data["object_id"],
        usuario=request.user,
    )
    
    # 3. Retornar
    return Response({"success": True, "data": result})
```

### FileService.upload() hace:

```python
1. FileValidator.validate_all()        ← Tamaño, extensión, MIME
2. FileAnalyzer.analyze()              ← MIME real, checksum
3. FileStorage.save()                  ← Guarda en storage
4. Archivo.objects.create()            ← BD
5. ArchivoRelacion.objects.create()    ← BD (si aplica)
6. return result
```

---

## 🛠️ Métodos de FileService

```python
# UPLOAD COMPLETO (punto único)
FileService.upload(
    file_obj,
    tipo,
    content_type=None,
    object_id=None,
    usuario=None,
)

# Validación simple
FileService.validate_file(file_obj)
# → {"is_valid": bool, "errors": list}

# Análisis simple
FileService.analyze_file(file_obj)
# → {"mime_type": str, "extension": str, ...}

# Procesar (validar + analizar, sin guardar)
FileService.process_file(file_obj)
# → {"mime_type": str, "is_valid": bool, "errors": list}
```

---

## 🛠️ Métodos de FileStorage

**ESTOS SON LOS ÚNICOS PUNTOS donde se toca storage:**

```python
FileStorage.save(file_obj, path)           # Guardar
FileStorage.url(storage_path)              # URL (¡vía FileStorage!)
FileStorage.delete(storage_path)           # Eliminar
FileStorage.exists(storage_path)           # Existe?
FileStorage.read(storage_path)             # Leer contenido
FileStorage.copy(source, dest)             # Copiar
FileStorage.generate_path(carpeta, nombre) # Generar ruta
FileStorage.size(storage_path)             # Tamaño
FileStorage.list_directory(path)           # Listar carpeta
```

**Regla:** Si necesitas tocar storage, `FileStorage.método()`. Nada más.

---

## 🔧 Configuración (settings.py)

```python
# Tamaño máximo
ARCHIVOS_MAX_MB = 500

# Extensiones permitidas
EXTENSIONES_PERMITIDAS = {
    "imagenes": ["jpg", "jpeg", "png", "gif", "webp"],
    "documentos": ["pdf", "doc", "docx", "txt", "xlsx"],
    "videos": ["mp4", "avi", "mov"],
    "otros": ["zip", "rar", "7z"],
}

# MIME types permitidos (opcional)
ARCHIVOS_MIME_PERMITIDOS = [
    "image/jpeg",
    "image/png",
    "application/pdf",
    # ... más
]
```

---

## 🚀 Cambio a S3/MinIO (el punto de esta arquitectura)

Si mañana necesitas S3:

### Opción 1: Cambiar solo settings.py

```python
# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'mi-bucket'
AWS_S3_REGION_NAME = 'us-east-1'
# ... más config S3
```

**El resto del código NO cambia.** ✨

### Opción 2: Cambiar storage_backend en FileStorage (si es más complejo)

```python
# services/file_storage.py
class FileStorage:
    # Cambiar backend aquí
    @staticmethod
    def save(file_obj, path):
        return s3_backend.save(path, file_obj)  # ← cambio local
    
    @staticmethod
    def url(path):
        return s3_backend.url(path)  # ← cambio local
```

**El resto del código SIGUE IGUAL.**

---

## 🔍 Auditoría y Debugging

### Ver proceso paso a paso

```python
from archivos.services import FileService
from archivos.services import FileValidator, FileAnalyzer

file_obj = request.FILES["archivo"]

# 1. Validar
try:
    FileValidator.validate_all(file_obj)
    print("✅ Validación OK")
except ValueError as e:
    print(f"❌ Error: {e}")

# 2. Analizar
metadata = FileAnalyzer.analyze(file_obj)
print(f"MIME: {metadata['mime_type']}")
print(f"Checksum: {metadata['checksum']}")

# 3. Procesar (todo junto)
result = FileService.process_file(file_obj)
print(result)
```

---

## 📊 Flujo sin fugas (verificado)

```
❌ ANTES (problemas):
   - validación en serializer + modelo + validator (duplicada)
   - .url usado en muchos lugares (acoplado)
   - default_storage repartido

✅ AHORA (limpio):
   - Validación SOLO en FileValidator
   - URLs SOLO vía FileStorage
   - Storage SOLO en FileStorage
   - Upload SOLO vía FileService
```

---

## 🎁 Próximo: Características que ahora son fáciles

- ✅ **Deduplicación**: Buscar por checksum, crear link en lugar de copiar
- ✅ **Versionado**: Múltiples versiones de un archivo (checksum != version)
- ✅ **Thumbnails**: Generar en `FileService.upload()` post-save
- ✅ **Storage híbrido**: Local para temp, S3 para final
- ✅ **Permisos avanzados**: Por tipo de archivo + rol
- ✅ **CDN firmado**: URLs con expiración (S3 pre-signed)
- ✅ **Backup automático**: Replicar a storage secundario

Todo sin tocar `models.py`, `views.py`, ni `serializers.py` 🚀

---

**CONCLUSIÓN:**

Esta arquitectura es **PRO** porque respeta las reglas de abstracción.
No es decorativa: **si mañana cambias a S3, solo cambias settings y un archivo.**

✨

