# ============================================================
# tests/test_api.py — Integration tests for FastAPI endpoints
# ============================================================

import pytest
from fastapi.testclient import TestClient

from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status(self, client):
        data = resp = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_has_config(self, client):
        data = client.get("/health").json()
        assert "config" in data
        assert "gemini_configured" in data["config"]


class TestStatsEndpoint:
    def test_stats_returns_200(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_stats_fields(self, client):
        data = client.get("/stats").json()
        assert "total_candidates" in data
        assert "shortlisted" in data
        assert "average_match_score" in data


class TestCandidateEndpoints:
    def test_get_nonexistent_candidate(self, client):
        resp = client.get("/candidate/nonexistent_id")
        assert resp.status_code == 404

    def test_list_candidates(self, client):
        resp = client.get("/candidates")
        assert resp.status_code == 200
        assert "candidates" in resp.json()


class TestParseResume:
    def test_unsupported_file_type(self, client):
        resp = client.post(
            "/parse_resume",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400


class TestOverrideEndpoint:
    def test_override_nonexistent(self, client):
        resp = client.put(
            "/candidate/nonexistent/override",
            json={"new_status": "Shortlisted"},
        )
        assert resp.status_code == 404
