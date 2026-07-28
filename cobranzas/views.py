from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.db.models import (
    DateField,
    DecimalField,
    F,
    ExpressionWrapper,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from licensing.decorators import require_module

from .filters import FacturaCobranzaFilter
from .models import Cobro, FacturaCobranza
from .permissions import PuedeGestionarCobranzas
from .serializers import (
    CobroSerializer,
    FacturaCobranzaListSerializer,
    FacturaCobranzaSerializer,
    SeguimientoCobranzaSerializer,
)
from .services import generar_excel_cobranzas


ZERO_MONEY = Value(
    Decimal("0.00"),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


class FacturaCobranzaViewSet(viewsets.ModelViewSet):
    serializer_class = FacturaCobranzaSerializer
    permission_classes = [PuedeGestionarCobranzas]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = FacturaCobranzaFilter
    search_fields = [
        "cliente__nombre",
        "cliente__apellido",
        "cliente__documento",
        "orden_compra",
        "presupuesto_referencia",
        "remitos__numero",
    ]
    ordering_fields = [
        "fecha_factura",
        "fecha_estimada_cobro",
        "total",
        "punto_venta",
        "numero_factura",
    ]
    ordering = ["-fecha_factura", "-id"]

    def get_serializer_class(self):
        if self.action in {"list", "dashboard"}:
            return FacturaCobranzaListSerializer
        return FacturaCobranzaSerializer

    def get_queryset(self):
        total_cobrado = (
            Cobro.objects.filter(factura_id=OuterRef("pk"))
            .values("factura_id")
            .annotate(total=Sum("importe"))
            .values("total")[:1]
        )
        ultimo_cobro = Cobro.objects.filter(
            factura_id=OuterRef("pk")
        ).order_by("-fecha_cobro", "-id").values("fecha_cobro")[:1]
        total_notas_credito = (
            FacturaCobranza.objects.filter(
                comprobante_original_id=OuterRef("pk"),
                tipo_comprobante=FacturaCobranza.TIPO_NOTA_CREDITO,
            )
            .values("comprobante_original_id")
            .annotate(total=Sum("total"))
            .values("total")[:1]
        )
        queryset = (
            FacturaCobranza.objects.select_related(
                "cliente",
                "comprobante_original",
                "presupuesto__comprobante",
                "creado_por",
                "enviado_por",
            )
            .prefetch_related(
                "remitos__comprobante",
            )
            .annotate(
                _total_cobrado=Coalesce(
                    Subquery(
                        total_cobrado,
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    ),
                    ZERO_MONEY,
                ),
                _fecha_ultimo_cobro=Subquery(
                    ultimo_cobro,
                    output_field=DateField(),
                ),
                _total_notas_credito=Coalesce(
                    Subquery(
                        total_notas_credito,
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    ),
                    ZERO_MONEY,
                ),
            )
            .annotate(
                _total_aplicado=ExpressionWrapper(
                    F("_total_cobrado") + F("_total_notas_credito"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
            .distinct()
        )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "cobros__registrado_por",
                "seguimientos__registrado_por",
            )
        return queryset

    def perform_create(self, serializer):
        enviado_por = (
            self.request.user if serializer.validated_data.get("fecha_envio") else None
        )
        serializer.save(creado_por=self.request.user, enviado_por=enviado_por)

    def perform_update(self, serializer):
        extras = {}
        if (
            serializer.validated_data.get("fecha_envio")
            and not serializer.instance.enviado_por_id
        ):
            extras["enviado_por"] = self.request.user
        serializer.save(**extras)

    @action(detail=True, methods=["get", "post"])
    def cobros(self, request, pk=None):
        factura = self.get_object()
        if request.method == "GET":
            return Response(CobroSerializer(factura.cobros.all(), many=True).data)

        serializer = CobroSerializer(
            data=request.data,
            context={"request": request, "factura": factura},
        )
        serializer.is_valid(raise_exception=True)
        cobro = serializer.save()
        return Response(CobroSerializer(cobro).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def seguimientos(self, request, pk=None):
        factura = self.get_object()
        if request.method == "GET":
            return Response(
                SeguimientoCobranzaSerializer(
                    factura.seguimientos.all(), many=True
                ).data
            )

        serializer = SeguimientoCobranzaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seguimiento = serializer.save(
            factura=factura,
            registrado_por=request.user,
        )
        return Response(
            SeguimientoCobranzaSerializer(seguimiento).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        fin_proximas = hoy + timedelta(days=7)
        queryset = self.filter_queryset(self.get_queryset())
        facturas = queryset.exclude(
            tipo_comprobante=FacturaCobranza.TIPO_NOTA_CREDITO
        )
        pendientes = facturas.filter(_total_aplicado__lt=F("total"))

        resumen = pendientes.aggregate(
            total_pendiente=Coalesce(
                Sum(F("total") - F("_total_aplicado")),
                ZERO_MONEY,
            ),
            total_vencido=Coalesce(
                Sum(
                    F("total") - F("_total_aplicado"),
                    filter=Q(fecha_estimada_cobro__lt=hoy),
                ),
                ZERO_MONEY,
            ),
        )
        total_facturado = facturas.aggregate(
            total=Coalesce(Sum("total"), ZERO_MONEY)
        )["total"]
        total_notas_credito = queryset.filter(
            tipo_comprobante=FacturaCobranza.TIPO_NOTA_CREDITO
        ).aggregate(total=Coalesce(Sum("total"), ZERO_MONEY))["total"]
        total_cobrado_documentos = facturas.aggregate(
            total=Coalesce(Sum("_total_cobrado"), ZERO_MONEY)
        )["total"]
        resumen["total_pendiente"] = max(
            total_facturado - total_notas_credito - total_cobrado_documentos,
            Decimal("0.00"),
        )
        hay_rango = bool(
            request.query_params.get("fecha_desde")
            or request.query_params.get("fecha_hasta")
        )
        if hay_rango:
            total_cobrado_mes = facturas.aggregate(
                total=Coalesce(Sum("_total_cobrado"), ZERO_MONEY)
            )["total"]
        else:
            total_cobrado_mes = Cobro.objects.filter(
                fecha_cobro__gte=inicio_mes,
                fecha_cobro__lte=hoy,
            ).aggregate(total=Coalesce(Sum("importe"), ZERO_MONEY))["total"]
        cantidades = {
            "pendiente": facturas.filter(_total_aplicado=Decimal("0.00")).count(),
            "parcial": facturas.filter(
                _total_aplicado__gt=Decimal("0.00"),
                _total_aplicado__lt=F("total"),
            ).count(),
            "pagado": facturas.filter(_total_aplicado=F("total")).count(),
        }
        proximas = pendientes.filter(
            fecha_estimada_cobro__gte=hoy,
            fecha_estimada_cobro__lte=fin_proximas,
        )

        return Response(
            {
                **resumen,
                "total_facturado": total_facturado,
                "total_notas_credito": total_notas_credito,
                "total_cobrado_mes": total_cobrado_mes,
                "cantidades_por_estado": cantidades,
                "proximas_a_vencer": FacturaCobranzaListSerializer(
                    proximas,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    @action(detail=False, methods=["get"], url_path="exportar-excel")
    @require_module("cobranzas")
    def exportar_excel(self, request):
        comprobantes = self.filter_queryset(self.get_queryset())
        contenido = generar_excel_cobranzas(comprobantes)
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        if fecha_desde or fecha_hasta:
            desde = fecha_desde or "inicio"
            hasta = fecha_hasta or "hoy"
            nombre = f"cobranzas_{desde}_a_{hasta}.xlsx"
        else:
            nombre = f"cobranzas_{timezone.localdate().isoformat()}.xlsx"
        response = HttpResponse(
            contenido,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response
