# Generated manually for the MVP scaffold.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LLMModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("ollama", "Ollama"), ("openai", "OpenAI"), ("gemini", "Gemini")], max_length=32)),
                ("name", models.CharField(max_length=120)),
                ("display_name", models.CharField(max_length=160)),
                ("role", models.CharField(choices=[("general", "General"), ("coding", "Coding"), ("reasoning", "Reasoning"), ("summary", "Summary")], default="general", max_length=32)),
                ("quality_level", models.PositiveSmallIntegerField(default=3)),
                ("speed_level", models.PositiveSmallIntegerField(default=3)),
                ("cost_level", models.PositiveSmallIntegerField(default=1)),
                ("privacy_level", models.CharField(choices=[("local", "Local"), ("external", "External")], default="local", max_length=32)),
                ("context_window", models.PositiveIntegerField(default=8192)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["provider", "name"],
                "unique_together": {("provider", "name")},
            },
        ),
        migrations.CreateModel(
            name="RoutingPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.SlugField(max_length=64, unique=True)),
                ("display_name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("priority_config", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
