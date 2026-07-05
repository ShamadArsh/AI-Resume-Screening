# ============================================================
# tests/test_n8n_webhook.py — Tests for the n8n webhook client
# ============================================================

import pytest
from unittest.mock import patch, MagicMock

from backend.n8n_webhook import N8nWebhookClient, WebhookPayload, notify_n8n


class TestWebhookPayload:
    """Test the typed payload model."""

    def test_payload_construction(self):
        payload = WebhookPayload(
            candidate_name="Jane Smith",
            email="jane@example.com",
            phone="+1-555-0100",
            match_score=92,
            application_status="Shortlisted",
            candidate_id="rec123",
            skills=["Python", "FastAPI"],
            matching_skills=["Python"],
            missing_skills=["Celery"],
            ai_summary="Strong candidate",
            recommendation="Strongly Recommended",
        )
        d = payload.to_dict()
        assert d["candidate_name"] == "Jane Smith"
        assert d["email"] == "jane@example.com"
        assert d["match_score"] == 92
        assert d["application_status"] == "Shortlisted"
        assert d["candidate_id"] == "rec123"
        assert d["skills"] == ["Python", "FastAPI"]
        assert d["matching_skills"] == ["Python"]
        assert d["missing_skills"] == ["Celery"]

    def test_payload_defaults(self):
        payload = WebhookPayload(
            candidate_name="Test",
            email="test@test.com",
            phone="",
            match_score=50,
            application_status="Rejected",
        )
        d = payload.to_dict()
        assert d["skills"] == []
        assert d["matching_skills"] == []
        assert d["missing_skills"] == []
        assert d["candidate_id"] == ""
        assert d["ai_summary"] == ""
        assert d["recommendation"] == ""

    def test_required_fields_in_dict(self):
        """Spec requires these exact keys in the payload."""
        payload = WebhookPayload(
            candidate_name="John",
            email="john@test.com",
            phone="+1-555-0000",
            match_score=85,
            application_status="Shortlisted",
        )
        d = payload.to_dict()
        required_keys = {"candidate_name", "email", "phone", "match_score", "application_status"}
        assert required_keys.issubset(set(d.keys()))


class TestN8nWebhookClient:
    """Test the webhook client behavior."""

    def test_skipped_when_not_configured(self):
        """Pipeline must NOT break when webhook URL is empty."""
        client = N8nWebhookClient(webhook_url="")
        assert not client.is_configured
        payload = WebhookPayload("Test", "t@t.com", "", 90, "Shortlisted")
        result = client.send(payload)
        assert result["status"] == "skipped"

    def test_is_configured_true(self):
        client = N8nWebhookClient(webhook_url="http://localhost:5678/webhook/interview")
        assert client.is_configured is True

    def test_is_configured_false_explicit_empty(self):
        client = N8nWebhookClient(webhook_url="")
        assert client.is_configured is False

    @patch("backend.n8n_webhook.httpx.post")
    def test_send_success(self, mock_post):
        """Successful webhook call returns status=sent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = N8nWebhookClient(webhook_url="http://localhost:5678/webhook/interview")
        payload = WebhookPayload("Jane", "jane@test.com", "", 95, "Shortlisted", candidate_id="rec1")
        result = client.send(payload)

        assert result["status"] == "sent"
        assert "200" in result["detail"]
        mock_post.assert_called_once()

    @patch("backend.n8n_webhook.httpx.post")
    def test_send_fails_gracefully(self, mock_post):
        """Webhook failure must NOT raise — pipeline continues."""
        import httpx
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        client = N8nWebhookClient(webhook_url="http://localhost:5678/webhook/interview")
        payload = WebhookPayload("Jane", "jane@test.com", "", 95, "Shortlisted")
        result = client.send(payload)

        assert result["status"] == "failed"
        assert "failed" in result["detail"].lower()

    @patch("backend.n8n_webhook.httpx.post")
    def test_send_retries_on_error(self, mock_post):
        """Webhook must retry on connection error."""
        import httpx
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        client = N8nWebhookClient(webhook_url="http://localhost:5678/webhook/interview", max_retries=3)
        payload = WebhookPayload("Jane", "jane@test.com", "", 95, "Shortlisted")
        result = client.send(payload)

        # tenacity retries internally — should attempt multiple times
        assert mock_post.call_count >= 1
        assert result["status"] == "failed"

    @patch("backend.n8n_webhook.httpx.post")
    def test_headers_include_api_key_when_set(self, mock_post):
        """API key should be sent as header when configured."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = N8nWebhookClient(
            webhook_url="http://localhost:5678/webhook/interview",
            api_key="test-key-123",
        )
        payload = WebhookPayload("Test", "t@t.com", "", 80, "Shortlisted")
        client.send(payload)

        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
        assert headers.get("X-N8N-API-KEY") == "test-key-123"
