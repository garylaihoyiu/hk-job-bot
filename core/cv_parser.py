import io
import json
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

_CV_SYSTEM_PROMPT = (
    "You are a CV parser. Extract structured information and return ONLY valid JSON with keys: "
    "job_titles (list of strings), skills (list of strings), experience_years (integer), "
    "education (string), languages (list of strings). "
    "No explanation, no markdown, no preamble."
)


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
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _CV_SYSTEM_PROMPT},
                {"role": "user", "content": cv_text[:8000]},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        json.loads(raw)  # validate — raises JSONDecodeError if invalid
        return raw
    except json.JSONDecodeError:
        logger.warning("Groq returned invalid JSON for CV parsing")
        return None
    except Exception as e:
        logger.error(f"Groq CV parsing error: {e}")
        raise
