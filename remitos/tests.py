import os
import shutil
import tempfile
import zipfile
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

    def _imagen(self, nombre='IMG_0255.jpg', size=(80, 120), orientation=None):
        output = BytesIO()
        image = Image.new('RGB', size, color=(40, 120, 180))
        exif = Image.Exif()
        if orientation:
            exif[274] = orientation
        image.save(output, format='JPEG', exif=exif)
        return SimpleUploadedFile(
            nombre,
            output.getvalue(),
            content_type='image/jpeg',
        )

    def _adjunto(self, nombre='IMG_0255.jpg', **kwargs):
        return RemitoAdjunto.objects.create(
            remito=kwargs.pop('remito', self.remito),
            archivo=self._imagen(nombre, **kwargs),
            tipo='foto',
            nombre_original=nombre,
            subido_por=self.usuario,
        )

    def _url(self, formato):
        return f'/api/remitos/{self.remito.pk}/adjuntos/{formato}/'

    def test_pdf_fotografico_una_y_varias_imagenes(self):
        primera = self._adjunto('IMG_0255.jpg', size=(60, 120))
        segunda = self._adjunto('IMG_0256.jpg', size=(160, 70))
        una = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [primera.id]},
            format='json',
        )
        self.assertEqual(una.status_code, status.HTTP_200_OK)
        self.assertTrue(una.content.startswith(b'%PDF'))
        self.assertEqual(una['Content-Type'], 'application/pdf')
        self.assertIn(
            f'Fotos_Remito_{self.remito.numero_formateado}.pdf',
            una['Content-Disposition'],
        )

        varias = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [primera.id, segunda.id]},
            format='json',
        )
        self.assertEqual(varias.status_code, status.HTTP_200_OK)
        self.assertGreater(len(varias.content), len(una.content))

    def test_pdf_respeta_orden_incluye_datos_y_soporta_exif_e_imagen_grande(self):
        primera = self._adjunto('vertical.jpg', size=(80, 160), orientation=6)
        segunda = self._adjunto('grande.jpg', size=(3000, 1000))
        capturados = {}

        def generar(*, remito, adjuntos):
            capturados['numero'] = remito.numero_formateado
            capturados['cliente'] = str(remito.cliente)
            capturados['ids'] = [adjunto.id for adjunto in adjuntos]
            return b'%PDF-1.4 prueba'

        with patch('remitos.views.generar_pdf_fotografico', side_effect=generar):
            response = self.client.post(
                self._url('pdf'),
                {'adjunto_ids': [segunda.id, primera.id]},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(capturados['ids'], [segunda.id, primera.id])
        self.assertEqual(capturados['numero'], self.remito.numero_formateado)
        self.assertIn('Cliente de prueba', capturados['cliente'])

        real = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [primera.id, segunda.id]},
            format='json',
        )
        self.assertEqual(real.status_code, status.HTTP_200_OK)
        self.assertTrue(real.content.startswith(b'%PDF'))

    def test_rechaza_lista_vacia_duplicados_ajenos_y_no_imagen(self):
        imagen = self._adjunto()
        vacia = self.client.post(self._url('pdf'), {'adjunto_ids': []}, format='json')
        self.assertEqual(vacia.status_code, status.HTTP_400_BAD_REQUEST)
        duplicada = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [imagen.id, imagen.id]},
            format='json',
        )
        self.assertEqual(duplicada.status_code, status.HTTP_400_BAD_REQUEST)

        otro = Remito.objects.create(
            comprobante=self.comprobante,
            cliente=self.cliente,
            creado_por=self.usuario,
        )
        ajeno = self._adjunto('ajeno.jpg', remito=otro)
        response_ajeno = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [ajeno.id]},
            format='json',
        )
        self.assertEqual(response_ajeno.status_code, status.HTTP_400_BAD_REQUEST)

        documento = RemitoAdjunto.objects.create(
            remito=self.remito,
            archivo=SimpleUploadedFile('informe.pdf', b'%PDF-1.4'),
            tipo='documento',
            nombre_original='informe.pdf',
            subido_por=self.usuario,
        )
        no_imagen = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': [documento.id]},
            format='json',
        )
        self.assertEqual(no_imagen.status_code, status.HTTP_400_BAD_REQUEST)

    def test_limites_cantidad_y_peso(self):
        demasiados = self.client.post(
            self._url('pdf'),
            {'adjunto_ids': list(range(1, 32))},
            format='json',
        )
        self.assertEqual(demasiados.status_code, status.HTTP_400_BAD_REQUEST)
        imagen = self._adjunto()
        with patch('remitos.photo_packages.MAX_TOTAL_BYTES', 1):
            pesada = self.client.post(
                self._url('pdf'),
                {'adjunto_ids': [imagen.id]},
                format='json',
            )
        self.assertEqual(pesada.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remito_inexistente_permiso_y_licencia(self):
        inexistente = self.client.post(
            '/api/remitos/999999/adjuntos/pdf/',
            {'adjunto_ids': [1]},
            format='json',
        )
        self.assertEqual(inexistente.status_code, status.HTTP_404_NOT_FOUND)

        imagen = self._adjunto()
        usuario = get_user_model().objects.create_user('sin-permiso-remitos')
        self.client.force_authenticate(usuario)
        self.assertEqual(
            self.client.post(
                self._url('pdf'),
                {'adjunto_ids': [imagen.id]},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.usuario)
        with patch(
            'licensing.decorators.license_manager.is_enabled',
            return_value=False,
        ):
            sin_licencia = self.client.post(
                self._url('pdf'),
                {'adjunto_ids': [imagen.id]},
                format='json',
            )
        self.assertEqual(sin_licencia.status_code, status.HTTP_403_FORBIDDEN)

    def test_zip_conserva_originales_y_resuelve_nombres_repetidos(self):
        original_uno = self._imagen('IMG_0255.jpg').read()
        original_dos = self._imagen('IMG_0255.jpg', size=(40, 40)).read()
        primero = RemitoAdjunto.objects.create(
            remito=self.remito,
            archivo=SimpleUploadedFile('uno.jpg', original_uno),
            tipo='foto',
            nombre_original='IMG_0255.jpg',
            subido_por=self.usuario,
        )
        segundo = RemitoAdjunto.objects.create(
            remito=self.remito,
            archivo=SimpleUploadedFile('dos.jpg', original_dos),
            tipo='foto',
            nombre_original='IMG_0255.jpg',
            subido_por=self.usuario,
        )
        before = set(
            path for path in os.listdir(self._media_root)
        )
        response = self.client.post(
            self._url('zip'),
            {'adjunto_ids': [primero.id, segundo.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('.zip', response['Content-Disposition'])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(
                archive.namelist(),
                ['IMG_0255.jpg', 'IMG_0255_2.jpg'],
            )
            self.assertEqual(archive.read('IMG_0255.jpg'), original_uno)
            self.assertEqual(archive.read('IMG_0255_2.jpg'), original_dos)
        self.assertEqual(set(os.listdir(self._media_root)), before)

    def test_adjunto_historico_sin_extension_sigue_funcionando(self):
        adjunto = self._adjunto('historica.jpg')
        RemitoAdjunto.objects.filter(pk=adjunto.pk).update(extension='', tamaño=0)
        response = self.client.post(
            self._url('zip'),
            {'adjunto_ids': [adjunto.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


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
