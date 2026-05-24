# Generated manually for stock reservation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("productos", "0003_producto_descripcion_corta_producto_destacado_web_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="stock_reservado",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Cantidad reservada por pedidos web pendientes o confirmados.",
            ),
        ),
    ]
