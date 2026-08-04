import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserScreenAccess


@pytest.mark.django_db
def test_chart_permission_can_read_evaluation_data_without_execute_access():
    user = User.objects.create_user(username="chart-viewer", password="pass12345")
    token = Token.objects.create(user=user)
    UserScreenAccess.objects.create(user=user, allowed_screens=["model-evaluation-chart"])

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    assert client.get("/api/evaluation-runs/").status_code == 200
    assert client.get("/api/evaluation-results/").status_code == 200
    assert client.post("/api/evaluation-runs/", {}, format="json").status_code == 403

