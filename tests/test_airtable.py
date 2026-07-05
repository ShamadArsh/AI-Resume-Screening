# ============================================================
# tests/test_airtable.py — Unit tests for Airtable mock repository
# ============================================================

import pytest
from database.airtable import CandidateRecord, CandidateRepository


class TestCandidateRecord:
    def test_create_empty(self):
        rec = CandidateRecord()
        assert rec.candidate_name == ""
        assert rec.match_score == 0

    def test_create_with_data(self):
        rec = CandidateRecord(
            candidate_name="Alice",
            email="alice@example.com",
            match_score=85,
            skills=["Python", "FastAPI"],
        )
        assert rec.candidate_name == "Alice"
        assert rec.match_score == 85

    def test_to_dict(self):
        rec = CandidateRecord(candidate_name="Bob", email="bob@test.com")
        d = rec.to_dict()
        assert d["candidate_name"] == "Bob"
        assert d["email"] == "bob@test.com"
