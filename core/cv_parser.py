import io
import json
import logging
from openai import AsyncOpenAI
from config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

_CV_SYSTEM_PROMPT = (
    "You are a CV parser. Extract structured information and return ONLY valid JSON with keys: "
    "job_titles (list of strings), skills (list of strings), experience_years (integer), "
    "education (string), languages (list of strings). "
    "No explanation, no markdown, no preamble."
)

_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif filename_lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def _extract_pdf(file_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


async def parse_cv_with_groq(cv_text: str) -> str | None:
    """Returns profile JSON string, or None if parsing fails."""
    try:
        response = await _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _CV_SYSTEM_PROMPT},
                {"role": "user", "content": cv_text[:8000]},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        json.loads(raw)  # validate — raises JSONDecodeError if invalid
        return raw
    except json.JSONDecodeError:
        logger.warning("AI returned invalid JSON for CV parsing")
        return None
    except Exception as e:
        logger.error(f"AI CV parsing error: {e}")
        raise
