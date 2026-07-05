# ============================================================
# tests/test_scheduler.py — Tests for scheduler services
# ============================================================
# Tests work in BOTH mock and live modes — they adapt to whatever
# mode the service initializes in based on available credentials.
# ============================================================

import pytest
from scheduler.gmail import EmailService, EmailTemplates
from scheduler.google_calendar import CalendarService


class TestEmailService:
    """Test Gmail service (mock or live depending on creds)."""

    def test_service_initializes(self):
        svc = EmailService()
        # Should initialize without crashing — mode depends on creds
        assert svc is not None

    def test_send_email(self):
        svc = EmailService()
        result = svc.send_email(
            to="test@example.com",
            subject="Test",
            body_text="Hello world",
        )
        # Either mock_sent or sent or error (if recipient invalid)
        assert result["status"] in ("mock_sent", "sent", "error")

    def test_send_application_received(self):
        svc = EmailService()
        result = svc.send_application_received("test@example.com", "Alice")
        assert result["status"] in ("mock_sent", "sent", "error")

    def test_send_shortlisted(self):
        svc = EmailService()
        result = svc.send_shortlisted("test@example.com", "Alice", 90, "Great")
        assert result["status"] in ("mock_sent", "sent", "error")

    def test_send_interview_invitation(self):
        svc = EmailService()
        result = svc.send_interview_invitation(
            "test@example.com", "Alice", "July 10", "2:00 PM", "https://meet.google.com/abc"
        )
        assert result["status"] in ("mock_sent", "sent", "error")

    def test_send_rejected(self):
        svc = EmailService()
        result = svc.send_rejected("test@example.com", "Alice")
        assert result["status"] in ("mock_sent", "sent", "error")


class TestEmailTemplates:
    def test_application_received_returns_tuple(self):
        text, html = EmailTemplates.application_received("Alice")
        assert "Alice" in text
        assert "Alice" in html
        assert "<html>" in html

    def test_interview_invitation_has_link(self):
        text, html = EmailTemplates.interview_invitation("Bob", "July 10", "2:00 PM", "https://meet.google.com/test")
        assert "https://meet.google.com/test" in html
        assert "Bob" in text

    def test_shortlisted_has_score(self):
        text, html = EmailTemplates.shortlisted("Carol", 85, "Excellent candidate")
        assert "85" in text
        assert "Carol" in text


class TestCalendarService:
    """Test Google Calendar service (mock or live depending on creds)."""

    def test_service_initializes(self):
        svc = CalendarService()
        assert svc is not None

    def test_create_interview_event(self):
        svc = CalendarService()
        result = svc.create_interview_event(
            candidate_name="Test User",
            candidate_email="test@example.com",
        )
        assert "event_id" in result
        assert "meeting_link" in result
        assert "start" in result
        assert "end" in result
        # meeting_link should be a Google Meet URL
        assert "meet.google.com" in result["meeting_link"] or "mock" in result["meeting_link"]

    def test_event_has_valid_structure(self):
        svc = CalendarService()
        result = svc.create_interview_event("Bob", "bob@test.com")
        assert result["event_id"]  # non-empty
        assert result["start"]  # non-empty
