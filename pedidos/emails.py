# gestion/backend/pedidos/emails.py

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

from .pdf_generator import filename_for, generar_pdf_pedido


def _email_cliente(pedido):
    if not pedido.cliente_web:
        return ""

    return pedido.cliente_web.user.email or ""


def _nombre_cliente(pedido):
    if pedido.cliente:
        nombre = pedido.cliente.nombre or ""
        apellido = pedido.cliente.apellido or ""
        return f"{nombre} {apellido}".strip() or "Cliente"

    if pedido.cliente_web:
        user = pedido.cliente_web.user
        return user.get_full_name() or user.email or "Cliente"

    return "Cliente"


def _url_pedido(pedido):
    portal = getattr(
        settings,
        "PORTAL_CLIENTES_URL",
        "https://portal.panozosistemas.com.ar",
    )

    return f"{portal.rstrip('/')}/mis-pedidos/{pedido.id}"


def _items_texto(pedido):
    lineas = []

    for item in pedido.items.all():
        lineas.append(
            f"- {item.nombre_snapshot} | "
            f"Código: {item.codigo_snapshot or '-'} | "
            f"Cantidad: {item.cantidad} | "
            f"Precio unitario: ${item.precio_unitario_snapshot} | "
            f"Subtotal: ${item.subtotal}"
        )

    return "\n".join(lineas)


def _items_html(pedido):
    filas = ""

    for item in pedido.items.all():
        filas += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                    {escape(item.nombre_snapshot)}
                </td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                    {escape(item.codigo_snapshot or "-")}
                </td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center;">
                    {item.cantidad}
                </td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:right;">
                    ${item.precio_unitario_snapshot}
                </td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:right;">
                    ${item.subtotal}
                </td>
            </tr>
        """

    return filas


def _enviar_email(
    pedido,
    asunto,
    texto,
    html,
    adjuntar_pdf=False,
):
    email_cliente = _email_cliente(pedido)

    if not email_cliente:
        return False

    email = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[email_cliente],
    )

    email.attach_alternative(html, "text/html")

    if adjuntar_pdf:
        pdf_bytes = generar_pdf_pedido(pedido)

        email.attach(
            filename_for(pedido),
            pdf_bytes,
            "application/pdf",
        )

    email.send(fail_silently=False)

    return True


def enviar_email_pedido_recibido(pedido):
    nombre_cliente = _nombre_cliente(pedido)
    url_pedido = _url_pedido(pedido)

    asunto = f"Recibimos tu pedido #{pedido.id}"

    texto = f"""
Hola {nombre_cliente}.

Recibimos tu pedido web #{pedido.id}.

Estado actual:
{pedido.get_estado_display()}

Detalle del pedido:

{_items_texto(pedido)}

Total estimado:
${pedido.total}

Podés ver el detalle desde:
{url_pedido}

Adjuntamos el PDF del pedido.

Nos contactaremos para confirmar disponibilidad, forma de entrega y pago.

Muchas gracias.
"""

    html = f"""
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
    <div style="max-width:760px;margin:0 auto;padding:24px;">
        <div style="background:#ffffff;border-radius:12px;padding:24px;border:1px solid #e5e7eb;">
            <h2 style="margin-top:0;color:#111827;">Recibimos tu pedido #{pedido.id}</h2>

            <p>Hola <strong>{escape(nombre_cliente)}</strong>,</p>

            <p>
                Recibimos tu pedido web. El estado actual es:
                <strong>{escape(pedido.get_estado_display())}</strong>.
            </p>

            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
                <thead>
                    <tr style="background:#1e3a8a;color:white;">
                        <th style="padding:8px;text-align:left;">Producto</th>
                        <th style="padding:8px;text-align:left;">Código</th>
                        <th style="padding:8px;text-align:center;">Cant.</th>
                        <th style="padding:8px;text-align:right;">Precio</th>
                        <th style="padding:8px;text-align:right;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {_items_html(pedido)}
                </tbody>
            </table>

            <div style="text-align:right;margin-top:18px;font-size:18px;">
                <strong>Total estimado: ${pedido.total}</strong>
            </div>

            <p style="margin-top:24px;">
                <a href="{url_pedido}"
                   style="background:#1e3a8a;color:white;text-decoration:none;padding:10px 16px;border-radius:8px;display:inline-block;">
                    Ver detalle del pedido
                </a>
            </p>

            <p style="color:#6b7280;font-size:14px;">
                Adjuntamos el PDF del pedido. Nos contactaremos para confirmar disponibilidad,
                forma de entrega y pago.
            </p>
        </div>
    </div>
</body>
</html>
"""

    return _enviar_email(
        pedido=pedido,
        asunto=asunto,
        texto=texto,
        html=html,
        adjuntar_pdf=True,
    )


def enviar_email_estado_pedido(pedido):
    if pedido.estado not in ["confirmado", "cancelado", "entregado"]:
        return False

    nombre_cliente = _nombre_cliente(pedido)
    url_pedido = _url_pedido(pedido)

    asuntos = {
        "confirmado": f"Pedido #{pedido.id} confirmado",
        "cancelado": f"Pedido #{pedido.id} cancelado",
        "entregado": f"Pedido #{pedido.id} entregado",
    }

    mensajes = {
        "confirmado": "Tu pedido fue confirmado. Nos pondremos en contacto para coordinar entrega y pago.",
        "cancelado": "Tu pedido fue cancelado. Si creés que fue un error, contactanos.",
        "entregado": "Tu pedido fue marcado como entregado. Muchas gracias por confiar en nosotros.",
    }

    asunto = asuntos[pedido.estado]
    mensaje = mensajes[pedido.estado]

    texto = f"""
Hola {nombre_cliente}.

{mensaje}

Pedido:
#{pedido.id}

Estado:
{pedido.get_estado_display()}

Total:
${pedido.total}

Podés ver el detalle desde:
{url_pedido}

Muchas gracias.
"""

    html = f"""
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
    <div style="max-width:680px;margin:0 auto;padding:24px;">
        <div style="background:#ffffff;border-radius:12px;padding:24px;border:1px solid #e5e7eb;">
            <h2 style="margin-top:0;color:#111827;">{escape(asunto)}</h2>

            <p>Hola <strong>{escape(nombre_cliente)}</strong>,</p>

            <p>{escape(mensaje)}</p>

            <p>
                <strong>Pedido:</strong> #{pedido.id}<br>
                <strong>Estado:</strong> {escape(pedido.get_estado_display())}<br>
                <strong>Total:</strong> ${pedido.total}
            </p>

            <p style="margin-top:24px;">
                <a href="{url_pedido}"
                   style="background:#1e3a8a;color:white;text-decoration:none;padding:10px 16px;border-radius:8px;display:inline-block;">
                    Ver detalle del pedido
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""

    return _enviar_email(
        pedido=pedido,
        asunto=asunto,
        texto=texto,
        html=html,
        adjuntar_pdf=False,
    )