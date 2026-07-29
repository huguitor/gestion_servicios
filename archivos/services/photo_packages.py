import os
import re
import zipfile
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from rest_framework.exceptions import ValidationError

from configuracion.services import ConfiguracionService


SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF"}
MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 80
BRAND_COLOR = colors.HexColor("#1E3A8A")
TEXT_COLOR = colors.HexColor("#1E293B")
MUTED_COLOR = colors.HexColor("#64748B")
LINE_COLOR = colors.HexColor("#CBD5E1")


def etiqueta_cliente(cliente):
    nombre = getattr(cliente, "nombre", "") or ""
    apellido = getattr(cliente, "apellido", "") or ""
    return f"{nombre} {apellido}".strip() or str(cliente)


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
    client_tax_id,
    date_label,
):
    company = _company_identity()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    page_width, page_height = A4
    total_photos = len(adjuntos)
    total_pages = max(total_photos, 1)
    pdf.setTitle(f"Registro fotográfico {document_title} {document_number}")
    _draw_cover(
        pdf,
        company=company,
        document_label=document_label,
        document_number=document_number,
        client_label=client_label,
        client_tax_id=client_tax_id,
        date_label=date_label,
        photo_count=total_photos,
        page_width=page_width,
        page_height=page_height,
    )

    if adjuntos:
        _draw_fitted_photo(
            pdf,
            adjunto=adjuntos[0],
            frame_x=30,
            frame_y=72,
            frame_width=page_width - 60,
            frame_height=page_height - 470,
        )
        _draw_photo_footer(
            pdf,
            index=1,
            total=total_photos,
            filename=_photo_caption(adjuntos[0]),
            page_number=1,
            total_pages=total_pages,
            page_width=page_width,
        )
    else:
        _draw_page_footer(pdf, page_number=1, total_pages=1, page_width=page_width)
    pdf.showPage()

    for index, adjunto in enumerate(adjuntos[1:], start=2):
        _draw_photo_header(
            pdf,
            company=company,
            document_label=document_label,
            document_number=document_number,
            page_width=page_width,
            page_height=page_height,
        )
        _draw_fitted_photo(
            pdf,
            adjunto=adjunto,
            frame_x=30,
            frame_y=72,
            frame_width=page_width - 60,
            frame_height=page_height - 142,
        )
        _draw_photo_footer(
            pdf,
            index=index,
            total=total_photos,
            filename=_photo_caption(adjunto),
            page_number=index,
            total_pages=total_pages,
            page_width=page_width,
        )
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


def _draw_fitted_photo(
    pdf,
    *,
    adjunto,
    frame_x,
    frame_y,
    frame_width,
    frame_height,
):
    image_bytes, image_width, image_height = _optimized_image(adjunto)
    padding = 5
    max_width = frame_width - (padding * 2)
    max_height = frame_height - (padding * 2)
    scale = min(max_width / image_width, max_height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    draw_x = frame_x + (frame_width - draw_width) / 2
    draw_y = frame_y + (frame_height - draw_height) / 2

    pdf.setStrokeColor(LINE_COLOR)
    pdf.setLineWidth(0.7)
    pdf.rect(frame_x, frame_y, frame_width, frame_height, fill=0, stroke=1)
    pdf.drawImage(
        ImageReader(image_bytes),
        draw_x,
        draw_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
    )


def _photo_caption(adjunto):
    return (
        getattr(adjunto, "descripcion", "")
        or getattr(adjunto, "nombre_original", "")
        or "imagen"
    )


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


def _company_identity():
    try:
        return ConfiguracionService.obtener_identidad_pdf()
    except Exception:
        return {
            "nombre_empresa": "",
            "cuit": "",
            "direccion": "",
            "telefono": "",
            "email": "",
            "pagina_web": "",
            "logo_path": None,
        }


def _draw_logo(pdf, company, x, y, width=82, height=42):
    logo_path = company.get("logo_path")
    if not logo_path:
        return
    try:
        pdf.drawImage(
            logo_path,
            x,
            y,
            width=width,
            height=height,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )
    except Exception:
        return


def _draw_cover(
    pdf,
    *,
    company,
    document_label,
    document_number,
    client_label,
    client_tax_id,
    date_label,
    photo_count,
    page_width,
    page_height,
):
    margin = 48
    _draw_logo(pdf, company, margin, page_height - 88)

    company_name = company.get("nombre_empresa") or ""
    pdf.setFillColor(TEXT_COLOR)
    pdf.setFont("Helvetica-Bold", 11)
    if company_name:
        pdf.drawRightString(page_width - margin, page_height - 53, company_name)
    pdf.setFillColor(MUTED_COLOR)
    pdf.setFont("Helvetica", 8)
    company_tax_id = company.get("cuit") or ""
    if company_tax_id:
        pdf.drawRightString(
            page_width - margin,
            page_height - 68,
            f"CUIT: {company_tax_id}",
        )

    pdf.setStrokeColor(BRAND_COLOR)
    pdf.setLineWidth(1.5)
    pdf.line(margin, page_height - 108, page_width - margin, page_height - 108)

    pdf.setFillColor(BRAND_COLOR)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 185,
        "REGISTRO FOTOGRÁFICO",
    )
    pdf.setFillColor(TEXT_COLOR)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 218,
        f"{document_label.upper()} · {document_number}",
    )

    box_x = 72
    box_y = page_height - 390
    box_width = page_width - 144
    box_height = 115
    pdf.setFillColor(colors.HexColor("#F8FAFC"))
    pdf.setStrokeColor(LINE_COLOR)
    pdf.roundRect(box_x, box_y, box_width, box_height, 5, fill=1, stroke=1)
    rows = [
        ("Cliente", client_label or "No especificado"),
        ("CUIT", client_tax_id or "No especificado"),
        ("Fecha", date_label or "No especificada"),
        ("Fotografías", str(photo_count)),
    ]
    label_x = box_x + 22
    value_x = box_x + 120
    row_y = box_y + box_height - 27
    for label, value in rows:
        pdf.setFillColor(MUTED_COLOR)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(label_x, row_y, f"{label}:")
        pdf.setFillColor(TEXT_COLOR)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(value_x, row_y, _fit_text(pdf, value, box_width - 145, 10))
        row_y -= 25


def _draw_photo_header(
    pdf,
    *,
    company,
    document_label,
    document_number,
    page_width,
    page_height,
):
    margin = 30
    _draw_logo(pdf, company, margin, page_height - 54, width=56, height=28)
    pdf.setFillColor(TEXT_COLOR)
    pdf.setFont("Helvetica-Bold", 9)
    reference = f"{document_label} · {document_number}"
    pdf.drawRightString(page_width - margin, page_height - 38, reference)
    pdf.setStrokeColor(BRAND_COLOR)
    pdf.setLineWidth(0.8)
    pdf.line(margin, page_height - 61, page_width - margin, page_height - 61)


def _draw_photo_footer(
    pdf,
    *,
    index,
    total,
    filename,
    page_number,
    total_pages,
    page_width,
):
    margin = 30
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setLineWidth(0.5)
    pdf.line(margin, 59, page_width - margin, 59)
    pdf.setFillColor(TEXT_COLOR)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margin, 43, f"Foto {index} de {total}")
    pdf.setFillColor(MUTED_COLOR)
    pdf.setFont("Helvetica", 8)
    safe_name = os.path.basename(filename or "imagen")
    available = page_width - 220
    pdf.drawCentredString(
        page_width / 2,
        43,
        _fit_text(pdf, safe_name, available, 8),
    )
    pdf.drawRightString(
        page_width - margin,
        43,
        f"Página {page_number} de {total_pages}",
    )


def _draw_page_footer(pdf, *, page_number, total_pages, page_width):
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setLineWidth(0.5)
    pdf.line(48, 48, page_width - 48, 48)
    pdf.setFillColor(MUTED_COLOR)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(
        page_width - 48,
        31,
        f"Página {page_number} de {total_pages}",
    )


def _fit_text(pdf, text, max_width, font_size):
    value = str(text or "")
    if pdf.stringWidth(value, "Helvetica", font_size) <= max_width:
        return value
    suffix = "..."
    while value and pdf.stringWidth(
        value + suffix,
        "Helvetica",
        font_size,
    ) > max_width:
        value = value[:-1]
    return value + suffix
