import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from clientes.models import Cliente
from comprobantes.models import Comprobante
from .models import Remito, RemitoAdjunto


class RemitoAdjuntoUploadTests(APITestCase):
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
            username='admin-remitos',
            password='test-password',
            is_staff=True,
        )
        self.cliente = Cliente.objects.create(
            tipo='juridica',
            nombre='Cliente de prueba',
        )
        self.comprobante = Comprobante.objects.create(
            tipo='REMI',
            serie='00001',
            numero_inicial=1,
            numero_final=999999,
            proximo_numero=1,
        )
        self.remito = Remito.objects.create(
            comprobante=self.comprobante,
            cliente=self.cliente,
            creado_por=self.usuario,
        )
        self.client.force_authenticate(self.usuario)

    def test_subir_adjunto_asigna_remito_desde_url(self):
        archivo = SimpleUploadedFile(
            'entrega.pdf',
            b'%PDF-1.4 contenido de prueba',
            content_type='application/pdf',
        )

        response = self.client.post(
            f'/api/remitos/{self.remito.pk}/adjuntos/',
            {
                'archivo': archivo,
                'tipo': 'entrega',
                'descripcion': 'Comprobante firmado',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        adjunto = RemitoAdjunto.objects.get()
        self.assertEqual(adjunto.remito, self.remito)
        self.assertEqual(adjunto.tipo, 'entrega')
        self.assertEqual(adjunto.descripcion, 'Comprobante firmado')

        listado_response = self.client.get(
            f'/api/remitos/{self.remito.pk}/adjuntos/',
        )

        self.assertEqual(listado_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            listado_response.data[0]['url_descarga'],
            f'http://testserver{adjunto.archivo.url}',
        )


class RemitoClienteFilterTests(APITestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='admin-remitos-filtros',
            password='test-password',
            is_staff=True,
        )
        self.client.force_authenticate(self.usuario)
        self.cliente_uno = Cliente.objects.create(
            tipo='juridica',
            nombre='Cliente Uno',
        )
        self.cliente_dos = Cliente.objects.create(
            tipo='juridica',
            nombre='Cliente Dos',
        )
        self.comprobante = Comprobante.objects.create(
            tipo='REMI',
            serie='00001',
            numero_inicial=1,
            numero_final=999999,
            proximo_numero=1,
        )
        self.remito_uno_pendiente = self._crear_remito(
            self.cliente_uno,
            'pendiente',
        )
        self.remito_uno_entregado = self._crear_remito(
            self.cliente_uno,
            'entregado',
        )
        self.remito_dos = self._crear_remito(
            self.cliente_dos,
            'pendiente',
        )

    def _crear_remito(self, cliente, estado):
        return Remito.objects.create(
            comprobante=self.comprobante,
            cliente=cliente,
            creado_por=self.usuario,
            estado=estado,
        )

    @staticmethod
    def _ids(response):
        return {row['id'] for row in response.data}

    def test_filtra_remitos_por_id_de_cliente(self):
        response = self.client.get(
            '/api/remitos/',
            {'cliente': self.cliente_uno.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            self._ids(response),
            {
                self.remito_uno_pendiente.id,
                self.remito_uno_entregado.id,
            },
        )

    def test_no_devuelve_remitos_de_otro_cliente(self):
        response = self.client.get(
            '/api/remitos/',
            {'cliente': self.cliente_uno.id},
        )

        self.assertNotIn(self.remito_dos.id, self._ids(response))

    def test_sin_cliente_mantiene_el_listado_completo(self):
        response = self.client.get('/api/remitos/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            self._ids(response),
            {
                self.remito_uno_pendiente.id,
                self.remito_uno_entregado.id,
                self.remito_dos.id,
            },
        )

    def test_cliente_inexistente_devuelve_lista_vacia(self):
        response = self.client.get(
            '/api/remitos/',
            {'cliente': 999999},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_combina_cliente_con_estado(self):
        response = self.client.get(
            '/api/remitos/',
            {
                'cliente': self.cliente_uno.id,
                'estado': 'pendiente',
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            self._ids(response),
            {self.remito_uno_pendiente.id},
        )
