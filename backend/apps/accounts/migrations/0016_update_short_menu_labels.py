from django.db import migrations


SCREEN_LABELS = [
    ("models", "모델"),
    ("policies", "정책"),
    ("service-features", "대상 서비스"),
    ("policy-draft", "초안 생성"),
    ("playground", "테스트"),
    ("simulator", "시뮬레이션"),
    ("validation-rules", "응답 규칙"),
]


def update_screen_labels(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    for screen_id, label in SCREEN_LABELS:
        ScreenDefinition.objects.filter(screen_id=screen_id).update(label=label)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_update_korean_screen_labels"),
    ]

    operations = [
        migrations.RunPython(update_screen_labels, migrations.RunPython.noop),
    ]
