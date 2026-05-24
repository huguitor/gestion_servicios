# gestion/backend/web_clientes/services.py

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner


EMAIL_VERIFICATION_SALT = "web_clientes.email_verification"


def generar_token_verificacion(cliente_web):
    signer = TimestampSigner(salt=EMAIL_VERIFICATION_SALT)
    return signer.sign(str(cliente_web.id))


def enviar_email_verificacion(cliente_web, next_url="/"):
    token = generar_token_verificacion(cliente_web)

    verificar_url = (
        f"{settings.BACKEND_BASE_URL}"
        f"/api/web-clientes/verificar-email/{token}/"
        f"?next={next_url}"
    )

    asunto = "Verificá tu correo"

    mensaje = f"""Hola {cliente_web.user.first_name}.

Para activar tu cuenta y poder ver precios o realizar pedidos, verificá tu correo ingresando al siguiente enlace:

{verificar_url}

Si vos no creaste esta cuenta, podés ignorar este mensaje.
"""

    send_mail(
        subject=asunto,
        message=mensaje,
        from_email=None,
        recipient_list=[cliente_web.user.email],
        fail_silently=False,
    )