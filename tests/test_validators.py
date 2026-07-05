# ============================================================
# tests/test_validators.py — Unit tests for input validation
# ============================================================

import pytest
from utils.validators import (
    ValidationError,
    extract_json_from_text,
    sanitize_filename,
    validate_email,
    validate_file_extension,
    validate_file_size,
    validate_phone,
    validate_text_length,
)


class TestFileExtension:
    def test_pdf_accepted(self):
        assert validate_file_extension("resume.pdf") == ".pdf"

    def test_docx_accepted(self):
        assert validate_file_extension("resume.docx") == ".docx"

    def test_uppercase_accepted(self):
        assert validate_file_extension("RESUME.PDF") == ".pdf"

    def test_doc_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported"):
            validate_file_extension("resume.doc")

    def test_txt_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported"):
            validate_file_extension("notes.txt")

    def test_no_extension_rejected(self):
        with pytest.raises(ValidationError):
            validate_file_extension("resume")


class TestFileSize:
    def test_small_file_ok(self):
        validate_file_size(b"small")  # should not raise

    def test_large_file_rejected(self):
        big = b"x" * (11 * 1024 * 1024)
        with pytest.raises(ValidationError, match="too large"):
            validate_file_size(big)


class TestTextLength:
    def test_normal_text(self):
        assert validate_text_length("hello world") == "hello world"

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="Empty"):
            validate_text_length("")

    def test_whitespace_rejected(self):
        with pytest.raises(ValidationError, match="Empty"):
            validate_text_length("   ")

    def test_truncation(self):
        long = "a" * 200_000
        result = validate_text_length(long)
        assert len(result) == 100_000


class TestEmailPhone:
    def test_valid_email(self):
        assert validate_email("user@example.com") is True

    def test_invalid_email(self):
        assert validate_email("not-an-email") is False

    def test_valid_phone(self):
        assert validate_phone("+1-555-123-4567") is True

    def test_short_phone(self):
        assert validate_phone("123") is False


class TestJsonExtraction:
    def test_clean_json(self):
        assert extract_json_from_text('{"name": "Alice"}') == {"name": "Alice"}

    def test_markdown_fenced(self):
        text = "```json\n{\"name\": \"Bob\"}\n```"
        assert extract_json_from_text(text) == {"name": "Bob"}

    def test_json_with_prose(self):
        text = 'Here is the data:\n{"name": "Carol", "age": 30}\nDone.'
        assert extract_json_from_text(text) == {"name": "Carol", "age": 30}

    def test_json_array(self):
        text = 'Result: [1, 2, 3]'
        assert extract_json_from_text(text) == [1, 2, 3]

    def test_empty(self):
        assert extract_json_from_text("") is None

    def test_no_json(self):
        assert extract_json_from_text("no json here") is None


class TestSanitizeFilename:
    def test_clean_name(self):
        assert sanitize_filename("resume.pdf") == "resume.pdf"

    def test_path_separators(self):
        # Path().name strips directory components — only basename survives
        assert sanitize_filename("../etc/passwd") == "passwd"

    def test_spaces(self):
        assert sanitize_filename("my resume.pdf") == "my_resume.pdf"
