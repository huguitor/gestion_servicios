import os
import re
import zipfile
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from rest_framework.exceptions import ValidationError


SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF"}
MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 80


def validar_seleccion_fotografica(
    *,
    adjuntos,
    requested_ids,
    parent_id,
    parent_field,
    parent_label,
    max_images,
    max_total_bytes,
):
    if not requested_ids:
        raise ValidationError({"adjunto_ids": "Seleccioná al menos una imagen."})
    if len(requested_ids) > max_images:
        raise ValidationError(
            {"adjunto_ids": f"Se permiten como máximo {max_images} imágenes."}
        )
    if len(set(requested_ids)) != len(requested_ids):
        raise ValidationError({"adjunto_ids": "No se permiten IDs duplicados."})

    por_id = {adjunto.id: adjunto for adjunto in adjuntos}
    if any(adjunto_id not in por_id for adjunto_id in requested_ids):
        raise ValidationError(
            {
                "adjunto_ids": (
                    f"Uno o más adjuntos no pertenecen al {parent_label} indicado."
                )
            }
        )
    seleccionados = [por_id[adjunto_id] for adjunto_id in requested_ids]
    total = 0
    for adjunto in seleccionados:
        if getattr(adjunto, parent_field) != parent_id:
            raise ValidationError(
                {
                    "adjunto_ids": (
                        f"Uno o más adjuntos no pertenecen al {parent_label} indicado."
                    )
                }
            )
        try:
            total += adjunto.archivo.size
        except (FileNotFoundError, OSError):
            raise ValidationError(
                {"adjunto_ids": f"No se pudo leer {adjunto.nombre_original}."}
            )
    if total > max_total_bytes:
        megabytes = max_total_bytes // (1024 * 1024)
        raise ValidationError(
            {"adjunto_ids": f"La selección supera el límite total de {megabytes} MB."}
        )

    for adjunto in seleccionados:
        try:
            with adjunto.archivo.open("rb") as archivo:
                with Image.open(archivo) as imagen:
                    imagen.verify()
                    if imagen.format not in SUPPORTED_FORMATS:
                        raise ValidationError(
                            {
                                "adjunto_ids": (
                                    f"{adjunto.nombre_original} no es una imagen compatible."
                                )
                            }
                        )
        except (UnidentifiedImageError, OSError):
            raise ValidationError(
                {"adjunto_ids": f"{adjunto.nombre_original} no es una imagen válida."}
            )
    return seleccionados


def generar_pdf_registro(
    *,
    adjuntos,
    document_title,
    document_label,
    document_number,
    client_label,
    date_label,
):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    page_width, page_height = A4
    pdf.setTitle(f"Registro fotográfico {document_title} {document_number}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(page_width / 2, page_height - 90, "REGISTRO FOTOGRÁFICO")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(70, page_height - 145, f"{document_label}: {document_number}")
    pdf.drawString(70, page_height - 170, f"Cliente: {client_label}")
    pdf.drawString(70, page_height - 195, f"Fecha: {date_label}")
    pdf.drawString(70, page_height - 220, f"Cantidad de fotografías: {len(adjuntos)}")
    _draw_page_number(pdf, 1, page_width)
    pdf.showPage()

    for index, adjunto in enumerate(adjuntos, start=1):
        image_bytes, image_width, image_height = _optimized_image(adjunto)
        max_width = page_width - 70
        max_height = page_height - 130
        scale = min(max_width / image_width, max_height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        pdf.drawImage(
            ImageReader(image_bytes),
            (page_width - draw_width) / 2,
            75 + (max_height - draw_height) / 2,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
        )
        pdf.setFont("Helvetica", 9)
        label = f"Foto {index} de {len(adjuntos)} · {adjunto.nombre_original}"
        pdf.drawCentredString(page_width / 2, 48, label[:110])
        _draw_page_number(pdf, index + 1, page_width)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def generar_zip_originales(*, adjuntos):
    output = BytesIO()
    used_names = set()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for adjunto in adjuntos:
            name = _unique_safe_name(adjunto.nombre_original, used_names)
            with adjunto.archivo.open("rb") as source:
                archive.writestr(name, source.read())
    return output.getvalue()


def nombre_archivo_paquete(*, prefix, document_number, fallback_id, extension):
    safe_number = re.sub(
        r"[^A-Za-z0-9_-]+", "_", document_number
    ).strip("_")
    return f"{prefix}_{safe_number or fallback_id}.{extension}"


def _optimized_image(adjunto):
    with adjunto.archivo.open("rb") as source:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            if getattr(image, "is_animated", False):
                image.seek(0)
            image = image.convert("RGB")
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            width, height = image.size
            output = BytesIO()
            image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            output.seek(0)
            return output, width, height


def _unique_safe_name(original_name, used_names):
    basename = os.path.basename(original_name or "imagen")
    basename = re.sub(r"[^A-Za-z0-9._ -]+", "_", basename).strip(" .") or "imagen"
    stem, extension = os.path.splitext(basename)
    candidate = basename
    suffix = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem}_{suffix}{extension}"
        suffix += 1
    used_names.add(candidate.casefold())
    return candidate


def _draw_page_number(pdf, number, page_width):
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(page_width - 35, 25, f"Página {number}")
