# gestion/presupuestos/pdf_generator.py
#
# Generador de PDF para presupuestos — portado de tkinter_client/pdf_generator.py.
# Diferencias clave:
#   - Sin Tkinter (sin filedialog, sin messagebox). Escribe a un buffer en memoria.
#   - Sin búsqueda heurística de logo en C:\... — usa MEDIA_ROOT de Django.
#   - Datos de empresa vienen del modelo ConfiguracionGlobal vía ConfiguracionService.
#
# Layout idéntico al original: zona fija de 3cm en cabecera con logo + datos empresa,
# luego cliente + número, items, totales, observaciones, condiciones, y footer.

import io
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from configuracion.services import ConfiguracionService


CONDICION_IVA_LABELS = {
    'ri': 'Responsable Inscripto',
    'mono': 'Monotributista',
    'exento': 'Exento',
    'cf': 'Consumidor Final',
    'noresidente': 'No Residente',
}


def _styles():
    """Devuelve la stylesheet con los estilos personalizados del PDF."""
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            name='PresupuestoTitle',
            parent=s['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.navy,
        )
    )
    s.add(
        ParagraphStyle(
            name='EmpresaInfo',
            parent=s['Normal'],
            fontSize=9,
            textColor=colors.darkblue,
        )
    )
    return s


def _resolve_logo_path():
    """
    Resuelve la ruta física del logo principal desde la config.
    `logo_principal_url` suele venir como '/media/config/logos/xxx.jpg' →
    lo mapeamos a MEDIA_ROOT/config/logos/xxx.jpg.
    """
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
    """Datos de empresa con fallbacks por defecto."""
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
    """Rectángulo gris con el nombre cuando no hay logo."""
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
    """Header fijo: logo a la izquierda, datos empresa a la derecha, línea inferior."""
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
    """Footer centrado con nombre + página web + teléfono."""
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


def _build_cliente_section(styles, cliente, numero):
    """Cabecera con datos cliente a la izquierda y nº/fecha a la derecha."""
    elements = [Spacer(1, 15)]
    try:
        numero_fmt = f"{int(numero):05d}" if numero else "00000"
    except (TypeError, ValueError):
        numero_fmt = str(numero) if numero else "00000"

    header_table = Table(
        [
            [
                '',
                f"PRESUPUESTO N° {numero_fmt}\n\nFecha: {datetime.now().strftime('%d/%m/%Y')}",
            ]
        ],
        colWidths=[360, 140],
    )
    header_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (1, 0), (1, 0), 11),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("DATOS DEL CLIENTE", styles['Heading2']))
    elements.append(Spacer(1, 5))

    nombre = f"{getattr(cliente, 'nombre', '') or ''} {getattr(cliente, 'apellido', '') or ''}".strip()
    rows = [
        ['Cliente:', nombre or 'Sin nombre'],
        ['CUIT:', getattr(cliente, 'documento', '') or 'No especificado'],
        [
            'Condición IVA:',
            CONDICION_IVA_LABELS.get(
                getattr(cliente, 'condicion_iva', ''), getattr(cliente, 'condicion_iva', '') or '—'
            ),
        ],
        ['Teléfono:', getattr(cliente, 'telefono', '') or 'No especificado'],
        ['Email:', getattr(cliente, 'email', '') or 'No especificado'],
        ['Dirección:', getattr(cliente, 'direccion', '') or 'No especificado'],
    ]
    table = Table(rows, colWidths=[100, 400])
    table.setStyle(
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
    elements.append(table)
    elements.append(Spacer(1, 15))
    return elements


def _build_items_section(styles, items):
    """Tabla con items: código, descripción, cantidad, precio unit, subtotal."""
    elements = [Paragraph("DETALLE DEL PRESUPUESTO", styles['Heading2']), Spacer(1, 3)]
    data = [['Código', 'Descripción', 'Cant.', 'Precio Unit.', 'Subtotal']]

    for item in items:
        cantidad = int(item.cantidad or 0)
        precio = Decimal(str(item.precio_unitario or 0))
        subtotal = (cantidad * precio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        data.append(
            [
                item.codigo or '',
                item.descripcion or '',
                str(cantidad),
                f"${precio:,.2f}",
                f"${subtotal:,.2f}",
            ]
        )

    table = Table(data, colWidths=[70, 240, 40, 80, 80])
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 15))
    return elements


def _build_totales_section(presupuesto):
    """Bloque con subtotal, IVA y total — total en verde con fondo."""
    subtotal = Decimal(str(presupuesto.subtotal or 0))
    iva_porcentaje = Decimal(str(presupuesto.iva_porcentaje or 0))
    iva_valor = Decimal(str(presupuesto.iva_valor or 0))
    total = Decimal(str(presupuesto.total or 0))

    rows = [
        ['', ''],
        ['SUBTOTAL:', f"${subtotal:,.2f}"],
        [f"IVA ({iva_porcentaje}%):", f"${iva_valor:,.2f}"],
        ['TOTAL:', f"${total:,.2f}"],
    ]
    table = Table(rows, colWidths=[250, 150])
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, -1), 12),
                ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (-1, -1), (-1, -1), 14),
                ('BACKGROUND', (-1, -1), (-1, -1), colors.HexColor('#10B981')),
                ('TEXTCOLOR', (-1, -1), (-1, -1), colors.white),
            ]
        )
    )
    return [table, Spacer(1, 20)]


def _build_observaciones_section(styles, presupuesto):
    """Observaciones del presupuesto + condiciones comerciales (de config si no hay)."""
    elements = []

    try:
        cfg = ConfiguracionService.obtener_config_presupuestos()
        condiciones_default = cfg.get('condiciones_comerciales') or ''
    except Exception:
        condiciones_default = ''

    if presupuesto.observaciones:
        elements.append(Paragraph("OBSERVACIONES", styles['Heading2']))
        elements.append(Spacer(1, 5))
        obs = presupuesto.observaciones.replace('\n', '<br/>')
        elements.append(Paragraph(obs, styles['Normal']))
        elements.append(Spacer(1, 10))

    condiciones = presupuesto.condiciones_comerciales or condiciones_default
    if condiciones:
        elements.append(Paragraph("CONDICIONES COMERCIALES", styles['Heading2']))
        elements.append(Spacer(1, 5))

        validez = '15 días'
        if presupuesto.valido_hasta:
            try:
                validez = f"hasta el {presupuesto.valido_hasta.strftime('%d/%m/%Y')}"
            except Exception:
                pass

        lineas = condiciones.split('\n')
        out = []
        validez_set = False
        for linea in lineas:
            if any(k in linea.lower() for k in ('mantenimiento', 'validez', 'vigencia')):
                out.append(f"Validez de oferta: {validez}")
                validez_set = True
            else:
                out.append(linea)
        if not validez_set:
            out.append(f"Validez de oferta: {validez}")

        elements.append(Paragraph('<br/>'.join(out), styles['Normal']))
        elements.append(Spacer(1, 15))

    return elements


def generar_pdf_presupuesto(presupuesto):
    """
    Genera el PDF de un Presupuesto y devuelve los bytes.

    `presupuesto` es la instancia Django; se accede a `presupuesto.cliente`,
    `presupuesto.items.all()`, totales precalculados (subtotal/iva_valor/total)
    y `numero`/`observaciones`/`condiciones_comerciales`/`valido_hasta`.
    """
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
    story.extend(_build_cliente_section(styles, presupuesto.cliente, presupuesto.numero))
    story.extend(_build_items_section(styles, presupuesto.items.all()))
    story.extend(_build_totales_section(presupuesto))
    story.extend(_build_observaciones_section(styles, presupuesto))

    def _on_page(canvas_obj, doc_):
        _draw_logo_zone(canvas_obj, doc_)
        _draw_footer(canvas_obj, doc_)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()


def filename_for(presupuesto):
    """Nombre sugerido para Content-Disposition."""
    numero = presupuesto.numero or 0
    cliente = getattr(presupuesto.cliente, 'nombre', '') or 'cliente'
    cliente = cliente.replace(' ', '_')
    fecha = datetime.now().strftime('%Y%m%d')
    return f"Presupuesto_{numero:05d}_{cliente}_{fecha}.pdf"
