# ==========================================================
# gestion/backend/licensing/decorators.py
# ==========================================================

from rest_framework.response import Response
from rest_framework import status

from licensing.manager import (
    license_manager
)


def require_module(
    module_name,
):

    def decorator(
        view_method,
    ):

        @wraps(view_method)
        def wrapped(
            self,
            request,
            *args,
            **kwargs,
        ):

            if (
                not
                license_manager
                .is_enabled(
                    module_name
                )
            ):

                return Response(
                    {
                        "error":
                            "license_required",

                        "detail":
                            (
                                "Modulo deshabilitado "
                                "por licencia"
                            ),

                        "module":
                            module_name,
                    },

                    status=
                    status.HTTP_403_FORBIDDEN,
                )

            return (
                view_method(
                    self,
                    request,
                    *args,
                    **kwargs,
                )
            )

        return wrapped

    return decorator
from functools import wraps
