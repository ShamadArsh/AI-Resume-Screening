# ============================================================
# ai/jd_matcher.py — Job Description Matching via Gemini
# ============================================================
# Compares structured candidate data against a JD and returns
# match score, matching/missing skills, summary, recommendation.
# ============================================================

from __future__ import annotations

import json
from typing import Any

from ai.prompts import JD_MATCH_PROMPT
from ai.resume_parser import GeminiError, _generate
from backend.config import settings
from database.redis_cache import get_cache
from utils.logger import logger
from utils.validators import extract_json_from_text, validate_text_length

__all__ = ["match_resume_to_jd"]


def match_resume_to_jd(candidate_data: dict[str, Any], jd_text: str) -> dict[str, Any]:
    """
    Match a parsed candidate against a job description.

    Returns:
        match_score (int 0-100), matching_skills (list), missing_skills (list),
        relevant_experience (str), ai_summary (str), hiring_recommendation (str)
    """
    jd_text = validate_text_length(jd_text)
    candidate_json = json.dumps(candidate_data, ensure_ascii=False)

    # --- Cache check ---
    cache = get_cache()
    cache_key = cache.make_key("jd_match", candidate_json + jd_text)
    cached = cache.get(cache_key)
    if cached:
        logger.event("cache_hit", key=cache_key, scope="jd_match")
        return cached

    logger.event("cache_miss", key=cache_key, scope="jd_match")

    # --- Build prompt ---
    prompt = JD_MATCH_PROMPT.format(candidate_json=candidate_json, jd_text=jd_text)

    # --- Call Gemini ---
    raw = _generate(prompt)

    # --- Parse JSON ---
    parsed = extract_json_from_text(raw)
    if parsed is None or not isinstance(parsed, dict):
        logger.event("ai_json_parse_error", level=40, scope="jd_match", raw_preview=raw[:500])
        raise GeminiError("Failed to parse JD match response as JSON")

    # --- Normalise score to int ---
    try:
        parsed["match_score"] = int(parsed.get("match_score", 0))
    except (ValueError, TypeError):
        parsed["match_score"] = 0
    parsed["match_score"] = max(0, min(100, parsed["match_score"]))

    # --- Cache + return ---
    cache.set(cache_key, parsed, ttl=settings.cache_ttl)
    logger.event(
        "jd_match_done",
        score=parsed["match_score"],
        recommendation=parsed.get("hiring_recommendation"),
    )
    return parsed
