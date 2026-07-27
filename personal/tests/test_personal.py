from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from pedidos_internos.models import Sector, UsuarioSector
from personal.models import Cargo, Empleado, RolPersonal
from personal.services import asignar_rol


class PersonalModelTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("empleado")
        self.group = Group.objects.create(name="ROL_TEST")
        self.rol = RolPersonal.objects.create(codigo="TEST", nombre="Test", grupo=self.group)

    def test_empleado_vincula_user_y_normaliza_vacios(self):
        empleado = Empleado.objects.create(usuario=self.user, legajo="", documento="")
        self.assertEqual(self.user.empleado, empleado)
        self.assertIsNone(empleado.legajo)
        self.assertIsNone(empleado.documento)

    def test_legajo_y_documento_unicos_si_existen(self):
        Empleado.objects.create(usuario=self.user, legajo="A1", documento="123")
        otro = get_user_model().objects.create_user("otro")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Empleado.objects.create(usuario=otro, legajo="A1")

    def test_cargo_no_asigna_permisos(self):
        cargo = Cargo.objects.create(codigo="TEC", nombre="Técnico")
        Empleado.objects.create(usuario=self.user, cargo=cargo)
        self.assertEqual(self.user.groups.count(), 0)

    def test_empleado_puede_desactivarse(self):
        empleado = Empleado.objects.create(usuario=self.user, activo=True)
        empleado.activo = False
        empleado.save()
        self.assertFalse(empleado.activo)


class AsignarRolTests(APITestCase):
    def test_cambia_solo_grupo_de_rol_y_conserva_adicional(self):
        user = get_user_model().objects.create_user("roles")
        adicional = Group.objects.create(name="ADICIONAL")
        grupo_uno = Group.objects.create(name="UNO")
        grupo_dos = Group.objects.create(name="DOS")
        rol_uno = RolPersonal.objects.create(codigo="UNO", nombre="Uno", grupo=grupo_uno)
        rol_dos = RolPersonal.objects.create(codigo="DOS", nombre="Dos", grupo=grupo_dos)
        empleado = Empleado.objects.create(usuario=user)
        user.groups.add(adicional)
        asignar_rol(empleado=empleado, rol=rol_uno)
        asignar_rol(empleado=empleado, rol=rol_dos)
        asignar_rol(empleado=empleado, rol=rol_dos)
        self.assertSetEqual(set(user.groups.values_list("name", flat=True)), {"ADICIONAL", "DOS"})


class LoginPersonalTests(APITestCase):
    def setUp(self):
        self.password = "clave-segura-123"

    def login(self, user):
        return self.client.post(reverse("admin_login"), {"username": user.username, "password": self.password})

    @patch("personal.access.license_manager.is_enabled", return_value=True)
    def test_operario_no_staff_con_sector_accede_solo_operacion(self, _license):
        user = get_user_model().objects.create_user("juan", password=self.password)
        Empleado.objects.create(usuario=user)
        sector = Sector.objects.create(codigo="TALLER-L", nombre="Taller")
        UsuarioSector.objects.create(usuario=user, sector=sector)
        response = self.login(user)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["user"]["puede_acceder_administracion"])
        self.assertTrue(response.data["user"]["puede_acceder_pedidos_internos"])

    @patch("personal.access.license_manager.is_enabled", return_value=True)
    def test_administrativo_activo_staff_con_permiso(self, _license):
        user = get_user_model().objects.create_user("maria", password=self.password, is_staff=True)
        Empleado.objects.create(usuario=user)
        user.user_permissions.add(Permission.objects.get(codename="access_admin_frontend", content_type__app_label="personal"))
        response = self.login(user)
        self.assertTrue(response.data["user"]["puede_acceder_administracion"])

    @patch("personal.access.license_manager.is_enabled", return_value=True)
    def test_sin_empleado_no_tiene_operacion_y_staff_historico_conserva_admin(self, _license):
        user = get_user_model().objects.create_user("historico", password=self.password, is_staff=True)
        response = self.login(user)
        self.assertTrue(response.data["user"]["puede_acceder_administracion"])
        self.assertFalse(response.data["user"]["puede_acceder_pedidos_internos"])

    def test_empleado_inactivo_y_usuario_sin_accesos(self):
        user = get_user_model().objects.create_user("sin-acceso", password=self.password)
        Empleado.objects.create(usuario=user, activo=False)
        response = self.login(user)
        self.assertFalse(response.data["user"]["puede_acceder_administracion"])
        self.assertFalse(response.data["user"]["puede_acceder_pedidos_internos"])

    def test_usuario_inactivo_no_autentica(self):
        user = get_user_model().objects.create_user("inactivo", password=self.password, is_active=False)
        self.assertEqual(self.login(user).status_code, 400)


class PersonalAPITests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("rrhh", is_staff=True)
        Empleado.objects.create(usuario=self.admin)
        permissions = Permission.objects.filter(content_type__app_label="personal")
        self.admin.user_permissions.add(*permissions)
        self.client.force_authenticate(self.admin)

    def test_crud_empleado_y_sectores_desde_usuario_sector(self):
        user = get_user_model().objects.create_user("api-empleado")
        sector = Sector.objects.create(codigo="API-SEC", nombre="API Sector")
        UsuarioSector.objects.create(usuario=user, sector=sector, principal=True)
        response = self.client.post(reverse("personal-empleados-list"), {"usuario": user.pk, "legajo": "E-1", "activo": True}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sectores"][0]["codigo"], "API-SEC")
        self.assertEqual(self.client.delete(reverse("personal-empleados-detail", args=[response.data["id"]])).status_code, 405)

    def test_crear_empleado_actualiza_solo_datos_personales_del_usuario(self):
        user = get_user_model().objects.create_user(
            "olga@olga.com", first_name="O.", last_name="Kas", email="anterior@example.com",
            is_staff=True, is_active=True,
        )
        group = Group.objects.create(name="GRUPO_EXISTENTE")
        permission = Permission.objects.get(codename="view_empleado", content_type__app_label="personal")
        user.groups.add(group)
        user.user_permissions.add(permission)

        response = self.client.post(reverse("personal-empleados-list"), {
            "usuario": user.pk, "first_name": "Olga", "last_name": "Kass", "email": "olga@example.com",
        }, format="json")

        self.assertEqual(response.status_code, 201)
        user.refresh_from_db()
        self.assertEqual((user.username, user.first_name, user.last_name, user.email), ("olga@olga.com", "Olga", "Kass", "olga@example.com"))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertSetEqual(set(user.groups.all()), {group})
        self.assertSetEqual(set(user.user_permissions.all()), {permission})
        self.assertEqual(response.data["first_name"], "Olga")
        self.assertEqual(response.data["last_name"], "Kass")

    def test_patch_actualiza_datos_personales_sin_cambiar_usuario(self):
        user = get_user_model().objects.create_user("olga", first_name="Olga", last_name="Kas", email="olga@example.com")
        empleado = Empleado.objects.create(usuario=user, legajo="E-2")
        otro = get_user_model().objects.create_user("otro")

        response = self.client.patch(reverse("personal-empleados-detail", args=[empleado.pk]), {
            "last_name": "Kass", "email": "olga.kass@example.com",
        }, format="json")

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        empleado.refresh_from_db()
        self.assertEqual(user.last_name, "Kass")
        self.assertEqual(user.username, "olga")
        self.assertEqual(empleado.usuario_id, user.pk)
        invalid = self.client.patch(reverse("personal-empleados-detail", args=[empleado.pk]), {"usuario": otro.pk}, format="json")
        self.assertEqual(invalid.status_code, 400)
        empleado.refresh_from_db()
        self.assertEqual(empleado.usuario_id, user.pk)

    def test_email_invalido_no_modifica_user_ni_empleado(self):
        user = get_user_model().objects.create_user("email-test", first_name="Antes", email="antes@example.com")
        empleado = Empleado.objects.create(usuario=user, legajo="E-3")

        response = self.client.patch(reverse("personal-empleados-detail", args=[empleado.pk]), {
            "first_name": "Después", "email": "email-invalido", "legajo": "CAMBIADO",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        user.refresh_from_db()
        empleado.refresh_from_db()
        self.assertEqual(user.first_name, "Antes")
        self.assertEqual(user.email, "antes@example.com")
        self.assertEqual(empleado.legajo, "E-3")

    def test_informes_sin_sector_y_usuario_con_sector_sin_empleado(self):
        sin_sector = get_user_model().objects.create_user("sin-sector")
        Empleado.objects.create(usuario=sin_sector)
        con_sector = get_user_model().objects.create_user("sector-sin-perfil")
        sector = Sector.objects.create(codigo="INF-SEC", nombre="Informe")
        UsuarioSector.objects.create(usuario=con_sector, sector=sector)
        empleados = self.client.get(reverse("personal-empleados-list"), {"informe": "sin_sector"})
        usuarios = self.client.get(reverse("personal-usuarios-list"), {"con_sector_sin_empleado": 1})
        self.assertIn(sin_sector.pk, [item["usuario"] for item in empleados.data])
        self.assertIn(con_sector.pk, [item["id"] for item in usuarios.data])

    def test_sin_permisos_recibe_403(self):
        user = get_user_model().objects.create_user("prohibido", is_staff=True)
        Empleado.objects.create(usuario=user)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(reverse("personal-empleados-list")).status_code, 403)
