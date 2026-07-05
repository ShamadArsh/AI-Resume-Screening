# ============================================================
# tests/test_scoring.py — Unit tests for business rule engine
# ============================================================

import pytest
from ai.scoring import ApplicationStatus, apply_override, determine_status


class TestDetermineStatus:
    def test_score_80_shortlisted(self):
        assert determine_status(80) == ApplicationStatus.SHORTLISTED

    def test_score_95_shortlisted(self):
        assert determine_status(95) == ApplicationStatus.SHORTLISTED

    def test_score_100_shortlisted(self):
        assert determine_status(100) == ApplicationStatus.SHORTLISTED

    def test_score_79_review(self):
        assert determine_status(79) == ApplicationStatus.MANUAL_REVIEW

    def test_score_60_review(self):
        assert determine_status(60) == ApplicationStatus.MANUAL_REVIEW

    def test_score_59_rejected(self):
        assert determine_status(59) == ApplicationStatus.REJECTED

    def test_score_0_rejected(self):
        assert determine_status(0) == ApplicationStatus.REJECTED

    def test_score_over_100_clamped(self):
        assert determine_status(150) == ApplicationStatus.SHORTLISTED

    def test_score_negative_clamped(self):
        assert determine_status(-10) == ApplicationStatus.REJECTED


class TestApplyOverride:
    def test_override_to_shortlisted(self):
        result = apply_override(
            ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED
        )
        assert result == ApplicationStatus.SHORTLISTED

    def test_override_with_string(self):
        result = apply_override("Rejected", "Manual Review")
        assert result == ApplicationStatus.MANUAL_REVIEW

    def test_override_invalid_status(self):
        with pytest.raises(ValueError):
            apply_override("Rejected", "Nonexistent")
