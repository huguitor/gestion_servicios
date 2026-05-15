# gestion/remitos/pdf_generator.py
#
# Generador de PDF para remitos — portado de tkinter_client/pdf_generator_remitos.py.
# Comparte el layout de cabecera/footer con presupuestos pero las secciones
# centrales son distintas:
#   - sin totales (un remito es un albarán de entrega, no una factura)
#   - sin IVA ni precios
#   - tiene origen/destino, referencias (presupuesto/licitación/Nº ref) y
#     espacio para firma del receptor

import io
import os
from datetime import datetime

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from configuracion.services import ConfiguracionService


def _styles():
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            name='RemitoTitle',
            parent=s['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.navy,
        )
    )
    return s


def _resolve_logo_path():
    """Idéntico al de presupuestos: map config.logo_principal_url → MEDIA_ROOT."""
    try:
        datos = ConfiguracionService.obtener_datos_empresa()
        url = datos.get('logo_principal_url')
        if not url:
            return None
        media_url = settings.MEDIA_URL.rstrip('/')
        if url.startswith(media_url + '/'):
            rel = url[len(media_url) + 1:]
        elif url.startswith('/'):
            rel = url.lstrip('/')
        else:
            rel = url
        path = os.path.join(settings.MEDIA_ROOT, rel)
        return path if os.path.exists(path) and os.path.getsize(path) > 0 else None
    except Exception:
        return None


def _empresa_info():
    try:
        d = ConfiguracionService.obtener_datos_empresa()
    except Exception:
        d = {}
    return {
        'nombre_empresa': d.get('nombre_empresa') or 'LAB Servicios',
        'cuit': d.get('cuit') or '',
        'direccion': d.get('direccion') or '',
        'telefono': d.get('telefono') or '',
        'email': d.get('email') or '',
        'pagina_web': d.get('pagina_web') or '',
    }


def _draw_logo_fallback(canvas_obj, x, y, nombre_empresa):
    canvas_obj.setFillColor(colors.HexColor('#F0F0F0'))
    canvas_obj.rect(x, y, 80, 40, fill=1)
    canvas_obj.setStrokeColor(colors.HexColor('#CCCCCC'))
    canvas_obj.setLineWidth(1)
    canvas_obj.rect(x, y, 80, 40)
    canvas_obj.setFillColor(colors.HexColor('#666666'))
    canvas_obj.setFont('Helvetica-Bold', 8)
    nombre = (nombre_empresa or 'EMPRESA')[:10]
    w = canvas_obj.stringWidth(nombre, 'Helvetica-Bold', 8)
    canvas_obj.drawString(x + (80 - w) / 2, y + 25, nombre)
    canvas_obj.setFont('Helvetica', 7)
    w = canvas_obj.stringWidth('LOGO', 'Helvetica', 7)
    canvas_obj.drawString(x + (80 - w) / 2, y + 15, 'LOGO')


def _draw_logo_zone(canvas_obj, _doc):
    """Header fijo idéntico al de presupuestos."""
    canvas_obj.saveState()
    empresa = _empresa_info()
    logo_path = _resolve_logo_path()

    logo_x = 40
    logo_y = A4[1] - 80
    if logo_path:
        if empresa['pagina_web']:
            canvas_obj.linkURL(
                empresa['pagina_web'],
                (logo_x, logo_y, logo_x + 80, logo_y + 40),
                relative=0,
            )
        try:
            canvas_obj.drawImage(
                logo_path, logo_x, logo_y, width=80, height=40, mask='auto'
            )
        except Exception:
            _draw_logo_fallback(canvas_obj, logo_x, logo_y, empresa['nombre_empresa'])
    else:
        _draw_logo_fallback(canvas_obj, logo_x, logo_y, empresa['nombre_empresa'])

    canvas_obj.setFont('Helvetica', 9)
    datos_x = 140
    canvas_obj.drawString(datos_x, A4[1] - 45, empresa['nombre_empresa'])
    if empresa['cuit']:
        canvas_obj.drawString(datos_x, A4[1] - 55, f"CUIT: {empresa['cuit']}")
    if empresa['direccion']:
        canvas_obj.drawString(datos_x, A4[1] - 65, empresa['direccion'])
    if empresa['telefono']:
        canvas_obj.drawString(datos_x, A4[1] - 75, f"Tel: {empresa['telefono']}")
    if empresa['email']:
        canvas_obj.drawString(datos_x, A4[1] - 85, f"Email: {empresa['email']}")

    canvas_obj.setStrokeColor(colors.gray)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(40, A4[1] - 95, A4[0] - 40, A4[1] - 95)
    canvas_obj.restoreState()


def _draw_footer(canvas_obj, _doc):
    canvas_obj.saveState()
    empresa = _empresa_info()
    if empresa['pagina_web']:
        text = f"{empresa['nombre_empresa']} - {empresa['pagina_web']} - Tel: {empresa['telefono']}"
    else:
        text = f"{empresa['nombre_empresa']} - Tel: {empresa['telefono']} - Email: {empresa['email']}"
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(colors.gray)
    w = canvas_obj.stringWidth(text, 'Helvetica', 8)
    canvas_obj.drawString((A4[0] - w) / 2, 30, text)
    canvas_obj.restoreState()


def _fmt_fecha(value):
    """Formatea fecha aceptando date, datetime o string ISO."""
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return str(value)


def _build_remito_info_section(styles, remito):
    """Número de remito + fechas + origen/destino + cliente."""
    elements = [Spacer(1, 10)]

    numero_fmt = remito.numero_formateado or 'Sin número'
    header_table = Table(
        [['', f"REMITO INTERNO N°: {numero_fmt}"]],
        colWidths=[350, 150],
    )
    header_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (1, 0), (1, 0), 14),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 10))

    fechas_rows = [['FECHA DE EMISIÓN:', _fmt_fecha(remito.fecha_emision)]]
    if remito.fecha_entrega:
        fechas_rows.append(['FECHA DE ENTREGA:', _fmt_fecha(remito.fecha_entrega)])
    fechas_table = Table(fechas_rows, colWidths=[120, 380])
    fechas_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ]
        )
    )
    elements.append(fechas_table)
    elements.append(Spacer(1, 10))

    if remito.origen or remito.destino:
        od_table = Table(
            [
                ['ORIGEN:', remito.origen or 'No especificado'],
                ['DESTINO:', remito.destino or 'No especificado'],
            ],
            colWidths=[80, 420],
        )
        od_table.setStyle(
            TableStyle(
                [
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ]
            )
        )
        elements.append(od_table)
        elements.append(Spacer(1, 10))

    elements.append(Paragraph("DATOS DEL CLIENTE", styles['Heading2']))
    elements.append(Spacer(1, 5))

    cliente = remito.cliente
    nombre = f"{getattr(cliente, 'nombre', '') or ''} {getattr(cliente, 'apellido', '') or ''}".strip()
    rows = [
        ['Cliente:', nombre or 'Sin nombre'],
        ['CUIT:', getattr(cliente, 'documento', '') or 'No especificado'],
        ['Teléfono:', getattr(cliente, 'telefono', '') or 'No especificado'],
        ['Dirección:', getattr(cliente, 'direccion', '') or 'No especificado'],
    ]
    cliente_table = Table(rows, colWidths=[100, 400])
    cliente_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ]
        )
    )
    elements.append(cliente_table)
    elements.append(Spacer(1, 15))
    return elements


def _build_referencias_section(remito):
    """Sólo se muestra si hay al menos una referencia cargada."""
    rows = []
    if remito.presupuesto_relacionado:
        rows.append(['Presupuesto:', remito.presupuesto_relacionado])
    if remito.licitacion_orden:
        rows.append(['Licitación/Orden:', remito.licitacion_orden])
    if remito.numero_referencia:
        rows.append(['N° de Referencia:', remito.numero_referencia])

    if not rows:
        return []

    table = Table(rows, colWidths=[120, 380])
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ]
        )
    )
    return [table, Spacer(1, 15)]


def _build_items_section(styles, items):
    """Tabla de entrega: #, descripción, cantidad (con unidad), observaciones."""
    elements = [Paragraph("DETALLE DE LA ENTREGA", styles['Heading2']), Spacer(1, 5)]

    data = [['#', 'Descripción', 'Cantidad', 'Observaciones']]
    for i, item in enumerate(items, 1):
        try:
            cantidad_str = f"{float(item.cantidad):.2f} {item.unidad_medida or ''}".strip()
        except (TypeError, ValueError):
            cantidad_str = f"{item.cantidad} {item.unidad_medida or ''}".strip()
        data.append(
            [
                str(i),
                f"{(item.codigo + ' — ') if item.codigo else ''}{item.descripcion or ''}",
                cantidad_str,
                item.observaciones or '',
            ]
        )

    table = Table(data, colWidths=[30, 300, 80, 90])
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('ALIGN', (3, 1), (3, -1), 'LEFT'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ]
        )
    )
    return [*elements, table, Spacer(1, 20)]


def _build_observaciones_section(styles, remito):
    if not remito.observaciones:
        return []
    obs = remito.observaciones.replace('\n', '<br/>')
    return [
        Paragraph("OBSERVACIONES", styles['Heading2']),
        Spacer(1, 5),
        Paragraph(obs, styles['Normal']),
        Spacer(1, 15),
    ]


def _build_firmas_section(styles):
    """Espacio reservado para firma del receptor."""
    firma_style = ParagraphStyle(
        name='FirmaSimple',
        parent=styles['Normal'],
        fontSize=10,
        alignment=0,
        textColor=colors.black,
        spaceAfter=10,
    )
    return [
        Spacer(1, 60),
        Paragraph(
            "RECIBIDO POR: <br/><br/><br/><br/>Firma y aclaración: ",
            firma_style,
        ),
    ]


def generar_pdf_remito(remito):
    """Genera el PDF del remito y devuelve los bytes."""
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
    story.extend(_build_remito_info_section(styles, remito))
    story.extend(_build_referencias_section(remito))
    story.extend(_build_items_section(styles, remito.items.all()))
    story.extend(_build_observaciones_section(styles, remito))
    story.extend(_build_firmas_section(styles))

    def _on_page(canvas_obj, doc_):
        _draw_logo_zone(canvas_obj, doc_)
        _draw_footer(canvas_obj, doc_)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()


def filename_for(remito):
    """Nombre sugerido para Content-Disposition."""
    numero = remito.numero or 0
    cliente = getattr(remito.cliente, 'nombre', '') or 'cliente'
    cliente = cliente.replace(' ', '_')
    fecha = datetime.now().strftime('%Y%m%d')
    return f"Remito_{numero:05d}_{cliente}_{fecha}.pdf"
