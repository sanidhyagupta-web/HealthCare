"""Convert raw extracted text into structured Markdown.

Identifies common medical document sections and formats them
with Markdown headers, improving downstream chunking quality.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Known medical section headers (case-insensitive)
_SECTION_PATTERNS = [
    r"chief\s+complaint",
    r"history\s+of\s+present\s+illness",
    r"hpi",
    r"past\s+medical\s+history",
    r"pmh",
    r"medications?",
    r"allergies?",
    r"review\s+of\s+systems",
    r"ros",
    r"physical\s+examination",
    r"vital\s+signs?",
    r"assessment",
    r"diagnosis",
    r"diagnos[ei]s",
    r"plan",
    r"follow[- ]?up",
    r"lab(?:oratory)?\s+results?",
    r"imaging",
    r"procedure\s+notes?",
    r"discharge\s+summary",
    r"social\s+history",
    r"family\s+history",
    r"impression",
    r"recommendations?",
]

_SECTION_RE = re.compile(
    r"^(" + "|".join(_SECTION_PATTERNS) + r")[:\s]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _promote_to_header(text: str) -> str:
    """Wrap detected section titles as Markdown H2 headers."""
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        if _SECTION_RE.match(stripped):
            out.append(f"\n## {stripped.title()}\n")
        else:
            out.append(line)
    return "\n".join(out)


def convert_to_markdown(text: str, doc_id: str = "") -> str:
    """
    Convert plain text (from PDF/OCR) to structured Markdown.
    Steps:
      1. Normalise line endings
      2. Promote section headers to ## headings
      3. Collapse excessive blank lines
    """
    if not text.strip():
        logger.warning("Empty text passed for doc_id=%s", doc_id)
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _promote_to_header(text)
    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
