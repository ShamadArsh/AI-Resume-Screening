# ============================================================
# parser/pdf_parser.py — PDF Resume Text Extraction
# ============================================================
# Uses PyMuPDF (fitz) as the primary engine (fast, reliable)
# and pdfplumber as a fallback for complex layouts.
# ============================================================

from __future__ import annotations

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber

from utils.logger import logger


def extract_text_pymupdf(file_path: str | Path) -> str:
    """Extract text via PyMuPDF — primary engine."""
    text_parts: list[str] = []
    with fitz.open(str(file_path)) as doc:
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text:
                text_parts.append(text)
            logger.struct(
                logger.level if hasattr(logger, "level") else 20,
                "PDF page parsed",
                engine="pymupdf",
                page=page_num,
                chars=len(text),
            )
    return "\n".join(text_parts).strip()


def extract_text_pdfplumber(file_path: str | Path) -> str:
    """Extract text via pdfplumber — fallback engine."""
    text_parts: list[str] = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text:
                text_parts.append(text)
            logger.struct(
                20,
                "PDF page parsed",
                engine="pdfplumber",
                page=page_num,
                chars=len(text),
            )
    return "\n".join(text_parts).strip()


def parse_pdf(file_path: str | Path) -> str:
    """
    Parse a PDF resume and return extracted text.
    Tries PyMuPDF first; falls back to pdfplumber if the result
    is too short (possible scanned/image PDF).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    logger.event("pdf_parse_start", file=str(path))

    text = ""
    try:
        text = extract_text_pymupdf(path)
    except Exception as exc:
        logger.event("pdf_parse_error", level=40, engine="pymupdf", error=str(exc))

    # Fallback if PyMuPDF returned very little text
    if len(text) < 50:
        logger.event("pdf_parse_fallback", reason="low_text_from_pymupdf", chars=len(text))
        try:
            text = extract_text_pdfplumber(path)
        except Exception as exc:
            logger.event("pdf_parse_error", level=40, engine="pdfplumber", error=str(exc))

    if not text or len(text) < 10:
        raise ValueError(
            f"Could not extract text from PDF. The file may be a scanned image. Path: {path}"
        )

    logger.event("pdf_parse_done", file=str(path), chars=len(text))
    return text
