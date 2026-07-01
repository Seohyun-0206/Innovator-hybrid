from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0017_modelhealthoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="providercredential",
            name="last_used_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="providercredential",
            name="token_rotated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
