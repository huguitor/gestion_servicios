"""
file_service.py

Servicio central de orquestación de archivos.

PUNTO ÚNICO DE ENTRADA para todo upload/proceso de archivos.

Combina:
- Validación (FileValidator)
- Análisis (FileAnalyzer)
- Almacenamiento (FileStorage)

Patrón: Facade + Orchestrator
"""

import os
from django.db import transaction
from .file_validator import FileValidator
from .file_analyzer import FileAnalyzer
from .file_storage import FileStorage


class FileService:
    """
    Servicio central de gestión de archivos.
    
    PUNTO ÚNICO DE VERDAD para todo lo relacionado con archivos.
    
    Orquesta:
    - Validación
    - Análisis
    - Almacenamiento
    
    Si necesitas hacer algo con archivos, vienes aquí.
    """

    # ==========================================================
    # VALIDACIÓN + ANÁLISIS (sin guardar)
    # ==========================================================

    @staticmethod
    def process_file(file_obj, perform_mime_validation=True):
        """
        Procesa un archivo: valida y analiza.
        
        NO guarda el archivo.
        Útil para pasar metadata al serializer antes de crear el Archivo.
        
        Args:
            file_obj: Archivo a procesar
            perform_mime_validation: Si validar MIME permitido
        
        Returns:
            dict: {
                "mime_type": str,
                "extension": str,
                "size_bytes": int,
                "checksum": str,
                "is_valid": bool,
                "errors": list,
            }
        
        Raises:
            ValueError: Si validación falla
        """
        errors = []
        
        try:
            # 1. VALIDAR
            FileValidator.validate_all(file_obj)
            
            # 2. ANALIZAR
            analysis = FileAnalyzer.analyze(file_obj)
            
            # 3. VALIDAR MIME (si está configurado)
            if perform_mime_validation:
                try:
                    FileValidator.validate_mime_allowed(
                        analysis["mime_type"]
                    )
                except ValueError as e:
                    errors.append(str(e))
            
            return {
                "mime_type": analysis["mime_type"],
                "extension": analysis["extension"],
                "size_bytes": analysis["size_bytes"],
                "checksum": analysis["checksum"],
                "is_valid": len(errors) == 0,
                "errors": errors,
            }
            
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Error procesando archivo: {str(e)}")

    # ==========================================================
    # UPLOAD COMPLETO (PUNTO ÚNICO DE ENTRADA)
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def upload_deduplicated(
        file_obj,
        *,
        tipo,
        content_type,
        object_id,
        rol="principal",
        usuario=None,
        observaciones="",
        carpeta_almacenamiento=None,
        perform_mime_validation=True,
    ):
        """Crea o reutiliza Archivo por checksum y asegura su relación."""
        from ..models import Archivo, ArchivoRelacion

        allowed_roles = {
            value for value, _label in ArchivoRelacion.ROL_ARCHIVO
        }
        if rol not in allowed_roles:
            raise ValueError(f"Rol de archivo inválido: {rol}")
        if content_type is None or object_id is None:
            raise ValueError(
                "content_type y object_id son requeridos para deduplicar."
            )

        metadata = FileService.process_file(
            file_obj,
            perform_mime_validation=perform_mime_validation,
        )
        if not metadata["is_valid"]:
            raise ValueError(
                f"Validación fallida: {', '.join(metadata['errors'])}"
            )
        matches = list(
            Archivo.objects.select_for_update()
            .filter(checksum=metadata["checksum"], activo=True)
            .order_by("pk")[:2]
        )
        if len(matches) > 1:
            raise ValueError(
                "Existen múltiples Archivo activos para el mismo checksum."
            )
        if matches:
            archivo = matches[0]
            relation, relation_created = ArchivoRelacion.objects.get_or_create(
                archivo=archivo,
                content_type=content_type,
                object_id=object_id,
                defaults={
                    "rol": rol,
                    "observaciones": observaciones or "",
                },
            )
            if relation.rol != rol:
                raise ValueError(
                    "La relación existente posee un rol incompatible: "
                    f"{relation.rol} != {rol}."
                )
            return {
                "archivo_id": archivo.pk,
                "archivo_path": archivo.archivo.name,
                "relacion_id": relation.pk,
                "checksum": archivo.checksum,
                "mime_type": archivo.mime_type,
                "extension": archivo.extension,
                "tamaño_bytes": archivo.tamano_bytes,
                "archivo_created": False,
                "archivo_reused": True,
                "relation_created": relation_created,
                "relation_reused": not relation_created,
            }

        file_obj.seek(0)
        uploaded = FileService.upload(
            file_obj,
            tipo=tipo,
            content_type=content_type,
            object_id=object_id,
            usuario=usuario,
            rol=rol,
            observaciones=observaciones,
            carpeta_almacenamiento=carpeta_almacenamiento,
            perform_mime_validation=perform_mime_validation,
        )
        archivo = Archivo.objects.get(pk=uploaded["archivo_id"])
        return {
            **uploaded,
            "archivo_path": archivo.archivo.name,
            "archivo_created": True,
            "archivo_reused": False,
            "relation_created": uploaded["relacion_id"] is not None,
            "relation_reused": False,
        }

    @staticmethod
    @transaction.atomic
    def upload(
        file_obj,
        *,
        tipo,
        content_type=None,
        object_id=None,
        usuario=None,
        rol="principal",
        observaciones="",
        carpeta_almacenamiento=None,
        perform_mime_validation=True,
    ):
        """
        PUNTO ÚNICO DE ENTRADA para todo upload de archivos.
        
        Hace TODO:
        - Valida archivo
        - Analiza metadata
        - Guarda en storage
        - Crea Archivo en BD
        - Crea ArchivoRelacion (si content_type + object_id)
        
        Args:
            file_obj: Archivo a subir
            tipo: TipoArchivo instance
            content_type: ContentType (para ArchivoRelacion), opcional
            object_id: ID del objeto relacionado, opcional
            usuario: Usuario que sube (para auditoría), opcional
            carpeta_almacenamiento: Carpeta dentro de storage, si None usa tipo.carpeta
            perform_mime_validation: Si validar MIME permitido
        
        Returns:
            dict: {
                "archivo_id": int,
                "archivo_url": str,
                "relacion_id": int (si hubo relación),
                "mime_type": str,
                "extension": str,
                "checksum": str,
                "tamaño_bytes": int,
            }
        
        Raises:
            ValueError: Si validación/almacenamiento falla
        
        Example:
            result = FileService.upload(
                file_obj=request.FILES["archivo"],
                tipo=tipo_instance,
                content_type=ContentType.objects.get(model="producto"),
                object_id=42,
                usuario=request.user,
            )
            
            print(result["archivo_url"])  # URL del archivo
        """
        # Importar aquí para evitar circular import
        from ..models import Archivo, ArchivoRelacion

        if not file_obj:
            raise ValueError("No se envió archivo")

        if not tipo:
            raise ValueError("tipo es requerido")

        # Variable para cleanup si falla
        stored_path = None

        try:
            # 1. PROCESAR (validar + analizar)
            try:
                file_metadata = FileService.process_file(
                    file_obj,
                    perform_mime_validation=perform_mime_validation
                )
            except ValueError as e:
                raise ValueError(f"Error en validación: {str(e)}")

            if not file_metadata["is_valid"]:
                raise ValueError(
                    f"Validación fallida: {', '.join(file_metadata['errors'])}"
                )

            # 2. GUARDAR EN STORAGE
            try:
                # Determinar carpeta
                if not carpeta_almacenamiento:
                    carpeta_almacenamiento = tipo.carpeta or "otros"

                storage_path = FileStorage.generate_path(
                    carpeta_almacenamiento,
                    file_obj.name
                )

                stored_path = FileStorage.save(file_obj, storage_path)

            except Exception as e:
                raise ValueError(f"Error guardando archivo: {str(e)}")

            # 3. CREAR REGISTRO EN BD
            try:
                archivo = Archivo.objects.create(
                    nombre=os.path.basename(file_obj.name),
                    nombre_original=file_obj.name,
                    archivo=stored_path,  # Guardar el path, no el file_obj
                    tipo=tipo,
                    usuario_creacion=usuario,
                    mime_type=file_metadata["mime_type"],
                    extension=file_metadata["extension"],
                    tamano_bytes=file_metadata["size_bytes"],
                    checksum=file_metadata["checksum"],
                    activo=True,
                )
            except Exception as e:
                raise ValueError(f"Error creando Archivo: {str(e)}")

            # 4. CREAR RELACIÓN POLIMÓRFICA (si es necesario)
            #
            # La relación es parte de la MISMA transacción atómica que
            # el Archivo. Si falla (ej: viola unique_together), se
            # propaga y se hace rollback de TODO + cleanup del storage.
            # No se traga el error: un upload a medias deja huérfanos.
            relacion_id = None
            if content_type and object_id:
                relacion = ArchivoRelacion.objects.create(
                    archivo=archivo,
                    content_type=content_type,
                    object_id=object_id,
                    rol=rol or "principal",
                    observaciones=observaciones or "",
                )
                relacion_id = relacion.id

            # 5. RETORNAR RESULTADO
            return {
                "archivo_id": archivo.id,
                "archivo_url": FileStorage.url(stored_path),
                "relacion_id": relacion_id,
                "mime_type": file_metadata["mime_type"],
                "extension": file_metadata["extension"],
                "checksum": file_metadata["checksum"],
                "tamaño_bytes": file_metadata["size_bytes"],
            }

        except Exception as e:
            # CLEANUP CRÍTICO: Si algo falla, borrar el archivo guardado
            # Esto garantiza que NO quedan archivos huérfanos
            if stored_path:
                try:
                    FileStorage.delete(stored_path)
                except Exception:
                    # Si borrarlo también falla, al menos lo intentamos
                    pass
            raise

    # ==========================================================
    # VALIDACIÓN SIMPLE (sin análisis ni almacenamiento)
    # ==========================================================

    @staticmethod
    def validate_file(file_obj):
        """
        Solo valida (tamaño, extensión).
        
        Returns:
            dict: {"is_valid": bool, "errors": list}
        
        Raises:
            ValueError: Propaga errores de validación
        """
        errors = []
        
        try:
            FileValidator.validate_all(file_obj)
            return {"is_valid": True, "errors": []}
        except ValueError as e:
            return {"is_valid": False, "errors": [str(e)]}

    # ==========================================================
    # ANÁLISIS SIMPLE (sin validación)
    # ==========================================================

    @staticmethod
    def analyze_file(file_obj):
        """
        Solo analiza (MIME, checksum, tamaño).
        No valida restricciones.
        
        Returns:
            dict: {
                "mime_type": str,
                "extension": str,
                "size_bytes": int,
                "checksum": str,
            }
        """
        return FileAnalyzer.analyze(file_obj)

    # ==========================================================
    # OPERACIONES DE STORAGE (DELEGADAS)
    # ==========================================================

    @staticmethod
    def get_file_url(storage_path):
        """Obtiene URL de un archivo en storage."""
        return FileStorage.url(storage_path)

    @staticmethod
    def delete_file(storage_path):
        """Elimina un archivo del storage."""
        return FileStorage.delete(storage_path)

    @staticmethod
    def file_exists(storage_path):
        """Verifica si existe un archivo."""
        return FileStorage.exists(storage_path)

    @staticmethod
    def generate_storage_path(carpeta, nombre_archivo):
        """Genera ruta de almacenamiento."""
        return FileStorage.generate_path(carpeta, nombre_archivo)
