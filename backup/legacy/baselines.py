"""Baselines declarativos creados por migraciones del esquema actual."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineSpec:
    table: str
    model_label: str
    fields: tuple[str, ...]
    rows: tuple[dict, ...]
    key_fields: tuple[str, ...] = ("id",)


GROUP_ROWS = tuple(
    {"id": position, "name": f"PERSONAL_{code}"}
    for position, code in enumerate(
        (
            "OPERARIO",
            "ADMINISTRATIVO",
            "SUPERVISOR",
            "ADMINISTRADOR_GENERAL",
        ),
        start=1,
    )
)

ROLE_ROWS = (
    {
        "id": 1,
        "codigo": "OPERARIO",
        "nombre": "Operario",
        "descripcion": "",
        "grupo_id": 1,
        "activo": True,
        "orden": 10,
    },
    {
        "id": 2,
        "codigo": "ADMINISTRATIVO",
        "nombre": "Administrativo",
        "descripcion": "",
        "grupo_id": 2,
        "activo": True,
        "orden": 20,
    },
    {
        "id": 3,
        "codigo": "SUPERVISOR",
        "nombre": "Supervisor",
        "descripcion": "",
        "grupo_id": 3,
        "activo": True,
        "orden": 30,
    },
    {
        "id": 4,
        "codigo": "ADMINISTRADOR_GENERAL",
        "nombre": "Administrador general",
        "descripcion": "",
        "grupo_id": 4,
        "activo": True,
        "orden": 40,
    },
)


def _permission_row(
    row_id,
    group_id,
    permission_id,
    model,
    codename,
):
    return {
        "id": row_id,
        "group_id": group_id,
        "permission_id": permission_id,
        "permission__content_type__app_label": "personal",
        "permission__content_type__model": model,
        "permission__codename": codename,
    }


GROUP_PERMISSION_ROWS = (
    _permission_row(1, 2, 1, "empleado", "access_admin_frontend"),
    _permission_row(2, 3, 1, "empleado", "access_admin_frontend"),
    _permission_row(3, 4, 1, "empleado", "access_admin_frontend"),
    _permission_row(4, 3, 5, "empleado", "view_empleado"),
    _permission_row(5, 3, 9, "rolpersonal", "view_rolpersonal"),
    _permission_row(6, 3, 13, "cargo", "view_cargo"),
    _permission_row(7, 4, 2, "empleado", "add_empleado"),
    _permission_row(8, 4, 3, "empleado", "change_empleado"),
    _permission_row(9, 4, 4, "empleado", "delete_empleado"),
    _permission_row(10, 4, 5, "empleado", "view_empleado"),
    _permission_row(11, 4, 6, "rolpersonal", "add_rolpersonal"),
    _permission_row(12, 4, 7, "rolpersonal", "change_rolpersonal"),
    _permission_row(13, 4, 8, "rolpersonal", "delete_rolpersonal"),
    _permission_row(14, 4, 9, "rolpersonal", "view_rolpersonal"),
    _permission_row(15, 4, 10, "cargo", "add_cargo"),
    _permission_row(16, 4, 11, "cargo", "change_cargo"),
    _permission_row(17, 4, 12, "cargo", "delete_cargo"),
    _permission_row(18, 4, 13, "cargo", "view_cargo"),
)


BASELINE_SPECS = (
    BaselineSpec(
        table="auth_group",
        model_label="auth.Group",
        fields=("id", "name"),
        rows=GROUP_ROWS,
    ),
    BaselineSpec(
        table="auth_group_permissions",
        model_label="auth.Group_permissions",
        fields=(
            "id",
            "group_id",
            "permission_id",
            "permission__content_type__app_label",
            "permission__content_type__model",
            "permission__codename",
        ),
        rows=GROUP_PERMISSION_ROWS,
    ),
    BaselineSpec(
        table="personal_rolpersonal",
        model_label="personal.RolPersonal",
        fields=(
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "grupo_id",
            "activo",
            "orden",
        ),
        rows=ROLE_ROWS,
    ),
)
