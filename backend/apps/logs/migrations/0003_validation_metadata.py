from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logs", "0002_usage_cost_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="routinglog",
            name="validation_status",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="routinglog",
            name="validation_errors",
            field=models.TextField(blank=True, default=""),
        ),
    ]
