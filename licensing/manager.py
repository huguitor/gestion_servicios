# ==========================================================
# backend/licensing/manager.py
# ==========================================================

import os

from licensing.license import load_license


class LicenseManager:

    def __init__(self):

        self.license = load_license()

    def is_enabled(
        self,
        module_name,
    ):

        env_enabled = (
            os.getenv(
                f"MODULO_{module_name.upper()}",
                "False",
            ).lower()
            == "true"
        )

        licensed = (
            module_name
            in self.license.get(
                "modules",
                [],
            )
        )

        return env_enabled and licensed

    def modules(self):

        result = {}

        modules = [
            "clientes",
            "productos",
            "presupuestos",
            "pedidos",
            "remitos",
            "stock",
            "backup",
            "web_publica",
        ]

        for module in modules:

            result[module] = (
                self.is_enabled(
                    module
                )
            )

        return result


license_manager = (
    LicenseManager()
)
