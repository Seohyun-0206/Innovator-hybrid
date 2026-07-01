# Generated manually for the MVP scaffold.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RoutingLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prompt_summary", models.CharField(max_length=240)),
                ("policy", models.CharField(max_length=64)),
                ("selected_provider", models.CharField(max_length=32)),
                ("selected_model", models.CharField(max_length=120)),
                ("routing_reason", models.TextField()),
                ("latency_ms", models.PositiveIntegerField()),
                ("estimated_tokens", models.PositiveIntegerField()),
                ("response_text", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
