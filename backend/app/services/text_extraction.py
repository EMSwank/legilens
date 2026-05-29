"""Pure text extraction from LegiScan getBillText document bytes.

LegiScan returns Colorado bill text as base64-encoded PDFs (mime
"application/pdf"), not UTF-8 text. This module is the single home for
document-format decoding; pypdf is imported only here.

extract_text is a pure function: bytes + mime in, text or None out. No
network, no DB. The orchestrator (worker.tasks.fetch_bill_texts._fetch_one)
logs the mime + reason when this returns None.
"""
import io
import logging

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text(raw: bytes, mime: str) -> str | None:
    """Extract plain text from document bytes, dispatching on mime type.

    - "application/pdf", or bytes starting with the %PDF magic -> pypdf
    - "text/*" or empty mime -> utf-8 decode
    - anything else -> None

    Returns stripped text, or None when extraction yields nothing or fails.
    """
    m = (mime or "").lower()
    if m == "application/pdf" or raw[:5] == b"%PDF-":
        return _extract_pdf(raw)
    if m.startswith("text/") or m == "":
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return text.strip() or None
    return None


def _extract_pdf(raw: bytes) -> str | None:
    # Any pypdf failure -> no text, never crash the batch.
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    return text.strip() or None
