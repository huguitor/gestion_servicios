from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0002_pedido_cliente_web"),
        ("productos", "0004_producto_stock_reservado"),
    ]

    operations = [
        migrations.CreateModel(
            name="MovimientoStock",

            fields=[

                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),

                (
                    "tipo",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("entrada", "Entrada"),
                            ("reserva", "Reserva"),
                            ("liberacion", "Liberación"),
                            ("salida", "Salida"),
                            ("ajuste", "Ajuste"),
                        ],
                    ),
                ),

                (
                    "cantidad",
                    models.IntegerField(),
                ),

                (
                    "stock_anterior",
                    models.IntegerField(),
                ),

                (
                    "stock_reservado_anterior",
                    models.IntegerField(default=0),
                ),

                (
                    "stock_nuevo",
                    models.IntegerField(),
                ),

                (
                    "stock_reservado_nuevo",
                    models.IntegerField(default=0),
                ),

                (
                    "observacion",
                    models.TextField(
                        blank=True,
                        default="",
                    ),
                ),

                (
                    "creado",
                    models.DateTimeField(
                        auto_now_add=True
                    ),
                ),

                (
                    "pedido",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="movimientos_stock",
                        to="pedidos.pedido",
                    ),
                ),

                (
                    "producto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="movimientos_stock",
                        to="productos.producto",
                    ),
                ),
            ],

            options={
                "ordering": [
                    "-creado",
                    "-id",
                ],
                "verbose_name": "Movimiento de stock",
                "verbose_name_plural": "Movimientos de stock",
            },
        ),
    ]
