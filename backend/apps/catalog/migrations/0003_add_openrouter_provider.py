from django.db import migrations, models


def seed_openrouter_model(apps, schema_editor):
    LLMModel = apps.get_model("catalog", "LLMModel")
    LLMModel.objects.update_or_create(
        provider="openrouter",
        name="openai/gpt-4.1-mini",
        defaults={
            "display_name": "OpenRouter GPT-4.1 Mini",
            "role": "general",
            "quality_level": 4,
            "speed_level": 4,
            "cost_level": 3,
            "privacy_level": "external",
            "context_window": 128000,
            "is_active": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_providercredential"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmmodel",
            name="provider",
            field=models.CharField(
                choices=[
                    ("ollama", "Ollama"),
                    ("openai", "OpenAI"),
                    ("gemini", "Gemini"),
                    ("openrouter", "OpenRouter"),
                ],
                max_length=32,
            ),
        ),
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
                unique=True,
            ),
        ),
        migrations.RunPython(seed_openrouter_model, migrations.RunPython.noop),
    ]
