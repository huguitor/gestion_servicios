"""
file_storage.py

Abstracción de almacenamiento de archivos.

REGLA CRÍTICA:
    ❌ Prohibido usar default_storage fuera de este archivo
    ✅ Todo acceso a storage va aquí
    ✅ Agnóstico: local, S3, MinIO, CDN, hybrid

Si mañana cambias a S3/MinIO:
    - Modificas SOLO este archivo
    - El resto del código no se entera

Permite:
    - Storage local → S3 sin tocar models/views/serializers
    - CDN firmado
    - Storage híbrido (local + cloud)
    - Cualquier storage del futuro
"""

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io


class StorageError(Exception):
    """Error en operaciones de storage"""
    pass


class FileStorage:
    """
    ABSTRACCIÓN ÚNICA de almacenamiento.
    
    Regla: Si necesitas acceder a storage, vienes aquí.
    
    Punto de cambio: Si cambias backend de storage,
    SOLO modificas este archivo, nada más.
    """

    # ==========================================================
    # GUARDAR ARCHIVO
    # ==========================================================

    @staticmethod
    def save(file_obj, path):
        """
        Guarda un archivo en storage.
        
        Args:
            file_obj: Archivo a guardar (InMemoryUploadedFile, etc)
            path: Ruta relativa (ej: "archivos/imagenes/foto.jpg")
        
        Returns:
            str: Path en storage del archivo guardado
        
        Raises:
            StorageError: Si falla guardar
        """
        if not file_obj or not path:
            raise StorageError("file_obj y path son requeridos")

        try:
            saved_path = default_storage.save(path, file_obj)
            return saved_path
        except Exception as e:
            raise StorageError(
                f"Error guardando archivo en {path}: {str(e)}"
            )

    # ==========================================================
    # OBTENER URL (punto crítico de abstracción)
    # ==========================================================

    @staticmethod
    def url(storage_path):
        """
        Obtiene la URL pública de un archivo.
        
        ABSTRACCIÓN CRÍTICA:
        - Si storage es local → /media/...
        - Si storage es S3 → https://s3.amazonaws.com/...
        - Si storage es CDN → https://cdn.example.com/...
        
        El modelo/serializer NO sabe cuál es.
        
        Args:
            storage_path: Path en storage
        
        Returns:
            str: URL pública del archivo
        
        Raises:
            StorageError: Si falla obtener URL
        """
        if not storage_path:
            return None

        try:
            return default_storage.url(storage_path)
        except Exception as e:
            raise StorageError(
                f"Error obteniendo URL de {storage_path}: {str(e)}"
            )

    # ==========================================================
    # ELIMINAR ARCHIVO
    # ==========================================================

    @staticmethod
    def delete(storage_path):
        """
        Elimina un archivo del storage.
        
        Args:
            storage_path: Path del archivo a eliminar
        
        Returns:
            bool: True si se eliminó
        
        Raises:
            StorageError: Si falla eliminar
        """
        if not storage_path:
            return False

        try:
            if default_storage.exists(storage_path):
                default_storage.delete(storage_path)
                return True
            return False
        except Exception as e:
            raise StorageError(
                f"Error eliminando {storage_path}: {str(e)}"
            )

    # ==========================================================
    # VERIFICAR EXISTENCIA
    # ==========================================================

    @staticmethod
    def exists(storage_path):
        """
        Verifica si un archivo existe.
        
        Args:
            storage_path: Path a verificar
        
        Returns:
            bool: True si existe
        """
        if not storage_path:
            return False

        try:
            return default_storage.exists(storage_path)
        except Exception:
            return False

    # ==========================================================
    # LEER CONTENIDO
    # ==========================================================

    @staticmethod
    def read(storage_path):
        """
        Lee el contenido de un archivo.
        
        Args:
            storage_path: Path del archivo
        
        Returns:
            bytes: Contenido del archivo
        
        Raises:
            StorageError: Si falla leer
        """
        if not storage_path:
            return None

        try:
            with default_storage.open(storage_path, "rb") as f:
                return f.read()
        except Exception as e:
            raise StorageError(
                f"Error leyendo {storage_path}: {str(e)}"
            )

    # ==========================================================
    # COPIAR ARCHIVO (dentro del mismo storage)
    # ==========================================================

    @staticmethod
    def copy(source_path, dest_path):
        """
        Copia un archivo dentro del storage.
        
        Útil para deduplicación.
        
        Args:
            source_path: Path origen
            dest_path: Path destino
        
        Returns:
            str: Path del archivo copiado
        
        Raises:
            StorageError: Si falla copiar
        """
        if not source_path or not dest_path:
            raise StorageError("source_path y dest_path son requeridos")

        try:
            if not default_storage.exists(source_path):
                raise StorageError(f"Archivo origen no existe: {source_path}")

            contenido = FileStorage.read(source_path)
            if not contenido:
                raise StorageError(f"No se pudo leer: {source_path}")

            return FileStorage.save(
                ContentFile(contenido),
                dest_path
            )
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Error copiando archivo: {str(e)}")

    # ==========================================================
    # GENERAR RUTA DE ALMACENAMIENTO
    # ==========================================================

    @staticmethod
    def generate_path(carpeta, nombre_original):
        """
        Genera la ruta donde guardar un archivo.
        
        Estructura: archivos/{carpeta}/{nombre_original}
        
        Args:
            carpeta: Carpeta lógica (ej: "imagenes", "documentos")
            nombre_original: Nombre original del archivo
        
        Returns:
            str: Ruta completa en storage
        """
        if not carpeta:
            carpeta = "otros"

        if not nombre_original:
            nombre_original = "archivo"

        return f"archivos/{carpeta}/{nombre_original}"

    # ==========================================================
    # TAMAÑO DE ARCHIVO
    # ==========================================================

    @staticmethod
    def size(storage_path):
        """
        Obtiene el tamaño de un archivo en storage.
        
        Args:
            storage_path: Path del archivo
        
        Returns:
            int: Tamaño en bytes, o -1 si error
        """
        if not storage_path:
            return -1

        try:
            return default_storage.size(storage_path)
        except Exception:
            return -1

    # ==========================================================
    # LISTAR ARCHIVOS EN CARPETA
    # ==========================================================

    @staticmethod
    def list_directory(path):
        """
        Lista archivos en una carpeta del storage.
        
        Args:
            path: Ruta de la carpeta
        
        Returns:
            tuple: (directorios, archivos)
        """
        if not path:
            return ([], [])

        try:
            directories, files = default_storage.listdir(path)
            return (directories, files)
        except Exception:
            return ([], [])

