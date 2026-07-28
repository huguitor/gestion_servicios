from comprobantes.models import Comprobante

from .master_base import MasterImportError, MasterModelImporter


class ComprobanteImporter(MasterModelImporter):
    table_name = "comprobantes_comprobante"
    model = Comprobante
    columns = (
        "id", "tipo", "serie", "numero_inicial",
        "proximo_numero", "numero_final",
    )
    timestamp_fields = ()
    integer_fields = frozenset(
        {"numero_inicial", "proximo_numero", "numero_final"}
    )
    unique_together = (("tipo", "serie"),)

    def validate_source(self, connection):
        rows = connection.execute(
            f'SELECT id, tipo, numero_inicial, proximo_numero, numero_final '
            f'FROM "{self.table_name}"'
        )
        source_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        document_tables = {
            "PRES": "presupuestos_presupuesto",
            "REMI": "remitos_remito",
        }
        for pk, tipo, initial, next_number, final in rows:
            if final <= initial:
                raise MasterImportError(
                    f"Comprobante {pk}: numero_final debe superar numero_inicial."
                )
            if not initial <= next_number <= final:
                raise MasterImportError(
                    f"Comprobante {pk}: proximo_numero fuera del rango."
                )
            document_table = document_tables.get(tipo)
            if document_table and document_table in source_tables:
                maximum = connection.execute(
                    f'SELECT MAX(numero) FROM "{document_table}" '
                    f'WHERE comprobante_id = ?',
                    (pk,),
                ).fetchone()[0]
                if maximum is not None and next_number <= maximum:
                    raise MasterImportError(
                        f"Comprobante {pk}: proximo_numero ({next_number}) "
                        f"no supera el máximo histórico ({maximum})."
                    )
