# ============================================================
# database/airtable.py — Airtable Repository Layer
# ============================================================
# Reads AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME
# from .env.  If credentials are missing the repository runs in
# *mock mode* — all writes/reads succeed against an in-memory
# store so the app remains fully functional for demos/tests.
# ============================================================

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import settings
from utils.logger import logger

__all__ = ["CandidateRepository", "get_repository", "CandidateRecord"]


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------
class CandidateRecord:
    """Flat representation of a candidate row in Airtable."""

    def __init__(self, **kwargs: Any):
        self.id: str = kwargs.get("id", "")
        self.candidate_name: str = kwargs.get("candidate_name", "")
        self.email: str = kwargs.get("email", "")
        self.phone: str = kwargs.get("phone", "")
        self.experience: str = kwargs.get("experience", "")
        self.skills: list[str] = kwargs.get("skills", [])
        self.match_score: int = kwargs.get("match_score", 0)
        self.matching_skills: list[str] = kwargs.get("matching_skills", [])
        self.missing_skills: list[str] = kwargs.get("missing_skills", [])
        self.ai_summary: str = kwargs.get("ai_summary", "")
        self.recommendation: str = kwargs.get("recommendation", "")
        self.application_status: str = kwargs.get("application_status", "")
        self.recruiter_notes: str = kwargs.get("recruiter_notes", "")
        self.interview_status: str = kwargs.get("interview_status", "")
        self.interview_date: str = kwargs.get("interview_date", "")
        self.interview_link: str = kwargs.get("interview_link", "")
        self.resume_text: str = kwargs.get("resume_text", "")
        self.created_time: str = kwargs.get("created_time", "")
        self.updated_time: str = kwargs.get("updated_time", "")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_airtable(cls, record_id: str, fields: dict[str, Any]) -> "CandidateRecord":
        """Build a CandidateRecord from an Airtable record's fields dict."""
        return cls(
            id=record_id,
            candidate_name=fields.get("Candidate Name", ""),
            email=fields.get("Email", ""),
            phone=fields.get("Phone", ""),
            experience=fields.get("Experience", ""),
            skills=fields.get("Skills", "").split(", ") if isinstance(fields.get("Skills"), str) else fields.get("Skills", []),
            match_score=fields.get("Match Score", 0),
            matching_skills=fields.get("Matching Skills", "").split(", ") if isinstance(fields.get("Matching Skills"), str) else fields.get("Matching Skills", []),
            missing_skills=fields.get("Missing Skills", "").split(", ") if isinstance(fields.get("Missing Skills"), str) else fields.get("Missing Skills", []),
            ai_summary=fields.get("AI Summary", ""),
            recommendation=fields.get("Recommendation", ""),
            application_status=fields.get("Application Status", ""),
            recruiter_notes=fields.get("Recruiter Notes", ""),
            interview_status=fields.get("Interview Status", ""),
            interview_date=fields.get("Interview Date", ""),
            interview_link=fields.get("Interview Link", ""),
            resume_text=fields.get("Resume Text", ""),
            created_time=fields.get("Created Time", ""),
            updated_time=fields.get("Updated Time", ""),
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        """Convert to Airtable field names."""
        raw = {
            "Candidate Name": self.candidate_name,
            "Email": self.email,
            "Phone": self.phone,
            "Experience": self.experience,
            "Skills": ", ".join(self.skills) if isinstance(self.skills, list) else self.skills,
            "Match Score": self.match_score,
            "Matching Skills": ", ".join(self.matching_skills) if isinstance(self.matching_skills, list) else self.matching_skills,
            "Missing Skills": ", ".join(self.missing_skills) if isinstance(self.missing_skills, list) else self.missing_skills,
            "AI Summary": self.ai_summary,
            "Recommendation": self.recommendation,
            "Application Status": self.application_status,
            "Recruiter Notes": self.recruiter_notes,
            "Interview Status": self.interview_status,
            "Interview Date": self.interview_date,
            "Interview Link": self.interview_link,
            "Resume Text": self.resume_text[:5000],   # Airtable cell limit
            "Created Time": self.created_time,
            "Updated Time": self.updated_time,
        }
        # Airtable rejects empty strings for typed fields (date, url, email, number).
        # Remove empty strings so Airtable treats them as unset.
        return {k: v for k, v in raw.items() if v not in ("", None)}


# ------------------------------------------------------------------
# Mock store (used when Airtable creds absent)
# ------------------------------------------------------------------
class _MockStore:
    """In-memory store mimicking Airtable for mock mode."""

    def __init__(self):
        self._records: dict[str, dict[str, Any]] = {}

    def create(self, fields: dict) -> tuple[str, dict]:
        record_id = f"rec{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        fields.setdefault("Created Time", now)
        fields["Updated Time"] = now
        self._records[record_id] = fields
        return record_id, fields

    def get(self, record_id: str) -> Optional[dict]:
        return self._records.get(record_id)

    def update(self, record_id: str, fields: dict) -> Optional[dict]:
        rec = self._records.get(record_id)
        if rec is None:
            return None
        rec.update(fields)
        rec["Updated Time"] = datetime.now(timezone.utc).isoformat()
        return rec

    def list_all(self) -> list[tuple[str, dict]]:
        return list(self._records.items())


# ------------------------------------------------------------------
# Repository
# ------------------------------------------------------------------
class CandidateRepository:
    """
    Repository layer for candidate data.

    Uses pyairtable when AIRTABLE_API_KEY + BASE_ID are present.
    Falls back to an in-memory mock store otherwise.
    """

    def __init__(self):
        self._mock: Optional[_MockStore] = None
        self._table = None
        self._is_mock = False

        if settings.airtable_api_key and settings.airtable_base_id:
            try:
                from pyairtable import Api
                api = Api(settings.airtable_api_key)
                self._table = api.table(
                    settings.airtable_base_id,
                    settings.airtable_table_name,
                )
                logger.event(
                    "db_init",
                    backend="airtable",
                    base=settings.airtable_base_id,
                    table=settings.airtable_table_name,
                )
            except Exception as exc:
                logger.event("db_init_error", level=40, backend="airtable", error=str(exc))
                self._init_mock()
        else:
            self._init_mock()

    def _init_mock(self):
        self._mock = _MockStore()
        self._is_mock = True
        logger.event("db_init", backend="mock", reason="Airtable credentials not configured")

    # ---- helpers ----
    @property
    def is_mock(self) -> bool:
        return self._is_mock

    # ---- CRUD ----
    def create(self, record: CandidateRecord) -> str:
        """Insert a new candidate. Returns the record ID."""
        fields = record.to_airtable_fields()

        if self._is_mock:
            record_id, _ = self._mock.create(fields)
        else:
            result = self._table.create(fields)
            record_id = result["id"]
            logger.event("db_write", op="create", record_id=record_id)

        return record_id

    def get_by_id(self, record_id: str) -> Optional[CandidateRecord]:
        """Fetch a single candidate by ID."""
        if self._is_mock:
            fields = self._mock.get(record_id)
            if fields is None:
                return None
            return CandidateRecord.from_airtable(record_id, fields)

        try:
            result = self._table.get(record_id)
            return CandidateRecord.from_airtable(result["id"], result["fields"])
        except Exception as exc:
            logger.event("db_read_error", level=40, record_id=record_id, error=str(exc))
            return None

    def update(self, record_id: str, fields: dict[str, Any]) -> Optional[CandidateRecord]:
        """Update a candidate's fields. Returns updated record."""
        # Translate to Airtable field names if internal keys are passed
        temp = CandidateRecord(**{k.replace(" ", "_").lower(): v for k, v in fields.items()})
        airtable_fields = temp.to_airtable_fields()
        airtable_fields.update(fields)  # allow raw Airtable field names to pass through

        if self._is_mock:
            updated = self._mock.update(record_id, airtable_fields)
            if updated is None:
                return None
            return CandidateRecord.from_airtable(record_id, updated)

        result = self._table.update(record_id, airtable_fields)
        logger.event("db_write", op="update", record_id=record_id)
        return CandidateRecord.from_airtable(result["id"], result["fields"])

    def list_all(self) -> list[CandidateRecord]:
        """Return all candidates."""
        if self._is_mock:
            return [
                CandidateRecord.from_airtable(rid, fields)
                for rid, fields in self._mock.list_all()
            ]

        results = self._table.all()
        return [CandidateRecord.from_airtable(r["id"], r["fields"]) for r in results]


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_repo_instance: Optional[CandidateRepository] = None


def get_repository() -> CandidateRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = CandidateRepository()
    return _repo_instance
