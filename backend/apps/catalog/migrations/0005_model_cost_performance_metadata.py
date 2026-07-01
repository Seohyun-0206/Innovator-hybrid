from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_model_provider_credential"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmmodel",
            name="input_token_price_per_1m",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="llmmodel",
            name="output_token_price_per_1m",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="llmmodel",
            name="average_latency_ms",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="llmmodel",
            name="timeout_seconds",
            field=models.PositiveIntegerField(default=120),
        ),
    ]
