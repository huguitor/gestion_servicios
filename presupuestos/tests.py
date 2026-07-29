import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from clientes.models import Cliente
from comprobantes.models import Comprobante
from presupuestos.models import Presupuesto, PresupuestoAdjunto
from presupuestos.serializers import PresupuestoAdjuntoSerializer


class PresupuestoPhotoPackagesTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp()
        cls._override_media = override_settings(MEDIA_ROOT=cls._media_root)
        cls._override_media.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override_media.disable()
        shutil.rmtree(cls._media_root)

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            "admin-presupuestos-fotos", is_staff=True
        )
        self.cliente = Cliente.objects.create(
            tipo="juridica", nombre="Cliente Presupuesto"
        )
        self.comprobante = Comprobante.objects.create(
            tipo="PRES",
            serie="00002",
            numero_inicial=1,
            numero_final=999999,
            proximo_numero=245,
        )
        self.presupuesto = Presupuesto.objects.create(
            cliente=self.cliente,
            comprobante=self.comprobante,
            creado_por=self.usuario,
        )
        self.client.force_authenticate(self.usuario)

    def _image_file(self, name="IMG_0255.jpg", size=(80, 120), orientation=None):
        output = BytesIO()
        image = Image.new("RGB", size, color=(80, 140, 200))
        exif = Image.Exif()
        if orientation:
            exif[274] = orientation
        image.save(output, format="JPEG", exif=exif)
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/jpeg")

    def _adjunto(self, name="IMG_0255.jpg", presupuesto=None, **image_kwargs):
        return PresupuestoAdjunto.objects.create(
            presupuesto=presupuesto or self.presupuesto,
            archivo=self._image_file(name, **image_kwargs),
            tipo="foto",
            nombre_original=name,
            tamaño=0,
            extension="",
            subido_por=self.usuario,
        )

    def _url(self, extension):
        return f"/api/presupuestos/{self.presupuesto.pk}/adjuntos/{extension}/"

    def test_pdf_una_y_varias_imagenes_cabeceras_y_nombre(self):
        vertical = self._adjunto("IMG_0255.jpg", size=(80, 160))
        horizontal = self._adjunto("IMG_0256.jpg", size=(160, 80))
        una = self.client.post(
            self._url("pdf"), {"adjunto_ids": [vertical.id]}, format="json"
        )
        self.assertEqual(una.status_code, status.HTTP_200_OK)
        self.assertTrue(una.content.startswith(b"%PDF"))
        self.assertEqual(una["Content-Type"], "application/pdf")
        self.assertIn(
            'filename="Fotos_Presupuesto_00002-000245.pdf"',
            una["Content-Disposition"],
        )
        varias = self.client.post(
            self._url("pdf"),
            {"adjunto_ids": [vertical.id, horizontal.id]},
            format="json",
        )
        self.assertEqual(varias.status_code, status.HTTP_200_OK)
        self.assertGreater(len(varias.content), len(una.content))

    def test_pdf_respeta_orden_datos_exif_e_imagen_grande(self):
        exif = self._adjunto("telefono.jpg", size=(80, 160), orientation=6)
        grande = self._adjunto("grande.jpg", size=(3000, 1000))
        captured = {}

        def generar(*, presupuesto, adjuntos):
            captured["numero"] = presupuesto.numero
            captured["cliente"] = str(presupuesto.cliente)
            captured["fecha"] = presupuesto.fecha
            captured["ids"] = [adjunto.id for adjunto in adjuntos]
            return b"%PDF-1.4"

        with patch(
            "presupuestos.views.generar_pdf_fotografico", side_effect=generar
        ):
            response = self.client.post(
                self._url("pdf"),
                {"adjunto_ids": [grande.id, exif.id]},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(captured["ids"], [grande.id, exif.id])
        self.assertEqual(captured["numero"], 245)
        self.assertIn("Cliente Presupuesto", captured["cliente"])
        self.assertIsInstance(captured["fecha"], datetime)

        real = self.client.post(
            self._url("pdf"), {"adjunto_ids": [exif.id, grande.id]}, format="json"
        )
        self.assertEqual(real.status_code, status.HTTP_200_OK)
        self.assertTrue(real.content.startswith(b"%PDF"))

    def test_rechaza_vacia_duplicados_ajenos_no_imagen_e_inexistente(self):
        image = self._adjunto()
        self.assertEqual(
            self.client.post(
                self._url("pdf"), {"adjunto_ids": []}, format="json"
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                self._url("pdf"),
                {"adjunto_ids": [image.id, image.id]},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        other = Presupuesto.objects.create(
            cliente=self.cliente,
            comprobante=self.comprobante,
            creado_por=self.usuario,
        )
        foreign = self._adjunto("ajena.jpg", presupuesto=other)
        self.assertEqual(
            self.client.post(
                self._url("pdf"), {"adjunto_ids": [foreign.id]}, format="json"
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        document = PresupuestoAdjunto.objects.create(
            presupuesto=self.presupuesto,
            archivo=SimpleUploadedFile("plano.pdf", b"%PDF-1.4"),
            tipo="plano",
            nombre_original="plano.pdf",
            tamaño=8,
            extension="pdf",
            subido_por=self.usuario,
        )
        self.assertEqual(
            self.client.post(
                self._url("pdf"), {"adjunto_ids": [document.id]}, format="json"
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                "/api/presupuestos/999999/adjuntos/pdf/",
                {"adjunto_ids": [image.id]},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_permisos_licencia_y_limites(self):
        image = self._adjunto()
        no_staff = get_user_model().objects.create_user("sin-acceso-presupuesto")
        self.client.force_authenticate(no_staff)
        self.assertEqual(
            self.client.post(
                self._url("pdf"), {"adjunto_ids": [image.id]}, format="json"
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.usuario)
        with patch(
            "licensing.decorators.license_manager.is_enabled", return_value=False
        ):
            disabled = self.client.post(
                self._url("pdf"), {"adjunto_ids": [image.id]}, format="json"
            )
        self.assertEqual(disabled.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(
                self._url("pdf"),
                {"adjunto_ids": list(range(1, 32))},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        with patch("presupuestos.photo_packages.MAX_TOTAL_BYTES", 1):
            heavy = self.client.post(
                self._url("pdf"), {"adjunto_ids": [image.id]}, format="json"
            )
        self.assertEqual(heavy.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zip_originales_orden_nombres_repetidos_y_sin_derivados(self):
        bytes_one = self._image_file().read()
        bytes_two = self._image_file(size=(40, 40)).read()
        first = PresupuestoAdjunto.objects.create(
            presupuesto=self.presupuesto,
            archivo=SimpleUploadedFile("one.jpg", bytes_one),
            tipo="foto",
            nombre_original="IMG_0255.jpg",
            tamaño=len(bytes_one),
            extension="jpg",
            subido_por=self.usuario,
        )
        second = PresupuestoAdjunto.objects.create(
            presupuesto=self.presupuesto,
            archivo=SimpleUploadedFile("two.jpg", bytes_two),
            tipo="foto",
            nombre_original="IMG_0255.jpg",
            tamaño=len(bytes_two),
            extension="jpg",
            subido_por=self.usuario,
        )
        before = set(os.listdir(self._media_root))
        response = self.client.post(
            self._url("zip"),
            {"adjunto_ids": [second.id, first.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("Fotos_Presupuesto_00002-000245.zip", response["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(archive.namelist(), ["IMG_0255.jpg", "IMG_0255_2.jpg"])
            self.assertEqual(archive.read("IMG_0255.jpg"), bytes_two)
            self.assertEqual(archive.read("IMG_0255_2.jpg"), bytes_one)
        self.assertEqual(set(os.listdir(self._media_root)), before)

    def test_adjunto_historico_sin_metadata_funciona(self):
        image = self._adjunto("historica.jpg")
        PresupuestoAdjunto.objects.filter(pk=image.pk).update(extension="", tamaño=0)
        response = self.client.post(
            self._url("zip"), {"adjunto_ids": [image.id]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_url_descarga_absoluta_y_fallback_sin_request(self):
        image = self._adjunto("IMG_0182.jpg")

        response = self.client.get(
            f"/api/presupuestos/{self.presupuesto.pk}/adjuntos/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = (
            response.data
            if isinstance(response.data, list)
            else response.data["results"]
        )
        self.assertEqual(
            rows[0]["url_descarga"],
            f"http://testserver{image.archivo.url}",
        )

        serialized = PresupuestoAdjuntoSerializer(image).data
        self.assertEqual(serialized["url_descarga"], image.archivo.url)
