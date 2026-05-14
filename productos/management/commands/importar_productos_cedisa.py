import csv
import os
import re
from urllib.request import urlopen
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile

from productos.models import Producto


class Command(BaseCommand):
    help = "Importa productos desde un CSV generado por el scraping de Cedisa."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Ruta al archivo CSV de productos scrapeados."
        )
        parser.add_argument(
            "--actualizar",
            action="store_true",
            help="Si el producto ya existe, actualiza costo, precio, descripción e imagen."
        )
        parser.add_argument(
            "--publicar",
            action="store_true",
            help="Marca publicado_web=True al importar."
        )
        parser.add_argument(
            "--destacar",
            action="store_true",
            help="Marca destacado_web=True al importar."
        )
        parser.add_argument(
            "--home",
            action="store_true",
            help="Marca mostrar_en_home=True al importar."
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        actualizar = options["actualizar"]
        publicar = options["publicar"]
        destacar = options["destacar"]
        mostrar_en_home = options["home"]

        if not os.path.exists(csv_path):
            raise CommandError(f"No existe el archivo CSV: {csv_path}")

        creados = 0
        actualizados = 0
        omitidos = 0
        errores = 0

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, start=1):
                try:
                    producto_data = self._normalizar_fila(row)

                    if not producto_data["nombre"]:
                        self.stdout.write(
                            self.style.WARNING(f"[Fila {i}] Omitido: no tiene nombre válido.")
                        )
                        omitidos += 1
                        continue

                    producto = self._buscar_producto_existente(producto_data)

                    if producto:
                        if not actualizar:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"[Fila {i}] Ya existe, omitido: {producto.nombre}"
                                )
                            )
                            omitidos += 1
                            continue

                        producto.nombre = producto_data["nombre"]
                        producto.descripcion = producto_data["descripcion"]
                        producto.costo_compra = producto_data["costo_compra"]
                        producto.precio_venta = producto_data["precio_venta"]
                        producto.stock = producto_data["stock"]
                        producto.activo = True
                        producto.publicado_web = publicar
                        producto.destacado_web = destacar
                        producto.mostrar_en_home = mostrar_en_home
                        producto.descripcion_corta = producto_data["descripcion_corta"]
                        producto.save()

                        if producto_data["imagen_url"]:
                            self._guardar_imagen_si_corresponde(producto, producto_data["imagen_url"])

                        self.stdout.write(
                            self.style.SUCCESS(f"[Fila {i}] Actualizado: {producto.nombre}")
                        )
                        actualizados += 1
                    else:
                        producto = Producto.objects.create(
                            nombre=producto_data["nombre"],
                            descripcion=producto_data["descripcion"],
                            costo_compra=producto_data["costo_compra"],
                            precio_venta=producto_data["precio_venta"],
                            stock=producto_data["stock"],
                            activo=True,
                            publicado_web=publicar,
                            destacado_web=destacar,
                            mostrar_en_home=mostrar_en_home,
                            descripcion_corta=producto_data["descripcion_corta"],
                        )

                        if producto_data["imagen_url"]:
                            self._guardar_imagen_si_corresponde(producto, producto_data["imagen_url"])

                        self.stdout.write(
                            self.style.SUCCESS(f"[Fila {i}] Creado: {producto.nombre}")
                        )
                        creados += 1

                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f"[Fila {i}] Error: {e}")
                    )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== RESUMEN IMPORTACIÓN ==="))
        self.stdout.write(f"Creados: {creados}")
        self.stdout.write(f"Actualizados: {actualizados}")
        self.stdout.write(f"Omitidos: {omitidos}")
        self.stdout.write(f"Errores: {errores}")

    def _buscar_producto_existente(self, producto_data: dict):
        codigo = producto_data["codigo_importado"]
        nombre = producto_data["nombre"]

        if codigo:
            producto = Producto.objects.filter(nombre__icontains=codigo).first()
            if producto:
                return producto

        return Producto.objects.filter(nombre=nombre).first()

    def _normalizar_fila(self, row: dict) -> dict:
        codigo = self._limpiar(row.get("codigo", ""))
        descripcion = self._limpiar(row.get("descripcion", ""))
        precio_raw = self._limpiar(row.get("precio", ""))
        imagen_url = self._limpiar(row.get("imagen", ""))
        ubicacion = self._limpiar(row.get("ubicacion", ""))
        rubro = self._limpiar(row.get("rubro", ""))
        texto_original = self._limpiar(row.get("texto_original", ""))
        marca = self._limpiar(row.get("marca", ""))
        stock_raw = self._limpiar(row.get("stock", ""))

        nombre = self._construir_nombre(codigo, descripcion)
        costo_compra = self._parsear_precio(precio_raw)
        precio_venta = self._calcular_precio_venta(costo_compra)
        stock = self._parsear_stock(stock_raw)

        descripcion_larga = self._construir_descripcion(
            codigo=codigo,
            descripcion=descripcion,
            marca=marca,
            ubicacion=ubicacion,
            rubro=rubro,
            texto_original=texto_original,
        )

        descripcion_corta = descripcion[:255] if descripcion else nombre[:255]

        return {
            "codigo_importado": codigo,
            "nombre": nombre[:200],
            "descripcion": descripcion_larga,
            "costo_compra": costo_compra,
            "precio_venta": precio_venta,
            "stock": stock,
            "imagen_url": imagen_url,
            "descripcion_corta": descripcion_corta,
        }

    def _construir_nombre(self, codigo: str, descripcion: str) -> str:
        if codigo and descripcion:
            nombre = f"{codigo} - {descripcion}"
        elif descripcion:
            nombre = descripcion
        elif codigo:
            nombre = codigo
        else:
            nombre = ""

        nombre = re.sub(r"\s+", " ", nombre).strip()
        return nombre[:200]

    def _construir_descripcion(self, codigo, descripcion, marca, ubicacion, rubro, texto_original):
        partes = []

        if descripcion:
            partes.append(descripcion)

        meta = []
        if codigo:
            meta.append(f"Código importado: {codigo}")
        if marca:
            meta.append(f"Marca importada: {marca}")
        if ubicacion:
            meta.append(f"Ubicación importada: {ubicacion}")
        if rubro:
            meta.append(f"Rubro importado: {rubro}")

        if meta:
            partes.append("\n".join(meta))

        if texto_original:
            partes.append(f"Texto original scraping:\n{texto_original}")

        return "\n\n".join(partes).strip()

    def _parsear_precio(self, valor: str) -> Decimal:
        if not valor:
            return Decimal("0.00")

        limpio = valor.replace("$", "").replace(" ", "").strip()

        if "," in limpio and "." in limpio:
            limpio = limpio.replace(",", "")
        else:
            limpio = limpio.replace(",", ".")

        try:
            return Decimal(limpio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    def _calcular_precio_venta(self, costo_compra: Decimal) -> Decimal:
        return (costo_compra * Decimal("1.40")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    def _parsear_stock(self, valor: str) -> int:
        if not valor:
            return 0

        valor_lower = valor.lower()

        if "no hay stock" in valor_lower:
            return 0

        m = re.search(r"(\d+)", valor_lower)
        if m:
            return int(m.group(1))

        return 0

    def _guardar_imagen_si_corresponde(self, producto: Producto, imagen_url: str):
        if not imagen_url:
            return

        url_lower = imagen_url.lower()

        if "no-image" in url_lower or "placeholder" in url_lower:
            return

        try:
            with urlopen(imagen_url, timeout=20) as response:
                content = response.read()
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"No se pudo descargar imagen para {producto.nombre}: {e}")
            )
            return

        extension = self._obtener_extension_desde_url(imagen_url)
        nombre_archivo = self._nombre_archivo_imagen(producto, extension)

        producto.foto.save(
            nombre_archivo,
            ContentFile(content),
            save=True
        )

    def _nombre_archivo_imagen(self, producto: Producto, extension: str) -> str:
        base = self._slug_basico(producto.nombre)[:120] or f"producto-{producto.id}"
        return f"{base}{extension}"

    def _obtener_extension_desde_url(self, url: str) -> str:
        url = url.lower().split("?")[0]
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            if url.endswith(ext):
                return ext
        return ".jpg"

    def _slug_basico(self, texto: str) -> str:
        texto = texto.lower().strip()
        texto = re.sub(r"[^a-z0-9áéíóúñü]+", "-", texto, flags=re.IGNORECASE)
        texto = re.sub(r"-+", "-", texto).strip("-")
        return texto

    def _limpiar(self, valor):
        if valor is None:
            return ""
        return re.sub(r"\s+", " ", str(valor)).strip()
