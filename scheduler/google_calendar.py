# ============================================================
# scheduler/google_calendar.py — Google Calendar Integration
# ============================================================
# Creates calendar events with Google Meet links for interviews.
# Uses OAuth credentials from .env.  If credentials are absent,
# runs in *mock mode* — generates a fake meeting link and logs
# the event so the full pipeline remains functional.
# ============================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.config import settings
from utils.logger import logger

__all__ = ["CalendarService", "get_calendar_service"]


class CalendarService:
    """Google Calendar service with graceful mock mode."""

    def __init__(self):
        self._service = None
        self._is_mock = False

        # Prefer dedicated Calendar token; fall back to shared token
        cal_token = settings.calendar_refresh_token or settings.google_refresh_token
        if settings.google_client_id and settings.google_client_secret and cal_token:
            try:
                self._service = self._build_service(cal_token)
                # Verify the credentials actually work
                self._service.calendarList().list().execute()
                logger.event("calendar_init", backend="google_calendar")
            except Exception as exc:
                logger.event("calendar_init_error", level=30, error=str(exc))
                self._is_mock = True
                logger.event("calendar_init", backend="mock", reason="Calendar init failed")
        else:
            self._is_mock = True
            logger.event("calendar_init", backend="mock", reason="Google OAuth creds not set")

    def _build_service(self, refresh_token: str = ""):
        """Build the Google Calendar API service."""
        from google.oauth2 import credentials
        from googleapiclient.discovery import build

        token = credentials.Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        return build("calendar", "v3", credentials=token)

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_interview_event(
        self,
        candidate_name: str,
        candidate_email: str,
        start_time: Optional[datetime] = None,
        duration_minutes: int | None = None,
        interviewer_email: str = "",
    ) -> dict[str, Any]:
        """
        Create a calendar event for an interview.

        Returns dict with:
            event_id, start, end, meeting_link, mock (bool)
        """
        duration = duration_minutes or settings.interview_duration_minutes
        if start_time is None:
            start_time = self._find_next_slot(duration)

        end_time = start_time + timedelta(minutes=duration)

        if self._is_mock:
            return self._mock_event(candidate_name, candidate_email, start_time, end_time)

        try:
            event = {
                "summary": f"Interview: {candidate_name}",
                "description": (
                    f"Interview with {candidate_name} ({candidate_email}).\n"
                    f"Automatically scheduled by AI Recruitment Platform."
                ),
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                },
                "attendees": self._build_attendees(candidate_email, interviewer_email),
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"interview-{candidate_email}-{int(start_time.timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 24 * 60},
                        {"method": "popup", "minutes": 15},
                    ],
                },
            }

            created = (
                self._service.events()
                .insert(
                    calendarId=settings.calendar_id,
                    body=event,
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute()
            )

            meeting_link = ""
            if "conferenceData" in created:
                for entry in created["conferenceData"].get("entryPoints", []):
                    if entry.get("entryPointType") == "video":
                        meeting_link = entry.get("uri", "")
                        break

            logger.event(
                "interview_scheduled",
                event_id=created.get("id"),
                candidate=candidate_name,
                start=start_time.isoformat(),
                meeting_link=meeting_link,
            )

            return {
                "event_id": created.get("id"),
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "meeting_link": meeting_link,
                "mock": False,
            }

        except Exception as exc:
            logger.event("calendar_error", level=40, error=str(exc))
            return self._mock_event(candidate_name, candidate_email, start_time, end_time, error=str(exc))

    def _find_next_slot(self, duration_minutes: int) -> datetime:
        """Find the next available business-hours slot (mock heuristic)."""
        now = datetime.now(timezone.utc)
        # Move to next 9 AM–5 PM slot on a weekday
        candidate = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        while candidate.weekday() >= 5:  # skip Sat/Sun
            candidate += timedelta(days=1)
        return candidate

    def _build_attendees(
        self, candidate_email: str, interviewer_email: str
    ) -> list[dict[str, str]]:
        attendees = [{"email": candidate_email}]
        if interviewer_email:
            attendees.append({"email": interviewer_email})
        return attendees

    def _mock_event(
        self,
        candidate_name: str,
        candidate_email: str,
        start_time: datetime,
        end_time: datetime,
        error: str = "",
    ) -> dict[str, Any]:
        """Generate a mock event for demo/testing mode."""
        import uuid

        meeting_link = f"https://meet.google.com/mock-{uuid.uuid4().hex[:8]}"
        event_id = f"mock_{uuid.uuid4().hex[:12]}"

        logger.event(
            "interview_scheduled_mock",
            event_id=event_id,
            candidate=candidate_name,
            start=start_time.isoformat(),
            meeting_link=meeting_link,
            error=error,
        )

        return {
            "event_id": event_id,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "meeting_link": meeting_link,
            "mock": True,
        }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_calendar_service: Optional[CalendarService] = None


def get_calendar_service() -> CalendarService:
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service
