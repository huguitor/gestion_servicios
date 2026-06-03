# gestion/backend/archivos/services.py

import hashlib
import mimetypes

from django.conf import settings

try:
    import magic
except ImportError:
    magic = None


# ==========================================================
# CHECKSUM
# ==========================================================

def calcular_checksum_sha256(file_obj):
    """
    Calcula SHA256 del archivo.
    """

    sha256_hash = hashlib.sha256()

    try:

        file_obj.seek(0)

        if hasattr(file_obj, "chunks"):

            for chunk in file_obj.chunks():
                sha256_hash.update(chunk)

        else:
            sha256_hash.update(
                file_obj.read()
            )

        file_obj.seek(0)

        return sha256_hash.hexdigest()

    except Exception:
        return ""


# ==========================================================
# MIME TYPE
# ==========================================================

def detectar_mime_type(file_obj):
    """
    Detecta el MIME real.

    Prioridad:

    1) python-magic
    2) mimetypes
    """

    try:

        if magic is not None:

            file_obj.seek(0)

            contenido = file_obj.read(
                4096
            )

            mime = magic.from_buffer(
                contenido,
                mime=True
            )

            file_obj.seek(0)

            if mime:
                return mime

        nombre = getattr(
            file_obj,
            "name",
            ""
        )

        mime, _ = mimetypes.guess_type(
            nombre
        )

        return (
            mime
            or "application/octet-stream"
        )

    except Exception:
        return "application/octet-stream"


# ==========================================================
# TAMAÑO
# ==========================================================

def obtener_tamano_archivo(file_obj):
    """
    Devuelve tamaño en bytes.
    """

    try:
        return file_obj.size

    except Exception:
        return 0


# ==========================================================
# VALIDACIÓN MIME
# ==========================================================

def validar_mime_permitido(file_obj):
    """
    Verifica si el MIME detectado
    está permitido por configuración.
    """

    mime = detectar_mime_type(
        file_obj
    )

    permitidos = getattr(
        settings,
        "ARCHIVOS_MIME_PERMITIDOS",
        []
    )

    return mime in permitidos


# ==========================================================
# METADATOS
# ==========================================================

def procesar_metadatos_archivo(
    archivo_instance
):
    """
    Completa automáticamente:

    - mime_type
    - tamano_bytes
    - checksum
    """

    file_obj = archivo_instance.archivo

    if not file_obj:
        return

    try:

        archivo_instance.mime_type = (
            detectar_mime_type(
                file_obj
            )
        )

        archivo_instance.tamano_bytes = (
            obtener_tamano_archivo(
                file_obj
            )
        )

        archivo_instance.checksum = (
            calcular_checksum_sha256(
                file_obj
            )
        )

    except Exception:

        archivo_instance.mime_type = (
            "application/octet-stream"
        )

        archivo_instance.tamano_bytes = 0

        archivo_instance.checksum = ""


# ==========================================================
# DEDUPLICACIÓN (FUTURO)
# ==========================================================

def obtener_checksum_archivo(
    file_obj
):
    """
    Alias semántico para futuras
    funcionalidades de deduplicación.

    Ejemplo futuro:

    Archivo.objects.filter(
        checksum=obtener_checksum_archivo(...)
    )
    """

    return calcular_checksum_sha256(
        file_obj
    )