# ============================================================
# ai/resume_parser.py — Gemini-Powered Resume Extraction
# ============================================================
# Uses Gemini 2.5 Flash to extract structured candidate info
# from raw resume text. Includes caching + retry logic.
# ============================================================

from __future__ import annotations

import json
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai.prompts import RESUME_EXTRACTION_PROMPT
from backend.config import settings
from database.redis_cache import get_cache
from utils.logger import logger
from utils.validators import extract_json_from_text

__all__ = ["parse_resume_with_ai", "GeminiError"]


class GeminiError(Exception):
    """Raised when Gemini fails after all retries."""


# ------------------------------------------------------------------
# Gemini client (lazy-init so missing key doesn't crash import)
# ------------------------------------------------------------------
_client = None


def _get_client():
    """Lazily initialise the google-genai client."""
    global _client
    if _client is not None:
        return _client
    if not settings.gemini_api_key:
        raise GeminiError(
            "GEMINI_API_KEY is not set. Add it to .env to enable AI parsing."
        )
    try:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
        logger.event("gemini_client_init", model=settings.gemini_model)
        return _client
    except ImportError:
        raise GeminiError(
            "google-genai package not installed. Run: pip install google-genai"
        )
    except Exception as exc:
        raise GeminiError(f"Failed to init Gemini client: {exc}")


# ------------------------------------------------------------------
# Core generation call with retry
# ------------------------------------------------------------------
@retry(
    retry=retry_if_exception_type((TimeoutError, ConnectionError, GeminiError)),
    stop=stop_after_attempt(settings.gemini_max_retries),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _generate(prompt: str) -> str:
    """Send prompt to Gemini and return raw text response."""
    client = _get_client()

    logger.event(
        "ai_request",
        model=settings.gemini_model,
        prompt_chars=len(prompt),
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = response.text
        logger.event("ai_response", model=settings.gemini_model, response_chars=len(text))
        return text
    except Exception as exc:
        logger.event("ai_request_error", level=40, error=str(exc))
        raise GeminiError(f"Gemini generation failed: {exc}") from exc


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def parse_resume_with_ai(resume_text: str) -> dict[str, Any]:
    """
    Extract structured candidate data from resume text via Gemini 2.5 Flash.

    Returns a dict with keys: name, email, phone, experience, education,
    skills, certifications, projects, languages, current_company, current_role.
    """
    from utils.validators import validate_text_length
    resume_text = validate_text_length(resume_text)

    # --- Cache check ---
    cache = get_cache()
    cache_key = cache.make_key("resume_parse", resume_text)
    cached = cache.get(cache_key)
    if cached:
        logger.event("cache_hit", key=cache_key, scope="resume_parse")
        return cached

    logger.event("cache_miss", key=cache_key, scope="resume_parse")

    # --- Build prompt ---
    prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=resume_text)

    # --- Call Gemini ---
    raw = _generate(prompt)

    # --- Parse JSON ---
    parsed = extract_json_from_text(raw)
    if parsed is None or not isinstance(parsed, dict):
        logger.event("ai_json_parse_error", level=40, raw_preview=raw[:500])
        raise GeminiError("Failed to parse Gemini response as JSON")

    # --- Cache + return ---
    cache.set(cache_key, parsed, ttl=settings.cache_ttl)
    logger.event("resume_extracted", name=parsed.get("name"), skills=len(parsed.get("skills", [])))
    return parsed
