import os
import re
import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from archivos.services import photo_packages
from archivos.services.photo_packages import generar_pdf_registro
from configuracion.models import ConfiguracionGlobal
from configuracion.services import ConfiguracionService


class PhotoPackageDesignTests(TestCase):
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

    def _image(self, name, size):
        output = BytesIO()
        Image.new("RGB", size, color=(35, 90, 150)).save(output, format="JPEG")
        return SimpleNamespace(
            nombre_original=name,
            archivo=SimpleUploadedFile(name, output.getvalue()),
        )

    def _generate(self, adjuntos):
        identity = {
            "nombre_empresa": "",
            "cuit": "",
            "direccion": "",
            "telefono": "",
            "email": "",
            "pagina_web": "",
            "logo_path": None,
        }
        with patch(
            "archivos.services.photo_packages._company_identity",
            return_value=identity,
        ):
            return generar_pdf_registro(
                adjuntos=adjuntos,
                document_title="Presupuesto",
                document_label="Presupuesto",
                document_number="00002-000245",
                client_label="Cliente de prueba",
                client_tax_id="",
                date_label="28/07/2026",
            )

    def _page_count(self, content):
        return len(re.findall(rb"/Type\s*/Page\b", content))

    def _assert_all_pages_are_portrait(self, content):
        media_boxes = re.findall(
            rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]",
            content,
        )
        self.assertTrue(media_boxes)
        self.assertTrue(
            all(float(width) < float(height) for width, height in media_boxes)
        )

    def test_identidad_pdf_resuelve_logo_y_datos_de_configuracion(self):
        logo = BytesIO()
        Image.new("RGB", (160, 80), color=(20, 60, 120)).save(
            logo,
            format="PNG",
        )
        config = ConfiguracionGlobal.objects.create(
            nombre_empresa="Empresa Fotográfica",
            cuit="30-12345678-9",
            logo_principal=SimpleUploadedFile(
                "logo.png",
                logo.getvalue(),
                content_type="image/png",
            ),
        )

        identity = ConfiguracionService.obtener_identidad_pdf()

        self.assertEqual(identity["nombre_empresa"], "Empresa Fotográfica")
        self.assertEqual(identity["cuit"], "30-12345678-9")
        self.assertEqual(identity["logo_path"], config.logo_principal.path)
        self.assertTrue(os.path.exists(identity["logo_path"]))

    def test_una_foto_genera_una_pagina_e_integra_foto_en_portada(self):
        first = self._image("IMG_0255_horizontal.jpg", (160, 80))

        with patch(
            "archivos.services.photo_packages._draw_fitted_photo",
            wraps=photo_packages._draw_fitted_photo,
        ) as draw_photo, patch(
            "archivos.services.photo_packages._draw_photo_footer",
            wraps=photo_packages._draw_photo_footer,
        ) as draw_footer:
            content = self._generate([first])

        self.assertTrue(content.startswith(b"%PDF"))
        self.assertEqual(self._page_count(content), 1)
        self._assert_all_pages_are_portrait(content)
        self.assertEqual(draw_photo.call_count, 1)
        self.assertIs(draw_photo.call_args.kwargs["adjunto"], first)
        self.assertEqual(draw_footer.call_args.kwargs["index"], 1)
        self.assertEqual(draw_footer.call_args.kwargs["page_number"], 1)
        self.assertEqual(draw_footer.call_args.kwargs["total_pages"], 1)

    def test_varias_fotos_generan_una_pagina_por_foto_todas_verticales(self):
        adjuntos = [
            self._image("IMG_0255_vertical.jpg", (80, 160)),
            self._image("IMG_0256_horizontal.jpg", (160, 80)),
            self._image("IMG_0257_horizontal.jpg", (200, 90)),
        ]

        with patch(
            "archivos.services.photo_packages._draw_fitted_photo",
            wraps=photo_packages._draw_fitted_photo,
        ) as draw_photo, patch(
            "archivos.services.photo_packages._draw_photo_footer",
            wraps=photo_packages._draw_photo_footer,
        ) as draw_footer:
            content = self._generate(adjuntos)

        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 2_000)
        self.assertEqual(self._page_count(content), 3)
        self._assert_all_pages_are_portrait(content)
        self.assertEqual(draw_photo.call_count, 3)
        self.assertEqual(
            [call.kwargs["page_number"] for call in draw_footer.call_args_list],
            [1, 2, 3],
        )
        self.assertTrue(
            all(
                call.kwargs["total_pages"] == 3
                for call in draw_footer.call_args_list
            )
        )
