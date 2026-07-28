from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from remitos.models import Remito

from .models import Cobro, FacturaCobranza, SeguimientoCobranza
from .services import registrar_cobro


class CobroSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.CharField(
        source="registrado_por.get_full_name",
        read_only=True,
    )

    class Meta:
        model = Cobro
        fields = [
            "id",
            "fecha_cobro",
            "importe",
            "medio_pago",
            "referencia",
            "observaciones",
            "registrado_por",
            "registrado_por_nombre",
            "creado",
            "actualizado",
        ]
        read_only_fields = [
            "registrado_por",
            "registrado_por_nombre",
            "creado",
            "actualizado",
        ]

    def create(self, validated_data):
        try:
            return registrar_cobro(
                factura=self.context["factura"],
                registrado_por=self.context["request"].user,
                **validated_data,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise serializers.ValidationError(detail) from exc


class SeguimientoCobranzaSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.CharField(
        source="registrado_por.get_full_name",
        read_only=True,
    )

    class Meta:
        model = SeguimientoCobranza
        fields = [
            "id",
            "fecha",
            "tipo",
            "detalle",
            "registrado_por",
            "registrado_por_nombre",
            "creado",
        ]
        read_only_fields = ["registrado_por", "registrado_por_nombre", "creado"]


class FacturaCobranzaSerializer(serializers.ModelSerializer):
    remitos = serializers.PrimaryKeyRelatedField(
        queryset=Remito.objects.select_related("cliente").all(),
        many=True,
        required=False,
    )
    numero_completo = serializers.CharField(read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.__str__", read_only=True)
    tipo_comprobante_display = serializers.CharField(
        source="get_tipo_comprobante_display",
        read_only=True,
    )
    total_cobrado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_notas_credito = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    importe_con_efecto = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    saldo_pendiente = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    fecha_ultimo_cobro = serializers.DateField(read_only=True)
    estado = serializers.CharField(read_only=True)
    vencida = serializers.BooleanField(read_only=True)
    dias_para_cobro = serializers.IntegerField(read_only=True)
    semaforo = serializers.CharField(read_only=True)
    remitos_info = serializers.SerializerMethodField()
    presupuesto_info = serializers.SerializerMethodField()
    cobros = CobroSerializer(many=True, read_only=True)
    seguimientos = SeguimientoCobranzaSerializer(many=True, read_only=True)

    class Meta:
        model = FacturaCobranza
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "presupuesto",
            "presupuesto_referencia",
            "presupuesto_info",
            "remitos",
            "remitos_info",
            "fecha_factura",
            "tipo_comprobante",
            "tipo_comprobante_display",
            "punto_venta",
            "numero_factura",
            "numero_completo",
            "orden_compra",
            "total",
            "importe_con_efecto",
            "comprobante_original",
            "observaciones",
            "fecha_envio",
            "medio_envio",
            "enviado_por",
            "observacion_envio",
            "plazo_cobro_dias",
            "fecha_estimada_cobro",
            "fecha_estimada_manual",
            "creado_por",
            "creado",
            "actualizado",
            "total_cobrado",
            "total_notas_credito",
            "saldo_pendiente",
            "fecha_ultimo_cobro",
            "estado",
            "vencida",
            "dias_para_cobro",
            "semaforo",
            "cobros",
            "seguimientos",
        ]
        read_only_fields = [
            "creado_por",
            "creado",
            "actualizado",
            "enviado_por",
        ]

    def get_remitos_info(self, obj):
        return [
            {
                "id": remito.id,
                "numero": remito.numero_formateado,
                "fecha": remito.fecha_emision,
            }
            for remito in obj.remitos.all()
        ]

    def get_presupuesto_info(self, obj):
        if not obj.presupuesto:
            return None
        comprobante = obj.presupuesto.comprobante
        referencia = (
            f"{comprobante.serie}-{obj.presupuesto.numero:06d}"
            if comprobante and obj.presupuesto.numero
            else str(obj.presupuesto.numero or "")
        )
        return {
            "id": obj.presupuesto.id,
            "numero": referencia,
            "fecha": obj.presupuesto.fecha,
        }

    def validate(self, attrs):
        cliente = attrs.get("cliente", getattr(self.instance, "cliente", None))
        presupuesto = attrs.get(
            "presupuesto", getattr(self.instance, "presupuesto", None)
        )
        remitos = attrs.get("remitos")
        remitos_a_validar = (
            remitos
            if remitos is not None
            else (self.instance.remitos.all() if self.instance else [])
        )

        if presupuesto and cliente and presupuesto.cliente_id != cliente.id:
            raise serializers.ValidationError(
                {"presupuesto": "El presupuesto debe pertenecer al cliente seleccionado."}
            )
        if cliente:
            if self.instance:
                try:
                    self.instance.validar_remitos(
                        remitos_a_validar,
                        cliente_id=cliente.id,
                    )
                except DjangoValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict) from exc
            elif any(
                remito.cliente_id != cliente.id for remito in remitos_a_validar
            ):
                raise serializers.ValidationError(
                    {"remitos": "Todos los remitos deben pertenecer al cliente seleccionado."}
                )
        if self.instance and "total" in attrs:
            total_cobrado = self.instance.cobros.aggregate(total=Sum("importe"))[
                "total"
            ] or Decimal("0.00")
            total_notas_credito = self.instance.notas_credito.aggregate(
                total=Sum("total")
            )["total"] or Decimal("0.00")
            if attrs["total"] < total_cobrado + total_notas_credito:
                raise serializers.ValidationError(
                    {
                        "total": (
                            "El total no puede ser menor que los cobros y "
                            "notas de crédito aplicados."
                        )
                    }
                )
        if self.instance and self.instance.cobros.exists():
            campos_bloqueados = (
                "cliente",
                "fecha_factura",
                "tipo_comprobante",
                "punto_venta",
                "numero_factura",
                "presupuesto",
            )
            errores = {
                campo: "Este campo no puede modificarse después de registrar cobros."
                for campo in campos_bloqueados
                if campo in attrs and attrs[campo] != getattr(self.instance, campo)
            }
            if errores:
                raise serializers.ValidationError(errores)

        manual = attrs.get(
            "fecha_estimada_manual",
            getattr(self.instance, "fecha_estimada_manual", False),
        )
        fecha_presente = "fecha_estimada_cobro" in attrs
        if fecha_presente and "fecha_estimada_manual" not in attrs:
            attrs["fecha_estimada_manual"] = True
            manual = True
        if manual and not attrs.get(
            "fecha_estimada_cobro",
            getattr(self.instance, "fecha_estimada_cobro", None),
        ):
            raise serializers.ValidationError(
                {"fecha_estimada_cobro": "Debe indicar la fecha estimada manual."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        remitos = validated_data.pop("remitos", [])
        cliente = validated_data["cliente"]
        validated_data.setdefault("plazo_cobro_dias", cliente.plazo_cobro_dias)
        self._completar_referencia_presupuesto(validated_data)
        try:
            factura = FacturaCobranza.objects.create(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        factura.remitos.set(remitos)
        return factura

    @transaction.atomic
    def update(self, instance, validated_data):
        remitos = validated_data.pop("remitos", None)
        self._completar_referencia_presupuesto(validated_data)
        try:
            instance = super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        if remitos is not None:
            instance.remitos.set(remitos)
        return instance

    @staticmethod
    def _completar_referencia_presupuesto(validated_data):
        presupuesto = validated_data.get("presupuesto")
        if presupuesto and not validated_data.get("presupuesto_referencia"):
            comprobante = presupuesto.comprobante
            if comprobante and presupuesto.numero:
                validated_data["presupuesto_referencia"] = (
                    f"{comprobante.serie}-{presupuesto.numero:06d}"
                )
            elif presupuesto.numero:
                validated_data["presupuesto_referencia"] = str(presupuesto.numero)


class FacturaCobranzaListSerializer(FacturaCobranzaSerializer):
    """Resumen sin historiales completos para listados y dashboard."""

    class Meta(FacturaCobranzaSerializer.Meta):
        fields = [
            field
            for field in FacturaCobranzaSerializer.Meta.fields
            if field not in {"cobros", "seguimientos"}
        ]
