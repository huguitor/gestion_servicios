# gestion/backend/pedidos/pdf_generator.py

import io
import os
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from configuracion.services import ConfiguracionService


def _styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="PedidoTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.navy,
        )
    )

    return styles


def _empresa_info():
    try:
        datos = ConfiguracionService.obtener_datos_empresa()
    except Exception:
        datos = {}

    return {
        "nombre_empresa": datos.get("nombre_empresa") or "Mi Empresa",
        "cuit": datos.get("cuit") or "",
        "direccion": datos.get("direccion") or "",
        "telefono": datos.get("telefono") or "",
        "email": datos.get("email") or "",
        "pagina_web": datos.get("pagina_web") or "",
        "logo_principal_url": datos.get("logo_principal_url") or "",
    }


def _resolve_logo_path():
    empresa = _empresa_info()
    url = empresa.get("logo_principal_url")

    if not url:
        return None

    media_url = settings.MEDIA_URL.rstrip("/")

    if url.startswith(media_url + "/"):
        rel = url[len(media_url) + 1:]
    elif url.startswith("/media/"):
        rel = url.replace("/media/", "", 1)
    elif url.startswith("/"):
        rel = url.lstrip("/")
    else:
        rel = url

    path = os.path.join(settings.MEDIA_ROOT, rel)

    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    return None


def _draw_logo_fallback(canvas_obj, x, y, nombre_empresa):
    canvas_obj.setFillColor(colors.HexColor("#F0F0F0"))
    canvas_obj.rect(x, y, 80, 40, fill=1)

    canvas_obj.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas_obj.rect(x, y, 80, 40)

    canvas_obj.setFillColor(colors.HexColor("#666666"))
    canvas_obj.setFont("Helvetica-Bold", 8)

    texto = (nombre_empresa or "EMPRESA")[:12]
    ancho = canvas_obj.stringWidth(texto, "Helvetica-Bold", 8)
    canvas_obj.drawString(x + (80 - ancho) / 2, y + 24, texto)

    canvas_obj.setFont("Helvetica", 7)
    ancho_logo = canvas_obj.stringWidth("LOGO", "Helvetica", 7)
    canvas_obj.drawString(x + (80 - ancho_logo) / 2, y + 14, "LOGO")


def _draw_header(canvas_obj, _doc):
    canvas_obj.saveState()

    empresa = _empresa_info()
    logo_path = _resolve_logo_path()

    logo_x = 40
    logo_y = A4[1] - 80

    if logo_path:
        try:
            canvas_obj.drawImage(
                logo_path,
                logo_x,
                logo_y,
                width=80,
                height=40,
                mask="auto",
            )
        except Exception:
            _draw_logo_fallback(canvas_obj, logo_x, logo_y, empresa["nombre_empresa"])
    else:
        _draw_logo_fallback(canvas_obj, logo_x, logo_y, empresa["nombre_empresa"])

    datos_x = 140
    y = A4[1] - 45

    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(datos_x, y, empresa["nombre_empresa"])

    canvas_obj.setFont("Helvetica", 9)

    if empresa["cuit"]:
        canvas_obj.drawString(datos_x, y - 12, f"CUIT: {empresa['cuit']}")

    if empresa["direccion"]:
        canvas_obj.drawString(datos_x, y - 24, empresa["direccion"])

    if empresa["telefono"]:
        canvas_obj.drawString(datos_x, y - 36, f"Tel: {empresa['telefono']}")

    if empresa["email"]:
        canvas_obj.drawString(datos_x, y - 48, f"Email: {empresa['email']}")

    canvas_obj.setStrokeColor(colors.gray)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(40, A4[1] - 95, A4[0] - 40, A4[1] - 95)

    canvas_obj.restoreState()


def _draw_footer(canvas_obj, _doc):
    canvas_obj.saveState()

    empresa = _empresa_info()

    texto = f"{empresa['nombre_empresa']}"

    if empresa["telefono"]:
        texto += f" - Tel: {empresa['telefono']}"

    if empresa["email"]:
        texto += f" - Email: {empresa['email']}"

    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.gray)

    ancho = canvas_obj.stringWidth(texto, "Helvetica", 8)
    canvas_obj.drawString((A4[0] - ancho) / 2, 30, texto)

    if empresa["pagina_web"]:
        ancho_web = canvas_obj.stringWidth(empresa["pagina_web"], "Helvetica", 8)
        canvas_obj.drawString((A4[0] - ancho_web) / 2, 18, empresa["pagina_web"])

    canvas_obj.restoreState()


def _cliente_nombre(pedido):
    if pedido.cliente:
        nombre = getattr(pedido.cliente, "nombre", "") or ""
        apellido = getattr(pedido.cliente, "apellido", "") or ""
        completo = f"{nombre} {apellido}".strip()
        return completo or str(pedido.cliente)

    if pedido.cliente_web:
        user = pedido.cliente_web.user
        return user.get_full_name() or user.email or str(user)

    return "Cliente web"


def _cliente_email(pedido):
    if pedido.cliente and getattr(pedido.cliente, "email", None):
        return pedido.cliente.email

    if pedido.cliente_web:
        return pedido.cliente_web.user.email or ""

    return ""


def _build_datos_pedido(styles, pedido):
    elements = []

    elements.append(Spacer(1, 15))

    elements.append(
        Paragraph(
            f"PEDIDO WEB N° {pedido.id:05d}",
            styles["PedidoTitle"],
        )
    )

    data = [
        ["Cliente:", _cliente_nombre(pedido)],
        ["Email:", _cliente_email(pedido) or "No informado"],
        ["Fecha:", pedido.creado.strftime("%d/%m/%Y %H:%M")],
        ["Estado:", pedido.get_estado_display()],
    ]

    table = Table(data, colWidths=[100, 400])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 15))

    return elements


def _build_items(pedido):
    data = [["Código", "Producto / Servicio", "Cant.", "Precio Unit.", "Subtotal"]]

    for item in pedido.items.all():
        precio = Decimal(str(item.precio_unitario_snapshot or 0))
        subtotal = Decimal(str(item.subtotal or 0))

        data.append(
            [
                item.codigo_snapshot or "-",
                item.nombre_snapshot or "",
                str(item.cantidad),
                f"${precio:,.2f}",
                f"${subtotal:,.2f}",
            ]
        )

    table = Table(data, colWidths=[70, 230, 45, 85, 85])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return [Paragraph("DETALLE DEL PEDIDO", getSampleStyleSheet()["Heading2"]), Spacer(1, 5), table, Spacer(1, 15)]


def _build_total(pedido):
    total = Decimal(str(pedido.total or 0))

    table = Table(
        [
            ["TOTAL:", f"${total:,.2f}"],
        ],
        colWidths=[350, 150],
    )

    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 13),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#10B981")),
                ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    return [table, Spacer(1, 15)]


def generar_pdf_pedido(pedido):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=85,
        bottomMargin=60,
        leftMargin=40,
        rightMargin=40,
    )

    styles = _styles()
    story = []

    story.extend(_build_datos_pedido(styles, pedido))
    story.extend(_build_items(pedido))
    story.extend(_build_total(pedido))

    if pedido.observaciones_cliente:
        story.append(Paragraph("OBSERVACIONES DEL CLIENTE", styles["Heading2"]))
        story.append(Paragraph(pedido.observaciones_cliente, styles["Normal"]))

    def _on_page(canvas_obj, doc_):
        _draw_header(canvas_obj, doc_)
        _draw_footer(canvas_obj, doc_)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)

    return buffer.getvalue()


def filename_for(pedido):
    fecha = datetime.now().strftime("%Y%m%d")
    cliente = _cliente_nombre(pedido).replace(" ", "_")
    return f"Pedido_{pedido.id:05d}_{cliente}_{fecha}.pdf"