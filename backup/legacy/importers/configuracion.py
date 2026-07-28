from configuracion.models import ConfiguracionGlobal

from .master_base import MasterImportError, MasterModelImporter


class ConfiguracionImporter(MasterModelImporter):
    table_name = "configuracion_configuracionglobal"
    model = ConfiguracionGlobal
    columns = (
        "id", "nombre_empresa", "cuit", "direccion", "telefono", "email",
        "pagina_web", "logo_principal", "logo_favicon", "logo_tkinter",
        "imagen_publicitaria_1", "imagen_publicitaria_2",
        "imagen_publicitaria_3", "condiciones_comerciales", "iva_por_defecto",
        "dias_validez_presupuesto", "moneda", "pais", "idioma", "activo",
        "creado", "actualizado", "imagen_publicitaria_1_alto",
        "imagen_publicitaria_1_ancho", "imagen_publicitaria_1_proporcion",
        "imagen_publicitaria_2_alto", "imagen_publicitaria_2_ancho",
        "imagen_publicitaria_2_proporcion", "imagen_publicitaria_3_alto",
        "imagen_publicitaria_3_ancho", "imagen_publicitaria_3_proporcion",
        "logo_favicon_alto", "logo_favicon_ancho", "logo_favicon_proporcion",
        "logo_principal_alto", "logo_principal_ancho",
        "logo_principal_proporcion", "logo_tkinter_alto",
        "logo_tkinter_ancho", "logo_tkinter_proporcion",
        "descripcion_sistema", "nombre_fantasia",
    )
    nullable_fields = frozenset(
        {
            "logo_principal", "logo_favicon", "logo_tkinter",
            "imagen_publicitaria_1", "imagen_publicitaria_2",
            "imagen_publicitaria_3",
        }
    )
    boolean_fields = frozenset(
        {
            "activo", "imagen_publicitaria_1_proporcion",
            "imagen_publicitaria_2_proporcion",
            "imagen_publicitaria_3_proporcion", "logo_favicon_proporcion",
            "logo_principal_proporcion", "logo_tkinter_proporcion",
        }
    )
    integer_fields = frozenset(
        {
            "dias_validez_presupuesto", "imagen_publicitaria_1_alto",
            "imagen_publicitaria_1_ancho", "imagen_publicitaria_2_alto",
            "imagen_publicitaria_2_ancho", "imagen_publicitaria_3_alto",
            "imagen_publicitaria_3_ancho", "logo_favicon_alto",
            "logo_favicon_ancho", "logo_principal_alto",
            "logo_principal_ancho", "logo_tkinter_alto",
            "logo_tkinter_ancho",
        }
    )
    decimal_fields = frozenset({"iva_por_defecto"})

    def validate_source(self, connection):
        count, active = connection.execute(
            f'SELECT COUNT(*), SUM(CASE WHEN activo = 1 THEN 1 ELSE 0 END) '
            f'FROM "{self.table_name}"'
        ).fetchone()
        if count and active != 1:
            raise MasterImportError(
                "Configuración requiere exactamente una fila activa."
            )

    def build_instance(self, row):
        instance = super().build_instance(row)
        positive_fields = self.integer_fields
        invalid = [
            field_name
            for field_name in positive_fields
            if getattr(instance, field_name) <= 0
        ]
        if invalid:
            raise MasterImportError(
                "Dimensiones o días no positivos: " + ", ".join(sorted(invalid))
            )
        if instance.iva_por_defecto < 0:
            raise MasterImportError("iva_por_defecto no puede ser negativo.")
        return instance
