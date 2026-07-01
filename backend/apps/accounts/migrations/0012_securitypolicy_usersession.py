from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_security_screens(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    screens = [
        ("security-settings", "Security Settings", "Session and access security policy management.", 201),
        ("sessions", "User Sessions", "Active user session monitoring and revocation.", 202),
    ]
    for screen_id, label, description, sort_order in screens:
        ScreenDefinition.objects.update_or_create(
            screen_id=screen_id,
            defaults={
                "label": label,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0011_seed_health_overrides_screen"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("max_sessions_user", models.PositiveIntegerField(default=1)),
                ("max_sessions_staff", models.PositiveIntegerField(default=3)),
                ("idle_timeout_minutes", models.PositiveIntegerField(default=30)),
                ("absolute_timeout_hours", models.PositiveIntegerField(default=12)),
                (
                    "on_session_limit",
                    models.CharField(
                        choices=[("revoke_oldest", "Revoke oldest session"), ("block_new", "Block new login")],
                        default="revoke_oldest",
                        max_length=32,
                    ),
                ),
                ("revoke_sessions_on_permission_change", models.BooleanField(default=True)),
                ("block_inactive_user_login", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Security Policy",
                "verbose_name_plural": "Security Policy",
            },
        ),
        migrations.CreateModel(
            name="UserSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_key", models.CharField(max_length=80, unique=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("login_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("logout_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                            ("logged_out", "Logged out"),
                        ],
                        default="active",
                        max_length=32,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="managed_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-last_seen_at"],
            },
        ),
        migrations.RunPython(seed_security_screens, migrations.RunPython.noop),
    ]
