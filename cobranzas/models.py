from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class FacturaCobranza(models.Model):
    TIPO_FACTURA_A = "factura_a"
    TIPO_FACTURA_B = "factura_b"
    TIPO_FACTURA_C = "factura_c"
    TIPO_NOTA_DEBITO = "nota_debito"
    TIPO_OTRO = "otro"
    TIPO_COMPROBANTE_CHOICES = [
        (TIPO_FACTURA_A, "Factura A"),
        (TIPO_FACTURA_B, "Factura B"),
        (TIPO_FACTURA_C, "Factura C"),
        (TIPO_NOTA_DEBITO, "Nota de débito"),
        (TIPO_OTRO, "Otro"),
    ]

    MEDIO_ENVIO_CHOICES = [
        ("correo_electronico", "Correo electrónico"),
        ("papel", "Papel"),
        ("portal", "Portal"),
        ("whatsapp", "WhatsApp"),
        ("otro", "Otro"),
    ]

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="facturas_cobranza",
    )
    presupuesto = models.ForeignKey(
        "presupuestos.Presupuesto",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="facturas_cobranza",
    )
    presupuesto_referencia = models.CharField(max_length=100, blank=True)
    remitos = models.ManyToManyField(
        "remitos.Remito",
        blank=True,
        related_name="facturas_cobranza",
    )
    fecha_factura = models.DateField()
    tipo_comprobante = models.CharField(
        max_length=30,
        choices=TIPO_COMPROBANTE_CHOICES,
    )
    punto_venta = models.PositiveIntegerField()
    numero_factura = models.PositiveBigIntegerField()
    orden_compra = models.CharField(max_length=100, blank=True)
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    observaciones = models.TextField(blank=True)

    fecha_envio = models.DateField(null=True, blank=True)
    medio_envio = models.CharField(
        max_length=30,
        choices=MEDIO_ENVIO_CHOICES,
        blank=True,
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="facturas_cobranza_enviadas",
    )
    observacion_envio = models.TextField(blank=True)

    plazo_cobro_dias = models.PositiveIntegerField(
        default=None,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    fecha_estimada_cobro = models.DateField(null=True, blank=True)
    fecha_estimada_manual = models.BooleanField(default=False)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facturas_cobranza_creadas",
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_factura", "-id"]
        verbose_name = "Factura de cobranza"
        verbose_name_plural = "Facturas de cobranza"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_comprobante", "punto_venta", "numero_factura"],
                name="cobranzas_factura_identificacion_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gt=0),
                name="cobranzas_factura_total_positivo",
            ),
            models.CheckConstraint(
                condition=models.Q(plazo_cobro_dias__gte=0),
                name="cobranzas_factura_plazo_no_negativo",
            ),
        ]
        permissions = [
            ("registrar_cobro", "Puede registrar cobros"),
            ("agregar_seguimiento", "Puede agregar seguimientos de cobranza"),
        ]
        indexes = [
            models.Index(fields=["cliente", "fecha_factura"]),
            models.Index(fields=["fecha_estimada_cobro"]),
            models.Index(fields=["tipo_comprobante", "punto_venta", "numero_factura"]),
        ]

    def clean(self):
        errors = {}
        if self.presupuesto_id and self.cliente_id:
            presupuesto_cliente_id = (
                self.presupuesto.cliente_id
                if hasattr(self, "presupuesto")
                else None
            )
            if presupuesto_cliente_id != self.cliente_id:
                errors["presupuesto"] = "El presupuesto debe pertenecer al cliente de la factura."
        if self.pk and self.cliente_id:
            if self.remitos.exclude(cliente_id=self.cliente_id).exists():
                errors["cliente"] = (
                    "No puede cambiarse el cliente mientras existan remitos de otro cliente."
                )

            total_cobrado = self.cobros.aggregate(total=Sum("importe"))[
                "total"
            ] or Decimal("0.00")
            if self.total is not None and self.total < total_cobrado:
                errors["total"] = "El total no puede ser menor que los cobros registrados."

            if total_cobrado > Decimal("0.00"):
                original = FacturaCobranza.objects.get(pk=self.pk)
                campos_bloqueados = {
                    "cliente_id": "cliente",
                    "fecha_factura": "fecha_factura",
                    "tipo_comprobante": "tipo_comprobante",
                    "punto_venta": "punto_venta",
                    "numero_factura": "numero_factura",
                    "total": "total",
                    "presupuesto_id": "presupuesto",
                }
                for atributo, campo in campos_bloqueados.items():
                    if getattr(self, atributo) != getattr(original, atributo):
                        errors[campo] = (
                            "Este campo no puede modificarse después de registrar cobros."
                        )
        if self.fecha_envio and self.fecha_envio < self.fecha_factura:
            errors["fecha_envio"] = "La fecha de envío no puede ser anterior a la fecha de factura."
        if self.fecha_estimada_manual and not self.fecha_estimada_cobro:
            errors["fecha_estimada_cobro"] = "Debe indicar una fecha estimada cuando se marca como manual."
        if (
            self.fecha_estimada_cobro
            and self.fecha_factura
            and self.fecha_estimada_cobro < self.fecha_factura
        ):
            errors["fecha_estimada_cobro"] = (
                "La fecha estimada de cobro no puede ser anterior a la fecha de factura."
            )
        if errors:
            raise ValidationError(errors)

    def calcular_fecha_estimada(self):
        """Usa fecha de envío; si falta, usa fecha de factura como fallback."""
        base = self.fecha_envio or self.fecha_factura
        return base + timedelta(days=self.plazo_cobro_dias) if base else None

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        update_fields = set(update_fields) if update_fields is not None else None
        if self._state.adding and self.plazo_cobro_dias is None and self.cliente_id:
            self.plazo_cobro_dias = self.cliente.plazo_cobro_dias
            if update_fields is not None:
                update_fields.add("plazo_cobro_dias")
        if not self.fecha_estimada_manual:
            self.fecha_estimada_cobro = self.calcular_fecha_estimada()
            if update_fields is not None:
                update_fields.add("fecha_estimada_cobro")
        if update_fields is not None:
            kwargs["update_fields"] = update_fields
        self.full_clean(exclude=["remitos"])
        super().save(*args, **kwargs)

    def validar_remitos(self, remitos, *, cliente_id=None):
        """Valida pertenencia e inmutabilidad antes de reemplazar la relación."""
        remitos = list(remitos)
        cliente_id = self.cliente_id if cliente_id is None else cliente_id
        if any(remito.cliente_id != cliente_id for remito in remitos):
            raise ValidationError(
                {"remitos": "Todos los remitos deben pertenecer al cliente de la factura."}
            )
        if self.pk and self.cobros.exists():
            actuales = set(self.remitos.values_list("pk", flat=True))
            nuevos = {remito.pk for remito in remitos}
            if actuales != nuevos:
                raise ValidationError(
                    {"remitos": "Los remitos no pueden modificarse después de registrar cobros."}
                )

    @property
    def numero_completo(self):
        return f"{self.punto_venta:05d}-{self.numero_factura:08d}"

    @property
    def total_cobrado(self):
        if hasattr(self, "_total_cobrado"):
            return self._total_cobrado or Decimal("0.00")
        agregado = self.cobros.aggregate(total=Sum("importe"))["total"]
        return agregado or Decimal("0.00")

    @property
    def saldo_pendiente(self):
        return self.total - self.total_cobrado

    @property
    def fecha_ultimo_cobro(self):
        if hasattr(self, "_fecha_ultimo_cobro"):
            return self._fecha_ultimo_cobro
        return self.cobros.order_by("-fecha_cobro", "-id").values_list(
            "fecha_cobro", flat=True
        ).first()

    @property
    def estado(self):
        total_cobrado = self.total_cobrado
        if total_cobrado == Decimal("0.00"):
            return "pendiente"
        if total_cobrado < self.total:
            return "parcial"
        return "pagado"

    @property
    def vencida(self):
        return bool(
            self.estado != "pagado"
            and self.fecha_estimada_cobro
            and self.fecha_estimada_cobro < timezone.localdate()
        )

    @property
    def dias_para_cobro(self):
        if self.estado == "pagado" or not self.fecha_estimada_cobro:
            return None
        return (self.fecha_estimada_cobro - timezone.localdate()).days

    @property
    def semaforo(self):
        if self.estado == "pagado":
            return "gris"
        dias = self.dias_para_cobro
        if dias is None or dias > 7:
            return "verde"
        if dias >= 0:
            return "amarillo"
        return "rojo"

    def __str__(self):
        return f"{self.get_tipo_comprobante_display()} {self.numero_completo}"


class Cobro(models.Model):
    MEDIO_PAGO_CHOICES = [
        ("transferencia", "Transferencia"),
        ("cheque", "Cheque"),
        ("efectivo", "Efectivo"),
        ("deposito", "Depósito"),
        ("retencion", "Retención"),
        ("compensacion", "Compensación"),
        ("otro", "Otro"),
    ]

    factura = models.ForeignKey(
        FacturaCobranza,
        on_delete=models.PROTECT,
        related_name="cobros",
    )
    fecha_cobro = models.DateField()
    importe = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    medio_pago = models.CharField(max_length=30, choices=MEDIO_PAGO_CHOICES)
    referencia = models.CharField(max_length=150, blank=True)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cobros_registrados",
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_cobro", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(importe__gt=0),
                name="cobranzas_cobro_importe_positivo",
            ),
        ]
        indexes = [
            models.Index(fields=["fecha_cobro"]),
            models.Index(fields=["factura", "fecha_cobro"]),
        ]

    def clean(self):
        if self.importe is not None and self.importe <= 0:
            raise ValidationError({"importe": "El importe debe ser mayor que cero."})
        if (
            self.factura_id
            and self.fecha_cobro
            and self.fecha_cobro < self.factura.fecha_factura
        ):
            raise ValidationError(
                {"fecha_cobro": "La fecha de cobro no puede ser anterior a la fecha de factura."}
            )
        if self.factura_id and self.importe:
            otros = self.factura.cobros.exclude(pk=self.pk).aggregate(
                total=Sum("importe")
            )["total"] or Decimal("0.00")
            if otros + self.importe > self.factura.total:
                raise ValidationError({"importe": "El cobro supera el saldo pendiente de la factura."})

    def __str__(self):
        return f"Cobro {self.factura.numero_completo} - {self.importe}"


class SeguimientoCobranza(models.Model):
    TIPO_CHOICES = [
        ("nota", "Nota"),
        ("reclamo", "Reclamo"),
        ("contacto", "Contacto"),
        ("promesa_pago", "Promesa de pago"),
        ("confirmacion_recepcion", "Confirmación de recepción"),
        ("otro", "Otro"),
    ]

    factura = models.ForeignKey(
        FacturaCobranza,
        on_delete=models.PROTECT,
        related_name="seguimientos",
    )
    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    detalle = models.TextField()
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seguimientos_cobranza_registrados",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado", "-id"]
        indexes = [
            models.Index(fields=["factura", "fecha"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.factura.numero_completo}"
