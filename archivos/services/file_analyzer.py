"""
file_analyzer.py

Análisis de archivos:
- Detección de MIME type (python-magic)
- Cálculo de checksum (SHA256)
- Extracción de extensión
- Cálculo de tamaño

Centraliza todos los análisis técnicos de archivos.
"""

import os
import hashlib
import mimetypes

try:
    import magic
except ImportError:
    magic = None


class FileAnalyzer:
    """
    Servicio de análisis de archivos.
    
    Encapsula:
    - detección de MIME type
    - cálculo de checksums
    - análisis de tamaño
    - extracción de metadata técnica
    """

    # ==========================================================
    # MIME TYPE (DETECTAR TIPO REAL)
    # ==========================================================

    @staticmethod
    def detect_mime_type(file_obj):
        """
        Detecta el MIME type real del archivo.
        
        Prioridad:
        1. python-magic (lectura de headers/magic numbers)
        2. mimetypes (extensión)
        3. fallback: application/octet-stream
        
        Args:
            file_obj: Objeto de archivo
        
        Returns:
            str: MIME type (ej: "image/png", "application/pdf")
        """
        if not file_obj:
            return "application/octet-stream"

        try:
            # Intenta con python-magic si está disponible
            if magic is not None:
                file_obj.seek(0)
                contenido = file_obj.read(4096)
                mime_type = magic.from_buffer(
                    contenido,
                    mime=True
                )
                file_obj.seek(0)

                if mime_type:
                    return mime_type

            # Fallback: mimetypes por extensión
            filename = getattr(file_obj, "name", "")
            mime_type, _ = mimetypes.guess_type(filename)

            return mime_type or "application/octet-stream"

        except Exception:
            return "application/octet-stream"

    # ==========================================================
    # CHECKSUM SHA256
    # ==========================================================

    @staticmethod
    def calculate_checksum_sha256(file_obj):
        """
        Calcula el SHA256 del archivo.
        
        Útil para:
        - deduplicación
        - detección de duplicados
        - integridad
        
        Args:
            file_obj: Objeto de archivo
        
        Returns:
            str: Hash SHA256 en hexadecimal
        """
        if not file_obj:
            return ""

        try:
            sha256_hash = hashlib.sha256()
            file_obj.seek(0)

            # Leer en chunks si es posible
            if hasattr(file_obj, "chunks"):
                for chunk in file_obj.chunks():
                    sha256_hash.update(chunk)
            else:
                sha256_hash.update(file_obj.read())

            file_obj.seek(0)
            return sha256_hash.hexdigest()

        except Exception:
            return ""

    # ==========================================================
    # TAMAÑO
    # ==========================================================

    @staticmethod
    def get_file_size(file_obj):
        """
        Obtiene el tamaño del archivo en bytes.
        
        Args:
            file_obj: Objeto de archivo
        
        Returns:
            int: Tamaño en bytes
        """
        if not file_obj:
            return 0

        try:
            return file_obj.size
        except Exception:
            return 0

    # ==========================================================
    # EXTENSIÓN
    # ==========================================================

    @staticmethod
    def get_extension(file_obj):
        """
        Extrae la extensión del archivo.
        
        Args:
            file_obj: Objeto de archivo
        
        Returns:
            str: Extensión sin punto (ej: "png", "pdf")
        """
        if not file_obj:
            return ""

        try:
            filename = getattr(file_obj, "name", "")
            _, ext = os.path.splitext(filename)
            return ext.lower().replace(".", "")
        except Exception:
            return ""

    # ==========================================================
    # ANÁLISIS COMPLETO
    # ==========================================================

    @staticmethod
    def analyze(file_obj):
        """
        Realiza un análisis completo del archivo.
        
        Returns:
            dict: {
                "mime_type": str,
                "extension": str,
                "size_bytes": int,
                "checksum": str,
            }
        """
        if not file_obj:
            return {
                "mime_type": "application/octet-stream",
                "extension": "",
                "size_bytes": 0,
                "checksum": "",
            }

        return {
            "mime_type": FileAnalyzer.detect_mime_type(file_obj),
            "extension": FileAnalyzer.get_extension(file_obj),
            "size_bytes": FileAnalyzer.get_file_size(file_obj),
            "checksum": FileAnalyzer.calculate_checksum_sha256(file_obj),
        }
