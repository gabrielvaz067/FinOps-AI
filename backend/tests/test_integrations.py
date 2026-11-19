import json
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from backend.app.automation import run_automation
from backend.app.config import Settings
from backend.app.investigation import deterministic, gemini_analysis, investigate
from backend.app.models import Analysis, Anomaly, GeminiAttempt, Notification


def test_gemini_structured_response_and_minimal_payload(session):
    anomaly = session.scalar(select(Anomaly))
    expected = deterministic(anomaly)

    def handler(request):
        payload = json.loads(request.content)
        assert request.url.host == "generativelanguage.googleapis.com"
        assert "transactions" not in payload["contents"][0]["parts"][0]["text"]
        assert "account_id" not in payload["contents"][0]["parts"][0]["text"]
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": expected.model_dump_json()}]}}
                ]
            },
        )

    result, status = gemini_analysis(
        anomaly, Settings(_env_file=None, gemini_api_key="test-key"), httpx.MockTransport(handler)
    )
    assert result == expected and status == 200


def test_controlled_gemini_investigation_records_source_model_and_sections(session):
    anomaly = session.scalar(select(Anomaly).where(Anomaly.severity == "critical"))
    expected = deterministic(anomaly)

    def handler(request):
        assert request.headers["x-goog-api-key"] == "test-key"
        assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
        return httpx.Response(
            201,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": expected.model_dump_json()}]}}
                ]
            },
        )

    result = investigate(
        session,
        anomaly,
        Settings(_env_file=None, gemini_api_key="test-key", gemini_model="gemini-2.5-flash"),
        "gemini",
        httpx.MockTransport(handler),
    )
    assert result.source == "gemini" and result.model == "gemini-2.5-flash"
    assert result.fallback_reason is None
    assert all(result.content[name] for name in ("evidence", "hypotheses", "recommendations", "limitations"))
    assert "revisão humana" in result.content["limitations"][-1]
    assert session.get(Analysis, result.id).source == "gemini"
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id))
    assert attempt.provider == "gemini" and attempt.requested_model == "gemini-2.5-flash"
    assert attempt.http_status == 201 and attempt.category == "success" and attempt.attempted_at


@pytest.mark.parametrize(
    ("status", "provider_code", "category"),
    [
        (400, "INVALID_ARGUMENT", "invalid_request"),
        (400, "FAILED_PRECONDITION", "failed_precondition"),
        (403, "PERMISSION_DENIED", "permission_denied"),
        (404, "NOT_FOUND", "model_unavailable"),
        (429, "RESOURCE_EXHAUSTED", "quota_exceeded"),
        (500, "INTERNAL", "temporary_service_failure"),
        (503, "UNAVAILABLE", "temporary_service_failure"),
    ],
)
def test_gemini_http_failure_is_recorded_without_provider_message(
    session, caplog, status, provider_code, category
):
    anomaly = session.scalar(select(Anomaly))
    response = httpx.Response(
        status,
        json={
            "error": {
                "status": provider_code,
                "message": "private-provider-message-must-not-be-logged",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "TEST_REASON",
                        "metadata": {"secret": "private-provider-metadata-must-not-be-logged"},
                    }
                ],
            }
        },
    )
    result = investigate(
        session,
        anomaly,
        Settings(_env_file=None, gemini_api_key="test-key", gemini_model="gemini-3.5-flash-lite"),
        "gemini",
        httpx.MockTransport(lambda _: response),
    )
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id))
    assert result.source == "rules" and result.model == "deterministic-v1"
    assert result.fallback_reason == "gemini_failed_or_invalid_response"
    assert (attempt.http_status, attempt.provider_code, attempt.provider_reason, attempt.category) == (
        status,
        provider_code,
        "TEST_REASON",
        category,
    )
    assert attempt.requested_model == "gemini-3.5-flash-lite" and attempt.attempted_at
    assert "private-provider-message" not in caplog.text
    assert "private-provider-metadata" not in caplog.text


@pytest.mark.parametrize(
    ("exception_type", "category"),
    [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection_error")],
)
def test_gemini_transport_failure_is_recorded(session, exception_type, category):
    anomaly = session.scalar(select(Anomaly))

    def handler(request):
        raise exception_type("private-transport-detail", request=request)

    result = investigate(
        session,
        anomaly,
        Settings(_env_file=None, gemini_api_key="test-key"),
        "gemini",
        httpx.MockTransport(handler),
    )
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id))
    assert result.source == "rules" and attempt.category == category
    assert attempt.http_status is None and attempt.provider_code is None


@pytest.mark.parametrize("status", [200, 404])
def test_gemini_malformed_encoded_response_preserves_status(session, status):
    result = investigate(
        session,
        session.scalar(select(Anomaly)),
        Settings(_env_file=None, gemini_api_key="test-key"),
        "gemini",
        httpx.MockTransport(
            lambda _: httpx.Response(
                status, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"broken")
            )
        ),
    )
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id))
    assert result.source == "rules" and attempt.http_status == status
    assert attempt.category == ("invalid_response" if status == 200 else "model_unavailable")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "quota"}),
        httpx.Response(200, json={"candidates": []}),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": '{"summary": "invalid"}'}]}}
                ]
            },
        ),
    ],
)
def test_invalid_gemini_falls_back_without_exposing_response(session, response):
    anomaly = session.scalar(select(Anomaly))
    result = investigate(
        session,
        anomaly,
        Settings(_env_file=None, gemini_api_key="test-key"),
        "gemini",
        httpx.MockTransport(lambda _: response),
    )
    assert result.source == "rules"
    assert result.fallback_reason == "gemini_failed_or_invalid_response"
    attempt = session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id))
    assert attempt.http_status == response.status_code
    assert attempt.category == ("quota_exceeded" if response.status_code == 429 else "invalid_response")


def test_gemini_without_key_uses_explicit_rules_fallback(session):
    result = investigate(
        session, session.scalar(select(Anomaly)), Settings(_env_file=None, gemini_api_key=""), "gemini"
    )
    assert result.source == "rules" and result.fallback_reason == "gemini_not_configured"
    assert session.scalar(select(GeminiAttempt).where(GeminiAttempt.analysis_id == result.id)) is None


def test_smtp_missing_config_stops_after_three_attempts(session):
    anomaly = session.scalar(
        select(Anomaly)
        .where(Anomaly.severity == "critical", Anomaly.rule_detected)
        .order_by(Anomaly.id.desc())
    )
    settings = Settings(_env_file=None, notification_mode="smtp", smtp_host="", smtp_from="", smtp_to="")
    for _ in range(3):
        run = run_automation(session, settings, [anomaly.id])
        assert run.failed == 1
    run = run_automation(session, settings, [anomaly.id])
    assert run.failed == 0 and run.processed == 0
    notification = session.scalar(
        select(Notification).where(Notification.anomaly_id == anomaly.id, Notification.mode == "smtp")
    )
    assert notification.attempts == 3


def test_smtp_connection_failure_is_retried_before_message_submission(session):
    anomaly = session.scalar(select(Anomaly).where(Anomaly.severity == "critical", Anomaly.rule_detected))
    settings = Settings(
        _env_file=None,
        notification_mode="smtp",
        smtp_host="smtp.example.invalid",
        smtp_from="demo@example.invalid",
        smtp_to="demo@example.invalid",
    )
    with patch("backend.app.automation.smtplib.SMTP", side_effect=OSError("offline")) as smtp:
        for _ in range(3):
            assert run_automation(session, settings, [anomaly.id]).failed == 1
        assert run_automation(session, settings, [anomaly.id]).processed == 0
        assert smtp.call_count == 3
    notification = session.scalar(
        select(Notification).where(Notification.anomaly_id == anomaly.id, Notification.mode == "smtp")
    )
    assert notification.status == "failed" and notification.attempts == 3


def test_ambiguous_smtp_failure_is_not_retried(session):
    anomaly = session.scalars(
        select(Anomaly)
        .where(Anomaly.severity == "critical", Anomaly.rule_detected)
        .order_by(Anomaly.id.desc())
        .offset(1)
        .limit(1)
    ).one()
    settings = Settings(
        _env_file=None,
        notification_mode="smtp",
        smtp_host="smtp.example.invalid",
        smtp_from="demo@example.invalid",
        smtp_to="demo@example.invalid",
    )
    with patch("backend.app.automation.deliver_smtp", side_effect=OSError("connection lost")) as deliver:
        assert run_automation(session, settings, [anomaly.id]).failed == 1
        assert run_automation(session, settings, [anomaly.id]).failed == 0
        assert deliver.call_count == 1
    notification = session.scalar(
        select(Notification).where(Notification.anomaly_id == anomaly.id, Notification.mode == "smtp")
    )
    assert notification.status == "unknown"
