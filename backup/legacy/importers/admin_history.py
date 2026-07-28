from contextlib import closing

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .master_base import MasterImportError, MasterModelImporter


class AdminLogImporter(MasterModelImporter):
    table_name = "django_admin_log"
    model = LogEntry
    columns = (
        "id", "object_id", "object_repr", "action_flag", "change_message",
        "content_type_id", "user_id", "action_time",
    )
    nullable_fields = frozenset({"object_id", "content_type_id"})
    integer_fields = frozenset({"action_flag", "content_type_id", "user_id"})
    timestamp_fields = ("action_time",)
    foreign_keys = {
        "content_type_id": ContentType,
        "user_id": get_user_model(),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type_map = {}

    def validate_foreign_keys(self):
        with closing(self._connect()) as connection:
            user_ids = {
                row[0]
                for row in connection.execute(
                    'SELECT DISTINCT user_id FROM "django_admin_log"'
                )
            }
            existing_users = set(
                get_user_model().objects.using(self.using)
                .filter(pk__in=user_ids)
                .values_list("pk", flat=True)
            )
            missing_users = sorted(user_ids - existing_users)
            if missing_users:
                raise MasterImportError(
                    f"FK inválidas user_id en django_admin_log: {missing_users}"
                )
            rows = connection.execute(
                """
                SELECT DISTINCT l.content_type_id, c.app_label, c.model
                FROM django_admin_log l
                JOIN django_content_type c ON c.id = l.content_type_id
                WHERE l.content_type_id IS NOT NULL
                """
            )
            for legacy_id, app_label, model in rows:
                try:
                    current = ContentType.objects.db_manager(self.using).get(
                        app_label=app_label,
                        model=model,
                    )
                except ContentType.DoesNotExist as exc:
                    raise MasterImportError(
                        f"ContentType legacy sin equivalente: {app_label}.{model}"
                    ) from exc
                self.content_type_map[legacy_id] = current.pk

    def build_instance(self, row):
        converted = dict(row)
        legacy_id = converted.get("content_type_id")
        if legacy_id is not None:
            converted["content_type_id"] = self.content_type_map[legacy_id]
        return super().build_instance(converted)
