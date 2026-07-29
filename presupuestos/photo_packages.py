from django.utils import timezone

from archivos.services.photo_packages import (
    generar_pdf_registro,
    generar_zip_originales,
    nombre_archivo_paquete,
    validar_seleccion_fotografica,
)


MAX_IMAGES = 30
MAX_TOTAL_BYTES = 100 * 1024 * 1024


def numero_formateado(presupuesto):
    serie = presupuesto.comprobante.serie if presupuesto.comprobante else "PRES"
    numero = f"{presupuesto.numero:06d}" if presupuesto.numero else "SIN_NUMERO"
    return f"{serie}-{numero}"


def validar_adjuntos_fotograficos(*, presupuesto, adjuntos, requested_ids):
    return validar_seleccion_fotografica(
        adjuntos=adjuntos,
        requested_ids=requested_ids,
        parent_id=presupuesto.id,
        parent_field="presupuesto_id",
        parent_label="presupuesto",
        max_images=MAX_IMAGES,
        max_total_bytes=MAX_TOTAL_BYTES,
    )


def generar_pdf_fotografico(*, presupuesto, adjuntos):
    fecha = timezone.localtime(presupuesto.fecha).strftime("%d/%m/%Y")
    return generar_pdf_registro(
        adjuntos=adjuntos,
        document_title="Presupuesto",
        document_label="Presupuesto",
        document_number=numero_formateado(presupuesto),
        client_label=str(presupuesto.cliente),
        date_label=fecha,
    )


def generar_zip_fotografico(*, adjuntos):
    return generar_zip_originales(adjuntos=adjuntos)


def nombre_paquete(presupuesto, extension):
    return nombre_archivo_paquete(
        prefix="Fotos_Presupuesto",
        document_number=numero_formateado(presupuesto),
        fallback_id=presupuesto.pk,
        extension=extension,
    )
