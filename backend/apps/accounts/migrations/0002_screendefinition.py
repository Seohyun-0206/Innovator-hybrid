from django.db import migrations, models


DEFAULT_SCREENS = [
    {"screen_id": "dashboard", "label": "Dashboard", "description": "운영 지표와 최근 요청 현황", "sort_order": 10},
    {"screen_id": "playground", "label": "Playground", "description": "프롬프트 실행 및 라우팅 결과 확인", "sort_order": 20},
    {"screen_id": "simulator", "label": "Routing Simulator", "description": "프롬프트별 모델 선택 점수 시뮬레이션", "sort_order": 25},
    {"screen_id": "models", "label": "Models", "description": "LLM 모델 카탈로그 관리", "sort_order": 30},
    {"screen_id": "policies", "label": "Policies", "description": "라우팅 정책 관리", "sort_order": 40},
    {"screen_id": "credentials", "label": "Credentials", "description": "외부 Provider 접속 정보 관리", "sort_order": 50},
    {"screen_id": "logs", "label": "Routing Logs", "description": "라우팅 요청 로그 조회", "sort_order": 60},
    {"screen_id": "users", "label": "Users", "description": "사용자 계정 관리", "sort_order": 900},
    {"screen_id": "screens", "label": "Screens", "description": "화면 접근 권한 선택지 관리", "sort_order": 910},
]


def seed_default_screens(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    for screen in DEFAULT_SCREENS:
        ScreenDefinition.objects.update_or_create(
            screen_id=screen["screen_id"],
            defaults={
                "label": screen["label"],
                "description": screen["description"],
                "sort_order": screen["sort_order"],
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScreenDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("screen_id", models.SlugField(max_length=64, unique=True)),
                ("label", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["sort_order", "screen_id"],
            },
        ),
        migrations.RunPython(seed_default_screens, migrations.RunPython.noop),
    ]
