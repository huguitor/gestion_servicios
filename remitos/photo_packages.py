from archivos.services.photo_packages import (
    generar_pdf_registro,
    generar_zip_originales,
    nombre_archivo_paquete,
    validar_seleccion_fotografica,
)


MAX_IMAGES = 30
MAX_TOTAL_BYTES = 100 * 1024 * 1024


def validar_adjuntos_fotograficos(*, remito, adjuntos, requested_ids):
    return validar_seleccion_fotografica(
        adjuntos=adjuntos,
        requested_ids=requested_ids,
        parent_id=remito.id,
        parent_field="remito_id",
        parent_label="remito",
        max_images=MAX_IMAGES,
        max_total_bytes=MAX_TOTAL_BYTES,
    )


def generar_pdf_fotografico(*, remito, adjuntos):
    return generar_pdf_registro(
        adjuntos=adjuntos,
        document_title="Remito",
        document_label="Remito",
        document_number=remito.numero_formateado,
        client_label=str(remito.cliente),
        date_label=remito.fecha_emision.strftime("%d/%m/%Y"),
    )


def generar_zip_fotografico(*, adjuntos):
    return generar_zip_originales(adjuntos=adjuntos)


def nombre_paquete(remito, extension):
    return nombre_archivo_paquete(
        prefix="Fotos_Remito",
        document_number=remito.numero_formateado,
        fallback_id=remito.pk,
        extension=extension,
    )
