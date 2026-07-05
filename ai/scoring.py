# ============================================================
# ai/scoring.py — Business Rule Engine
# ============================================================
# Applies threshold-based business rules to the AI match score
# and determines the application status. Supports overrides.
# ============================================================

from __future__ import annotations

from enum import Enum
from typing import Any

from backend.config import settings
from utils.logger import logger

__all__ = ["ApplicationStatus", "determine_status", "apply_override"]


class ApplicationStatus(str, Enum):
    SHORTLISTED = "Shortlisted"
    MANUAL_REVIEW = "Manual Review"
    REJECTED = "Rejected"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    INTERVIEW_COMPLETED = "Interview Completed"
    HIRED = "Hired"
    OVERRIDDEN = "Overridden"


def determine_status(match_score: int) -> ApplicationStatus:
    """
    Apply business rules:
        >= 80  → Shortlisted
        60-79  → Manual Review
        < 60   → Rejected
    """
    score = max(0, min(100, int(match_score)))

    if score >= settings.shortlist_threshold:
        status = ApplicationStatus.SHORTLISTED
    elif score >= settings.review_threshold:
        status = ApplicationStatus.MANUAL_REVIEW
    else:
        status = ApplicationStatus.REJECTED

    logger.event(
        "status_determined",
        score=score,
        status=status.value,
        shortlist_threshold=settings.shortlist_threshold,
        review_threshold=settings.review_threshold,
    )
    return status


def apply_override(
    current_status: ApplicationStatus | str,
    new_status: ApplicationStatus | str,
    recruiter: str = "",
    note: str = "",
) -> ApplicationStatus:
    """
    Allow a recruiter to override the AI-determined status.
    Returns the new status, logged as overridden.
    """
    new = ApplicationStatus(new_status) if isinstance(new_status, str) else new_status
    logger.event(
        "status_overridden",
        from_status=str(current_status),
        to_status=new.value,
        recruiter=recruiter,
        note=note,
    )
    return new
