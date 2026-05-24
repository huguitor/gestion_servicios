from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0002_pedido_cliente_web"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="stock_reservado_aplicado",
            field=models.BooleanField(
                default=False,
                help_text="Indica si este pedido ya aplicó reserva de stock.",
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="stock_finalizado_aplicado",
            field=models.BooleanField(
                default=False,
                help_text="Indica si este pedido ya aplicó salida definitiva o liberación de stock.",
            ),
        ),
    ]
