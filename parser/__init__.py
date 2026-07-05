# ============================================================
# parser/__init__.py — Unified Resume Parser
# ============================================================
# Auto-detects file type and routes to the correct parser.
# ============================================================

from __future__ import annotations

from pathlib import Path

from utils.logger import logger
from utils.validators import validate_file_extension, validate_file_size

from .docx_parser import parse_docx
from .pdf_parser import parse_pdf

__all__ = ["parse_resume_file", "parse_resume_bytes"]


def parse_resume_file(file_path: str | Path) -> str:
    """
    Parse a resume file from disk. Auto-detects PDF or DOCX.
    Returns extracted plain text.
    """
    file_path = Path(file_path)
    ext = validate_file_extension(file_path.name)

    logger.event("resume_parse_start", file=str(file_path), ext=ext)

    if ext == ".pdf":
        text = parse_pdf(file_path)
    elif ext == ".docx":
        text = parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported extension: {ext}")

    logger.event("resume_parse_done", file=str(file_path), chars=len(text))
    return text


def parse_resume_bytes(filename: str, file_bytes: bytes) -> str:
    """
    Parse a resume from raw bytes. Saves to temp, parses, removes.
    Returns extracted plain text.
    """
    validate_file_size(file_bytes)
    ext = validate_file_extension(filename)

    from backend.config import UPLOAD_DIR

    safe_name = f"upload_{Path(filename).stem}{ext}"
    temp_path = UPLOAD_DIR / safe_name
    temp_path.write_bytes(file_bytes)

    try:
        return parse_resume_file(temp_path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
