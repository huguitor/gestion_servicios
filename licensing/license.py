# ==========================================================
# ARCHIVO:
# backend/licensing/license.py
#
# RESPONSABILIDAD:
# Leer licencia local desde:
#
# /srv/gestion/license.json
#
# Primera versión:
# - carga archivo
# - valida existencia
# - valida JSON
# - devuelve dict
# ==========================================================

from pathlib import Path
import json
import logging


logger = logging.getLogger(__name__)


LICENSE_PATH = Path("/app/license.json")


DEFAULT_LICENSE = {
    "version": 1,
    "cliente": "SIN LICENCIA",
    "modules": [],
    "expires": None,
}


def load_license():
    """
    Lee licencia local.
    Nunca rompe backend.
    """

    try:

        if not LICENSE_PATH.exists():

            logger.warning(
                "LICENSE → archivo no encontrado"
            )

            return DEFAULT_LICENSE.copy()

        with open(
            LICENSE_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        logger.info(
            "LICENSE → cargada cliente=%s",
            data.get("cliente"),
        )

        return data

    except Exception as e:

        logger.exception(
            "LICENSE ERROR → %s",
            e,
        )

        return DEFAULT_LICENSE.copy()
