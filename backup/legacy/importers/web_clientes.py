from django.contrib.auth import get_user_model

from clientes.models import Cliente
from web_clientes.models import ClienteWeb

from .master_base import MasterModelImporter


class ClienteWebImporter(MasterModelImporter):
    table_name = "web_clientes_clienteweb"
    model = ClienteWeb
    columns = (
        "id", "telefono", "activo", "email_verificado", "acepta_terminos",
        "fecha_alta", "ultimo_acceso", "cliente_id", "user_id",
    )
    nullable_fields = frozenset({"ultimo_acceso", "cliente_id"})
    boolean_fields = frozenset(
        {"activo", "email_verificado", "acepta_terminos"}
    )
    integer_fields = frozenset({"cliente_id", "user_id"})
    timestamp_fields = ("fecha_alta", "ultimo_acceso")
    unique_fields = ("user_id", "cliente_id")
    foreign_keys = {
        "user_id": get_user_model(),
        "cliente_id": Cliente,
    }
