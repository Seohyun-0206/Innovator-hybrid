from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("logs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="routinglog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="routing_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="routinglog",
            name="estimated_cost_usd",
            field=models.DecimalField(decimal_places=8, default=0, max_digits=12),
        ),
    ]
