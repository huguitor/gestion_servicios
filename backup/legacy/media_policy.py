"""Política declarativa de publicación y conversión multimedia legacy."""

from __future__ import annotations

from dataclasses import dataclass

from archivos.models import ArchivoRelacion


@dataclass(frozen=True)
class MediaPolicy:
    table: str
    field: str
    target_model: str
    publish_file_field: bool
    create_archivo: bool
    role: str
    type_name: str
    folder: str
    required: bool = True

    @property
    def mode(self):
        if self.publish_file_field and self.create_archivo:
            return "file_field_and_archivo"
        if self.publish_file_field:
            return "file_field"
        return "archivo"


def _policy(
    table,
    field,
    target_model,
    *,
    file_field,
    archivo,
    role,
    type_name,
    folder,
):
    return MediaPolicy(
        table=table,
        field=field,
        target_model=target_model,
        publish_file_field=file_field,
        create_archivo=archivo,
        role=role,
        type_name=type_name,
        folder=folder,
    )


MEDIA_POLICIES = (
    _policy(
        "productos_producto", "foto", "productos.Producto",
        file_field=False, archivo=True, role="principal",
        type_name="Imagen de producto", folder="producto-imagen",
    ),
    _policy(
        "productos_producto", "plano", "productos.Producto",
        file_field=False, archivo=True, role="plano",
        type_name="Plano de producto", folder="producto-plano",
    ),
    _policy(
        "productos_servicio", "imagen", "productos.Servicio",
        file_field=True, archivo=True, role="principal",
        type_name="Imagen de servicio", folder="servicio-imagen",
    ),
    _policy(
        "productos_servicio", "adjunto", "productos.Servicio",
        file_field=True, archivo=True, role="adjunto",
        type_name="Adjunto de servicio", folder="servicio-adjunto",
    ),
    _policy(
        "productos_servicio", "video", "productos.Servicio",
        file_field=True, archivo=True, role="video",
        type_name="Video de servicio", folder="servicio-video",
    ),
    _policy(
        "presupuestos_presupuestoadjunto",
        "archivo",
        "presupuestos.PresupuestoAdjunto",
        file_field=True,
        archivo=True,
        role="adjunto",
        type_name="Adjunto de presupuesto",
        folder="presupuesto-adjunto",
    ),
    _policy(
        "remitos_remitoadjunto",
        "archivo",
        "remitos.RemitoAdjunto",
        file_field=True,
        archivo=True,
        role="adjunto",
        type_name="Adjunto de remito",
        folder="remito-adjunto",
    ),
    _policy(
        "configuracion_configuracionglobal",
        "logo_principal",
        "configuracion.ConfiguracionGlobal",
        file_field=True,
        archivo=True,
        role="principal",
        type_name="Logo principal",
        folder="configuracion-logo-principal",
    ),
    _policy(
        "configuracion_configuracionglobal",
        "logo_favicon",
        "configuracion.ConfiguracionGlobal",
        file_field=True,
        archivo=True,
        role="secundaria",
        type_name="Logo favicon",
        folder="configuracion-logo-favicon",
    ),
    _policy(
        "configuracion_configuracionglobal",
        "logo_tkinter",
        "configuracion.ConfiguracionGlobal",
        file_field=True,
        archivo=True,
        role="secundaria",
        type_name="Logo de escritorio",
        folder="configuracion-logo-escritorio",
    ),
    *(
        _policy(
            "configuracion_configuracionglobal",
            f"imagen_publicitaria_{position}",
            "configuracion.ConfiguracionGlobal",
            file_field=True,
            archivo=True,
            role="galeria",
            type_name=f"Imagen publicitaria {position}",
            folder=f"configuracion-publicitaria-{position}",
        )
        for position in (1, 2, 3)
    ),
)

MEDIA_POLICY_BY_KEY = {
    (policy.table, policy.field): policy for policy in MEDIA_POLICIES
}


def validate_media_policies():
    allowed_roles = {value for value, _label in ArchivoRelacion.ROL_ARCHIVO}
    invalid = sorted(
        {
            policy.role
            for policy in MEDIA_POLICIES
            if policy.role not in allowed_roles
        }
    )
    if invalid:
        raise RuntimeError(f"Roles multimedia inválidos: {invalid}")
    if len(MEDIA_POLICY_BY_KEY) != len(MEDIA_POLICIES):
        raise RuntimeError("La política multimedia contiene claves duplicadas.")


validate_media_policies()
