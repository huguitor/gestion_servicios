"""
services/

Servicios de archivos.

Organización:
- file_validator.py  → Validaciones
- file_analyzer.py   → Análisis técnico
- file_storage.py    → Almacenamiento
- file_service.py    → Orquestación central

Uso:
    from archivos.services import FileService
    
    result = FileService.process_file(file_obj)
"""

from .file_validator import FileValidator
from .file_analyzer import FileAnalyzer
from .file_storage import FileStorage
from .file_service import FileService

__all__ = [
    "FileValidator",
    "FileAnalyzer",
    "FileStorage",
    "FileService",
]
