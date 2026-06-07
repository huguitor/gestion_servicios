# gestion/backend/pedidos_internos/apps.py
from django.apps import AppConfig


class PedidosInternosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pedidos_internos'
    verbose_name = 'Pedidos internos'
