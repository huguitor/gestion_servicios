"""
file_validator.py

Validación de archivos:
- Tamaño máximo
- Extensiones permitidas
- Reglas de negocio

Centraliza todas las reglas de validación en un solo lugar.
"""

import os
from django.conf import settings


class FileValidator:
    """
    Servicio de validación de archivos.
    
    Encapsula:
    - validación de tamaño
    - validación de extensión
    - validaciones de negocio
    """

    # ==========================================================
    # TAMAÑO
    # ==========================================================

    @staticmethod
    def validate_size(file_obj):
        """
        Valida que el archivo no supere el tamaño máximo.
        
        Raises:
            ValueError: Si el archivo supera el límite
        """
        if not file_obj:
            return

        max_size_mb = getattr(
            settings,
            "ARCHIVOS_MAX_MB",
            500
        )
        max_size_bytes = max_size_mb * 1024 * 1024

        if file_obj.size > max_size_bytes:
            raise ValueError(
                f"El archivo supera el límite de {max_size_mb} MB. "
                f"Tamaño: {file_obj.size / (1024*1024):.2f} MB"
            )

    # ==========================================================
    # EXTENSIÓN
    # ==========================================================

    @staticmethod
    def validate_extension(file_obj):
        """
        Valida que la extensión esté permitida.
        
        Reads from settings.EXTENSIONES_PERMITIDAS:
            {
                "imagenes": ["jpg", "png", "gif"],
                "documentos": ["pdf", "doc", "docx"],
                ...
            }
        
        Raises:
            ValueError: Si la extensión no está permitida
        """
        if not file_obj:
            return

        # Extraer extensión
        filename = getattr(file_obj, "name", "")
        _, ext = os.path.splitext(filename)
        ext = ext.lower().replace(".", "")

        # Obtener todas las extensiones permitidas
        extensiones_por_grupo = getattr(
            settings,
            "EXTENSIONES_PERMITIDAS",
            {}
        )

        extensiones_permitidas = set()
        for grupo, exts in extensiones_por_grupo.items():
            extensiones_permitidas.update(exts)

        if ext not in extensiones_permitidas:
            raise ValueError(
                f"Extensión no permitida: .{ext}. "
                f"Extensiones válidas: {', '.join(sorted(extensiones_permitidas))}"
            )

    # ==========================================================
    # MIME (validación de negocio)
    # ==========================================================

    @staticmethod
    def validate_mime_allowed(mime_type):
        """
        Valida que el MIME esté permitido por configuración.
        
        Reads from settings.ARCHIVOS_MIME_PERMITIDOS (opcional).
        
        Args:
            mime_type (str): MIME type detectado (ej: "image/png")
        
        Raises:
            ValueError: Si el MIME no está permitido
        """
        if not mime_type:
            return

        mime_permitidos = getattr(
            settings,
            "ARCHIVOS_MIME_PERMITIDOS",
            None
        )

        # Si no está configurado, permitir todos
        if not mime_permitidos:
            return

        if mime_type not in mime_permitidos:
            raise ValueError(
                f"Tipo MIME no permitido: {mime_type}"
            )

    # ==========================================================
    # VALIDACIÓN COMPLETA
    # ==========================================================

    @staticmethod
    def validate_all(file_obj):
        """
        Ejecuta todas las validaciones en orden.
        
        Args:
            file_obj: Objeto de archivo (InMemoryUploadedFile)
        
        Raises:
            ValueError: Si alguna validación falla
        """
        FileValidator.validate_size(file_obj)
        FileValidator.validate_extension(file_obj)
