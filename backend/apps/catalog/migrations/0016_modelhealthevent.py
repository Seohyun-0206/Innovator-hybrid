from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0015_seed_default_recovery_strategy"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelHealthEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("triggered", "Triggered"), ("recovered", "Recovered")], max_length=32)),
                ("provider", models.CharField(max_length=32)),
                ("model_name", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("healthy", "Healthy"), ("unhealthy", "Unhealthy")], max_length=32)),
                ("rule_name", models.CharField(blank=True, default="", max_length=120)),
                ("reason", models.TextField(blank=True)),
                ("request_count", models.PositiveIntegerField(default=0)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("failure_rate", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("average_latency_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="catalog.modelhealthrule",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
