"""Interfaz común de los futuros importadores legacy."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseImporter(ABC):
    """Contrato común de los importadores legacy."""

    @abstractmethod
    def prepare(self):
        """Preparar el lote sin escribir registros."""

    @abstractmethod
    def validate(self):
        """Validar el lote preparado."""

    @abstractmethod
    def import_batch(self, batch):
        """Importar un lote previamente validado."""

    @abstractmethod
    def finalize(self):
        """Finalizar y validar el importador."""
