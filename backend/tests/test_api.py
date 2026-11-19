from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.investigation import GeminiFailure
from backend.app.main import create_app
from backend.app.models import Anomaly, GeminiAttempt


def test_health_options_and_openapi(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["synthetic"] is True
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert len(client.get("/api/options").json()["accounts"]) == 8
    assert client.get("/openapi.json").status_code == 200


def test_rules_are_default_without_removing_other_approaches(client, session):
    rule_count = session.scalar(select(func.count()).select_from(Anomaly).where(Anomaly.rule_detected))
    ml_count = session.scalar(select(func.count()).select_from(Anomaly).where(Anomaly.ml_detected))
    combined_count = session.scalar(select(func.count()).select_from(Anomaly))
    assert client.get("/api/summary").json()["anomaly_count"] == rule_count
    for approach, expected in [
        ("rules", rule_count),
        ("isolation_forest", ml_count),
        ("combined", combined_count),
    ]:
        assert client.get(f"/api/anomalies?approach={approach}").json()["total"] == expected
    assert client.get("/api/anomalies?approach=invalid").status_code == 422


def test_summary_matches_series_and_filters(client):
    summary = client.get("/api/summary").json()
    assert summary["transaction_count"] == 5000
    points = client.get("/api/series").json()
    assert sum(point["count"] for point in points) == 5000
    assert sum(point["inflow_cents"] for point in points) == summary["inflow_cents"]
    assert sum(point["outflow_cents"] for point in points) == summary["outflow_cents"]
    filtered = client.get("/api/summary?account_id=1&start=2025-10-01&end=2025-10-31").json()
    assert 0 < filtered["transaction_count"] < 5000
    empty = client.get("/api/summary?start=2030-01-01").json()
    assert empty["transaction_count"] == 0 and empty["approval_rate"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "/api/summary?start=2025-12-01&end=2025-01-01",
        "/api/transactions?page=-1",
        "/api/transactions?page_size=1000",
        "/api/transactions?status=invalid",
        "/api/anomalies?severity=invalid",
        "/api/summary?account_id=-1",
    ],
)
def test_query_validation(client, url):
    assert client.get(url).status_code == 422


@pytest.mark.parametrize("path", ["summary", "transactions", "anomalies"])
def test_maximum_end_date_is_inclusive(client, path):
    response = client.get(f"/api/{path}?end=9999-12-31")
    assert response.status_code == 200
    assert response.json()["transaction_count" if path == "summary" else "total"] > 0


def test_transaction_search_pagination_and_channel_filter(client):
    first = client.get("/api/transactions?page_size=10&status=declined&channel_id=2").json()
    second = client.get("/api/transactions?page_size=10&status=declined&channel_id=2&page=2").json()
    assert first["items"] and all(
        item["status"] == "declined" and item["channel_id"] == 2 for item in first["items"]
    )
    assert not ({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})
    ref = first["items"][0]["payment_ref"]
    assert all(
        item["payment_ref"] == ref for item in client.get(f"/api/transactions?search={ref}").json()["items"]
    )
    assert client.get("/api/transactions?search=%25").json()["total"] == 0


def test_anomaly_detail_history_and_rules_investigation(client, auth):
    anomaly = client.get("/api/anomalies?severity=critical&page_size=1").json()["items"][0]
    detail = client.get(f"/api/anomalies/{anomaly['id']}").json()
    assert detail["transactions"] and detail["evidence"]
    response = client.post(
        f"/api/anomalies/{anomaly['id']}/investigate", headers=auth, json={"provider": "rules"}
    )
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["source"] == "rules"
    assert set(analysis["content"]) == {"summary", "evidence", "hypotheses", "recommendations", "limitations"}
    history = client.get(f"/api/anomalies/{anomaly['id']}/analyses").json()
    assert history[0]["id"] == analysis["id"]
    assert client.get("/api/anomalies/9999999").status_code == 404


def test_analysis_preview_does_not_persist(client):
    anomaly_id = client.get("/api/anomalies?page_size=1").json()["items"][0]["id"]
    before = client.get(f"/api/anomalies/{anomaly_id}/analyses").json()
    response = client.get(f"/api/anomalies/{anomaly_id}/analysis-preview")
    assert response.status_code == 200
    assert response.json()["source"] == "rules"
    assert response.json()["content"]["evidence"]
    assert client.get(f"/api/anomalies/{anomaly_id}/analyses").json() == before


def test_gemini_diagnostics_stay_in_backend(seeded_engine, session, auth):
    settings = Settings(_env_file=None, finops_admin_key=auth["X-Admin-Key"], gemini_api_key="test-key")
    with TestClient(create_app(settings, seeded_engine)) as local:
        with patch(
            "backend.app.investigation.gemini_analysis",
            side_effect=GeminiFailure("model_unavailable", 404, "NOT_FOUND"),
        ):
            response = local.post("/api/anomalies/1/investigate", headers=auth, json={"provider": "gemini"})
        assert response.status_code == 200
        analysis = response.json()
        assert analysis["source"] == "rules" and analysis["model"] == "deterministic-v1"
        assert analysis["fallback_reason"] == "gemini_failed_or_invalid_response"
        assert "provider_code" not in analysis and "http_status" not in analysis
        history = local.get("/api/anomalies/1/analyses").json()
        assert "provider_code" not in history[0] and "http_status" not in history[0]
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == analysis["id"]))
    assert attempt.http_status == 404 and attempt.provider_code == "NOT_FOUND"


def test_public_demo_has_no_administrative_routes(seeded_engine):
    from fastapi.testclient import TestClient

    settings = Settings(_env_file=None, public_demo=True, gemini_api_key="", notification_mode="simulated")
    with TestClient(create_app(settings, seeded_engine)) as demo:
        assert demo.get("/api/health").json()["public_demo"] is True
        paths = demo.get("/openapi.json").json()["paths"]
        assert "/api/automations/pending" not in paths
        for path in [
            "/api/pipeline/run",
            "/api/automations/run",
            "/api/anomalies/1/investigate",
        ]:
            assert demo.post(path, headers={"X-Admin-Key": settings.finops_admin_key}).status_code in (
                404,
                405,
            )
        assert "post" not in paths["/api/anomalies/{anomaly_id}/analysis-preview"]


def test_public_demo_rejects_external_integrations(seeded_engine):
    with pytest.raises(ValueError, match="Gemini desativado"):
        create_app(Settings(_env_file=None, public_demo=True, gemini_api_key="configured"), seeded_engine)
    with pytest.raises(ValueError, match="notificações simuladas"):
        create_app(Settings(_env_file=None, public_demo=True, notification_mode="smtp"), seeded_engine)


@pytest.mark.parametrize(
    "path", ["/api/pipeline/run", "/api/automations/run", "/api/anomalies/1/investigate"]
)
def test_all_writes_require_admin_key(client, path):
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, headers={"X-Admin-Key": "incorrect"}, json={}).status_code == 401


def test_admin_rate_limit(client):
    for _ in range(12):
        assert client.post("/api/pipeline/run").status_code == 401
    assert client.post("/api/pipeline/run").status_code == 429


def test_missing_key_disables_writes(seeded_engine):
    from fastapi.testclient import TestClient

    with TestClient(create_app(Settings(_env_file=None, finops_admin_key=""), seeded_engine)) as client:
        assert client.post("/api/pipeline/run").status_code == 503


def test_pipeline_api_is_idempotent(client, auth):
    first = client.post("/api/pipeline/run", headers=auth)
    second = client.post("/api/pipeline/run", headers=auth)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_automation_api_deduplicates(client, auth, session):
    anomaly = session.scalar(
        select(Anomaly).where(Anomaly.severity == "critical", Anomaly.rule_detected).order_by(Anomaly.id)
    )
    body = {"anomaly_ids": [anomaly.id, anomaly.id]}
    first = client.post("/api/automations/run", headers=auth, json=body)
    assert first.status_code == 200
    assert first.json()["processed"] == 1
    second = client.post("/api/automations/run", headers=auth, json=body)
    assert second.json()["processed"] == 0
    assert client.get("/api/automations").json()["attempts"][0]["status"] == "simulated"
