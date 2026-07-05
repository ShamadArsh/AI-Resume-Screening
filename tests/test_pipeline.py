# ============================================================
# tests/test_pipeline.py — Integration tests for the full pipeline
# ============================================================

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.api import app, run_full_pipeline
from database.airtable import CandidateRecord, get_repository


@pytest.fixture
def client():
    return TestClient(app)


class TestPipelineStoreAndScore:
    """Test the store + score portion of the pipeline (no Gemini needed)."""

    def test_store_candidate_in_mock_repo(self):
        repo = get_repository()
        record = CandidateRecord(
            candidate_name="Test Candidate",
            email="test@example.com",
            match_score=85,
            application_status="Shortlisted",
            skills=["Python", "FastAPI"],
        )
        record_id = repo.create(record)
        assert record_id  # non-empty ID

        # Retrieve
        fetched = repo.get_by_id(record_id)
        assert fetched is not None
        assert fetched.candidate_name == "Test Candidate"
        assert fetched.match_score == 85

    def test_update_candidate_status(self):
        repo = get_repository()
        record = CandidateRecord(
            candidate_name="Override Test",
            email="override@test.com",
            match_score=50,
            application_status="Rejected",
        )
        record_id = repo.create(record)

        updated = repo.update(record_id, {
            "Application Status": "Shortlisted",
            "Recruiter Notes": "Great portfolio override",
        })
        assert updated is not None
        assert updated.application_status == "Shortlisted"

    def test_list_candidates(self):
        repo = get_repository()
        records = repo.list_all()
        assert isinstance(records, list)


class TestN8nDelegationArchitecture:
    """Verify that the refactored architecture delegates to n8n, not schedulers."""

    def test_api_does_not_import_scheduler_modules(self):
        """FastAPI must NOT import gmail or google_calendar directly."""
        import backend.api as api_module
        import inspect

        source = inspect.getsource(api_module)
        # These imports must be gone after refactoring
        assert "from scheduler.gmail import" not in source, \
            "api.py still imports scheduler.gmail — should delegate to n8n"
        assert "from scheduler.google_calendar import" not in source, \
            "api.py still imports scheduler.google_calendar — should delegate to n8n"
        assert "get_email_service" not in source, \
            "api.py still calls get_email_service — should delegate to n8n"
        assert "get_calendar_service" not in source, \
            "api.py still calls get_calendar_service — should delegate to n8n"

    def test_api_imports_n8n_webhook(self):
        """FastAPI must import the n8n webhook module."""
        import backend.api as api_module
        import inspect

        source = inspect.getsource(api_module)
        assert "from backend.n8n_webhook import" in source, \
            "api.py must import from backend.n8n_webhook"
        assert "notify_n8n" in source, \
            "api.py must call notify_n8n to delegate workflow automation"

    @patch("backend.api.notify_n8n")
    def test_pipeline_calls_n8n_webhook(self, mock_notify, client):
        """run_full_pipeline must send candidate data to n8n webhook."""
        from database.airtable import CandidateRecord, get_repository

        repo = get_repository()
        record = CandidateRecord(
            candidate_name="Webhook Test",
            email="wh@test.com",
            match_score=90,
            application_status="Shortlisted",
        )
        record_id = repo.create(record)
        record.id = record_id

        # Simulate what run_full_pipeline does for the n8n delegation step
        from backend.api import _notify_n8n
        _notify_n8n(record)

        # notify_n8n was called with a WebhookPayload
        mock_notify.assert_called_once()

    @patch("backend.n8n_webhook.notify_n8n")
    def test_pipeline_survives_webhook_failure(self, mock_notify):
        """Pipeline must not crash even if webhook delivery fails."""
        from backend.n8n_webhook import WebhookPayload
        mock_notify.return_value = {"status": "failed", "detail": "n8n down"}

        from backend.n8n_webhook import get_client
        client = get_client()
        payload = WebhookPayload("Test", "t@t.com", "", 90, "Shortlisted")
        result = client.send(payload)
        # send() should return a dict, never raise
        assert isinstance(result, dict)


class TestAPIWorkflowViaClient:
    """Test API workflow integration via TestClient."""

    def test_health_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_n8n_flag(self, client):
        """Health endpoint should report n8n webhook config status."""
        resp = client.get("/health")
        data = resp.json()
        assert "n8n_webhook_configured" in data["config"]

    def test_full_candidate_lifecycle(self, client):
        """Create a candidate via repo, then fetch via API."""
        repo = get_repository()
        record = CandidateRecord(
            candidate_name="Lifecycle Test",
            email="lifecycle@test.com",
            phone="+1-555-000-1111",
            match_score=92,
            application_status="Shortlisted",
            skills=["Python", "Docker", "Kubernetes"],
            matching_skills=["Python", "Docker"],
            missing_skills=["Kubernetes"],
            ai_summary="Strong backend engineer with excellent Python skills.",
            recommendation="Strongly Recommended",
        )
        record_id = repo.create(record)

        # Fetch via API
        resp = client.get(f"/candidate/{record_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_name"] == "Lifecycle Test"
        assert data["match_score"] == 92

        # Override status via API
        resp = client.put(
            f"/candidate/{record_id}/override",
            json={"new_status": "Manual Review", "note": "Need second opinion"},
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "Manual Review"

    def test_stats_after_operations(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_candidates"] >= 0
