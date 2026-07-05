# ============================================================
# utils/validators.py — Input Validation Utilities
# ============================================================
# File-type checks, email/phone validation, JSON repair.
# ============================================================

from __future__ import annotations

import json
import re
from pathlib import Path

# Allowed resume file extensions
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})

# Reasonable file-size guard (10 MB)
MAX_FILE_SIZE: int = 10 * 1024 * 1024

# Max text length sent to the LLM (~100k chars)
MAX_TEXT_LENGTH: int = 100_000

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{7,20}$")


class ValidationError(Exception):
    """Raised when user input fails validation."""


# ------------------------------------------------------------------
# File validators
# ------------------------------------------------------------------
def validate_file_extension(filename: str) -> str:
    """Return lowercased extension if allowed, else raise."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def validate_file_size(file_bytes: bytes) -> None:
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large ({len(file_bytes)} bytes). Max: {MAX_FILE_SIZE} bytes."
        )


def validate_file_path(path: str | Path) -> Path:
    """Ensure the path is inside the upload directory."""
    upload_dir = Path(__file__).resolve().parent.parent / "uploads"
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(upload_dir)
    except ValueError:
        raise ValidationError(f"Path outside upload directory: {path}")
    return resolved


# ------------------------------------------------------------------
# Text validators
# ------------------------------------------------------------------
def validate_text_length(text: str) -> str:
    if not text or not text.strip():
        raise ValidationError("Empty text provided.")
    if len(text) > MAX_TEXT_LENGTH:
        return text[:MAX_TEXT_LENGTH]
    return text


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email or ""))


def validate_phone(phone: str) -> bool:
    return bool(_PHONE_RE.match(phone or ""))


# ------------------------------------------------------------------
# JSON helpers (repair LLM output)
# ------------------------------------------------------------------
def extract_json_from_text(text: str) -> dict | list | None:
    """
    Extract JSON from text that may contain markdown fences or
    surrounding prose.  Returns parsed JSON or None.
    """
    if not text:
        return None
    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    # Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try to find first { ... } or [ ... ] block
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = cleaned.find(start_char)
        end = cleaned.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def sanitize_filename(filename: str) -> str:
    """Remove path separators / unsafe chars from a filename."""
    return re.sub(r"[^\w.\-]", "_", Path(filename).name)
