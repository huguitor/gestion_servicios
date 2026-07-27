import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ROLES = [
    ("OPERARIO", "Operario", 10),
    ("ADMINISTRATIVO", "Administrativo", 20),
    ("SUPERVISOR", "Supervisor", 30),
    ("ADMINISTRADOR_GENERAL", "Administrador general", 40),
]


def crear_roles_base(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    RolPersonal = apps.get_model("personal", "RolPersonal")
    db = schema_editor.connection.alias

    grupos = {}
    for codigo, nombre, orden in ROLES:
        grupo, _ = Group.objects.using(db).get_or_create(name=f"PERSONAL_{codigo}")
        RolPersonal.objects.using(db).get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "grupo": grupo, "orden": orden},
        )
        grupos[codigo] = grupo

    content_type, _ = ContentType.objects.using(db).get_or_create(app_label="personal", model="empleado")
    acceso, _ = Permission.objects.using(db).get_or_create(
        content_type=content_type,
        codename="access_admin_frontend",
        defaults={"name": "Puede acceder al frontend administrativo"},
    )
    grupos["ADMINISTRATIVO"].permissions.add(acceso)
    grupos["SUPERVISOR"].permissions.add(acceso)
    grupos["ADMINISTRADOR_GENERAL"].permissions.add(acceso)

    permisos_personal = []
    for modelo, nombre in [("empleado", "empleado"), ("rolpersonal", "rol de personal"), ("cargo", "cargo")]:
        ct, _ = ContentType.objects.using(db).get_or_create(app_label="personal", model=modelo)
        for accion, etiqueta in [("add", "Puede agregar"), ("change", "Puede cambiar"), ("delete", "Puede eliminar"), ("view", "Puede ver")]:
            permiso, _ = Permission.objects.using(db).get_or_create(
                content_type=ct,
                codename=f"{accion}_{modelo}",
                defaults={"name": f"{etiqueta} {nombre}"},
            )
            permisos_personal.append(permiso)
            if accion == "view":
                grupos["SUPERVISOR"].permissions.add(permiso)
    grupos["ADMINISTRADOR_GENERAL"].permissions.add(*permisos_personal)


def eliminar_roles_base(apps, schema_editor):
    RolPersonal = apps.get_model("personal", "RolPersonal")
    RolPersonal.objects.using(schema_editor.connection.alias).filter(
        codigo__in=[codigo for codigo, _nombre, _orden in ROLES]
    ).delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Cargo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True)),
                ("nombre", models.CharField(max_length=120)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("actualizado", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Cargo", "verbose_name_plural": "Cargos", "ordering": ["nombre"]},
        ),
        migrations.CreateModel(
            name="RolPersonal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True)),
                ("nombre", models.CharField(max_length=100)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True)),
                ("orden", models.PositiveIntegerField(default=0)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("actualizado", models.DateTimeField(auto_now=True)),
                ("grupo", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="rol_personal", to="auth.group")),
            ],
            options={"verbose_name": "Rol de personal", "verbose_name_plural": "Roles de personal", "ordering": ["orden", "nombre"]},
        ),
        migrations.CreateModel(
            name="Empleado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legajo", models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ("documento", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("fecha_ingreso", models.DateField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
                ("observaciones", models.TextField(blank=True, default="")),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("actualizado", models.DateTimeField(auto_now=True)),
                ("cargo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="empleados", to="personal.cargo")),
                ("rol", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="empleados", to="personal.rolpersonal")),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="empleado", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Empleado",
                "verbose_name_plural": "Empleados",
                "ordering": ["usuario__last_name", "usuario__first_name", "usuario__username"],
                "permissions": [("access_admin_frontend", "Puede acceder al frontend administrativo")],
            },
        ),
        migrations.RunPython(crear_roles_base, eliminar_roles_base),
    ]
