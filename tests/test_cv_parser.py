import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import json
import pytest
from unittest.mock import AsyncMock, patch
from core.cv_parser import extract_text_from_bytes, parse_cv_with_groq


def make_simple_pdf_bytes() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "John Doe\nSoftware Engineer\nPython Django PostgreSQL")
    return doc.tobytes()


def test_extract_text_from_pdf():
    pdf_bytes = make_simple_pdf_bytes()
    text = extract_text_from_bytes(pdf_bytes, "cv.pdf")
    assert "John Doe" in text
    assert "Python" in text


def test_extract_text_wrong_extension_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text_from_bytes(b"data", "image.jpg")


def _mock_response(content: str):
    return type("R", (), {
        "choices": [type("C", (), {
            "message": type("M", (), {"content": content})()
        })()]
    })()


@pytest.mark.asyncio
async def test_parse_cv_returns_valid_profile():
    mock_content = '{"job_titles": ["Software Engineer"], "skills": ["Python"], "experience_years": 3, "education": "BSc CS", "languages": ["English"]}'
    with patch("core.cv_parser.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response(mock_content))
        result = await parse_cv_with_groq("John Doe\nSoftware Engineer")
    assert result is not None
    data = json.loads(result)
    assert "skills" in data
    assert "job_titles" in data


@pytest.mark.asyncio
async def test_parse_cv_returns_none_on_bad_json():
    with patch("core.cv_parser.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response("not json at all"))
        result = await parse_cv_with_groq("some cv text")
    assert result is None
