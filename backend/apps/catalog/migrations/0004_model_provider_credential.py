from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_add_openrouter_provider"),
    ]

    operations = [
        migrations.AlterField(
            model_name="providercredential",
            name="provider",
            field=models.CharField(
                choices=[
                    ("openai", "OpenAI"),
                    ("gemini", "Gemini"),
                    ("openrouter", "OpenRouter"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="llmmodel",
            name="provider_credential",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="models",
                to="catalog.providercredential",
            ),
        ),
    ]
