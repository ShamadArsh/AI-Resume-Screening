# ============================================================
# tests/test_parsers.py — Unit tests for resume file parsers
# ============================================================

from pathlib import Path

import pytest

from parser.pdf_parser import parse_pdf
from parser.docx_parser import parse_docx


SAMPLE_RESUME_TEXT = """
Jane Smith
jane.smith@email.com
+1-555-987-6543

EXPERIENCE
Senior Software Engineer at Tech Corp (2020-Present)
Software Developer at Startup Inc (2017-2020)

SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Redis

EDUCATION
M.S. Computer Science, MIT, 2017
"""

SAMPLE_RESUME_PATH = Path("/workspace/tests/sample_resume.txt")


class TestFileParsers:
    """Integration tests for PDF and DOCX parsing."""

    def test_pdf_parser_missing_file(self):
        with pytest.raises(FileNotFoundError):
            parse_pdf("/nonexistent/file.pdf")

    def test_docx_parser_missing_file(self):
        with pytest.raises(FileNotFoundError):
            parse_docx("/nonexistent/file.docx")
