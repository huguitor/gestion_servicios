from django.apps import AppConfig


class CobranzasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cobranzas"
    verbose_name = "Cobranzas"

    def ready(self):
        from . import signals  # noqa: F401
