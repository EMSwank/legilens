# IST PDF Text Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project note:** The user mandates the `route-tasks` skill as the executor for this plan. Route each task through route-tasks; it will classify and dispatch (mechanical → local_llm, structural → local_llm draft + Agent review, judgment → Agent).

**Goal:** Make the LegiScan text-fetch and snippet-evidence pipelines extract real text from `getBillText` responses, which for Colorado are base64-encoded PDFs, so CO bills get `full_text` + MinHash signatures and snippet extraction stops dead-ending in ghosts.

**Architecture:** Add `LegiScanClient.get_bill_doc(doc_id) -> BillDoc{raw, mime}` (pure HTTP + base64, no content interpretation). Add a new pure module `app/services/text_extraction.py::extract_text(raw, mime)` that owns all format decoding (PDF via pypdf, utf-8 for text mimes) — pypdf is imported only there. Keep `get_bill_text_by_doc_id` as a thin wrapper over `get_bill_doc` + `extract_text` so the evidence worker is fixed with zero changes. `_fetch_one` switches to `get_bill_doc` directly so it can log the `mime` on permanent failure.

**Tech Stack:** Python 3, httpx (async), pypdf 6.12.2, SQLAlchemy async, pytest + pytest-asyncio (`asyncio_mode = "auto"`), unittest.mock.

**Spec:** `docs/superpowers/specs/2026-05-29-ist-pdf-text-extraction-design.md`

**Working directory for all commands:** `/Users/eliotswank/dev/legilens/backend`
**Branch:** `feat/ist-pdf-text-extraction` (already checked out)
**Python:** use the repo venv — `.venv/bin/python` and `.venv/bin/pytest`.

**Invariant / execution tripwire:** The 4 existing `get_bill_text_by_doc_id` tests in `tests/test_legiscan.py` and ALL tests in `tests/test_evidence.py` must stay green **without modification**. If any breaks, the wrapper changed observable behavior — stop and reconcile, do not edit those tests to fit.

---

## File Structure

- `backend/requirements.txt` — add `pypdf==6.12.2` (Task 1).
- `backend/app/services/text_extraction.py` — **new**, pure `extract_text(raw, mime) -> str | None`; sole home of pypdf (Task 2).
- `backend/tests/test_text_extraction.py` — **new**, extractor unit tests with embedded base64 PDF fixtures (Task 2).
- `backend/app/services/legiscan.py` — add `BillDoc` dataclass + `get_bill_doc`; rewrite `get_bill_text_by_doc_id` as a wrapper (Task 3).
- `backend/tests/test_legiscan.py` — add `get_bill_doc` tests + the required wrapper PDF test; keep 4 existing wrapper tests unchanged (Task 3).
- `backend/worker/tasks/fetch_bill_texts.py` — `_fetch_one` calls `get_bill_doc` + `extract_text`, logs mime on permanent failure (Task 4).
- `backend/tests/worker/test_fetch_bill_texts.py` — update mocks to `get_bill_doc`/`BillDoc`; add a garbage-PDF permanent test (Task 4).
- `backend/worker/tasks/evidence.py` — **unchanged**; fixed for free via the wrapper.

---

## Task 1: Add pypdf dependency

**Files:**
- Modify: `backend/requirements.txt` (insert after `pydantic_core==2.46.4`, before `python-dotenv==1.2.2`)

- [ ] **Step 1: Add the pinned dependency**

Edit `backend/requirements.txt`. Insert this line between `pydantic_core==2.46.4` and `python-dotenv==1.2.2` (keeps the file's alphabetical, pinned style):

```
pypdf==6.12.2
```

- [ ] **Step 2: Install into the venv**

Run: `.venv/bin/pip install pypdf==6.12.2`
Expected: `Successfully installed pypdf-6.12.2` (or "Requirement already satisfied" — it was used during planning).

- [ ] **Step 3: Verify the import resolves**

Run: `.venv/bin/python -c "import pypdf; print(pypdf.__version__)"`
Expected output: `6.12.2`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build(ist): add pypdf 6.12.2 for PDF text extraction

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Pure `text_extraction` module

**Files:**
- Create: `backend/app/services/text_extraction.py`
- Test: `backend/tests/test_text_extraction.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_text_extraction.py` with this exact content. The two base64 constants are minimal valid PDFs generated and verified against pypdf 6.12.2 during planning (`PDF_WITH_TEXT_B64` extracts `"Be it enacted by the General Assembly LegiLens"`; `PDF_NO_TEXT_B64` is a valid single blank page that extracts the empty string).

```python
import base64

from app.services.text_extraction import extract_text

# Minimal valid PDF with a text layer reading:
# "Be it enacted by the General Assembly LegiLens"
# Verified against pypdf 6.12.2.
PDF_WITH_TEXT_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
    "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
    "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
    "NzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4g"
    "Pj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA3NyA+PgpzdHJlYW0KQlQgL0YxIDI0IFRm"
    "IDcyIDcwMCBUZCAoQmUgaXQgZW5hY3RlZCBieSB0aGUgR2VuZXJhbCBBc3NlbWJseSBMZWdpTGVu"
    "cykgVGogRVQKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9TdWJ0eXBl"
    "IC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAw"
    "MCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAw"
    "MDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzNjggMDAwMDAgbiAKdHJh"
    "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0Y="
)

# Minimal valid PDF, single blank page, no text content stream.
# pypdf parses it successfully and extracts the empty string.
PDF_NO_TEXT_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
    "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
    "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
    "NzkyXSA+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAw"
    "MDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAp0cmFpbGVyCjw8"
    "IC9TaXplIDQgL1Jvb3QgMSAwIFIgPj4Kc3RhcnR4cmVmCjE4NgolJUVPRg=="
)


def _pdf_with_text() -> bytes:
    return base64.b64decode(PDF_WITH_TEXT_B64)


def _pdf_no_text() -> bytes:
    return base64.b64decode(PDF_NO_TEXT_B64)


def test_extract_pdf_returns_text():
    result = extract_text(_pdf_with_text(), "application/pdf")
    assert result is not None
    assert "enacted" in result


def test_extract_pdf_via_magic_bytes_when_mime_empty():
    # mime absent but bytes are a genuine PDF -> still routed to pypdf
    result = extract_text(_pdf_with_text(), "")
    assert result is not None
    assert "LegiLens" in result


def test_extract_pdf_no_text_layer_returns_none():
    assert extract_text(_pdf_no_text(), "application/pdf") is None


def test_extract_pdf_garbage_bytes_returns_none():
    assert extract_text(b"not a pdf at all", "application/pdf") is None


def test_extract_text_html_mime_decodes_utf8():
    assert extract_text(b"<html>hi</html>", "text/html") == "<html>hi</html>"


def test_extract_text_plain_mime_decodes_utf8():
    assert extract_text(b"plain bill text", "text/plain") == "plain bill text"


def test_extract_empty_mime_non_pdf_uses_utf8():
    assert extract_text(b"some legislative text", "") == "some legislative text"


def test_extract_text_invalid_utf8_returns_none():
    assert extract_text(b"\xff\xfe\x00 bad", "text/plain") is None


def test_extract_unknown_mime_returns_none():
    assert extract_text(b"PK\x03\x04zipdata", "application/zip") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_text_extraction.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'app.services.text_extraction'`.

- [ ] **Step 3: Write the module**

Create `backend/app/services/text_extraction.py` with this exact content:

```python
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
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:  # noqa: BLE001 - any pypdf failure -> no text, never crash the batch
        return None
    return text.strip() or None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_text_extraction.py -q`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/text_extraction.py tests/test_text_extraction.py
git commit -m "feat(ist): add pure text_extraction module (PDF via pypdf, utf-8 fallback)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `BillDoc` + `get_bill_doc` + wrapper in the client

**Files:**
- Modify: `backend/app/services/legiscan.py` (imports near line 1-4; add `BillDoc` after the module constants near line 7; replace `get_bill_text_by_doc_id` at lines 82-104)
- Test: `backend/tests/test_legiscan.py` (add new tests after the existing `get_bill_text_by_doc_id` tests; do NOT modify the 4 existing ones)

- [ ] **Step 1: Write the failing tests**

Append these tests to `backend/tests/test_legiscan.py` (after the last existing test, `test_get_bill_text_by_doc_id_raises_on_non_ok`). Do not touch the existing tests.

```python
async def test_get_bill_doc_returns_billdoc_with_mime(client):
    import base64 as b64
    from app.services.legiscan import BillDoc

    body = b"%PDF-1.4 minimal pdf bytes"
    encoded = b64.b64encode(body).decode("ascii")
    mock_response = {
        "status": "OK",
        "text": {"doc_id": 999, "doc": encoded, "mime": "application/pdf"},
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert isinstance(result, BillDoc)
    assert result.raw == body
    assert result.mime == "application/pdf"


async def test_get_bill_doc_defaults_mime_to_empty_when_absent(client):
    import base64 as b64
    from app.services.legiscan import BillDoc

    body = b"some bytes"
    encoded = b64.b64encode(body).decode("ascii")
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": encoded}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert isinstance(result, BillDoc)
    assert result.mime == ""


async def test_get_bill_doc_returns_none_on_empty_doc(client):
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": ""}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert result is None


async def test_get_bill_doc_raises_on_non_ok(client):
    payload = {"status": "ERROR", "alert": {"message": "Doc not found"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="getBillText returned non-OK"):
            await client.get_bill_doc(999)


async def test_get_bill_text_by_doc_id_extracts_pdf(client):
    """Wrapper composition get_bill_doc -> extract_text on a REAL PDF.

    This is the only test that proves the evidence.py 'free fix' actually
    decodes PDFs. The doc field is the base64 of the minimal text-bearing PDF
    verified against pypdf 6.12.2.
    """
    pdf_b64 = (
        "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
        "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
        "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
        "NzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4g"
        "Pj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA3NyA+PgpzdHJlYW0KQlQgL0YxIDI0IFRm"
        "IDcyIDcwMCBUZCAoQmUgaXQgZW5hY3RlZCBieSB0aGUgR2VuZXJhbCBBc3NlbWJseSBMZWdpTGVu"
        "cykgVGogRVQKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9TdWJ0eXBl"
        "IC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAw"
        "MCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAw"
        "MDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzNjggMDAwMDAgbiAKdHJh"
        "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0Y="
    )
    mock_response = {
        "status": "OK",
        "text": {"doc_id": 999, "doc": pdf_b64, "mime": "application/pdf"},
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text_by_doc_id(999)
    assert result is not None
    assert "enacted" in result
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/pytest tests/test_legiscan.py -q -k "get_bill_doc or extracts_pdf"`
Expected: FAIL — `AttributeError: ... object has no attribute 'get_bill_doc'` / `ImportError: cannot import name 'BillDoc'`.

- [ ] **Step 3: Add imports and the `BillDoc` dataclass**

In `backend/app/services/legiscan.py`, change the top imports. Replace:

```python
import base64
import binascii

import httpx
```

with:

```python
import base64
import binascii
from dataclasses import dataclass

import httpx

from app.services.text_extraction import extract_text
```

Then, immediately after the two module-level constants (`LEGISCAN_BASE` and `LEGISCAN_USER_AGENT`, near line 7) and before `class LegiScanClient:`, add:

```python


@dataclass(frozen=True)
class BillDoc:
    """A decoded LegiScan document: base64-decoded bytes + declared mime."""

    raw: bytes
    mime: str
```

- [ ] **Step 4: Replace `get_bill_text_by_doc_id` with `get_bill_doc` + wrapper**

In `backend/app/services/legiscan.py`, replace the entire existing method (lines 82-104):

```python
    async def get_bill_text_by_doc_id(self, doc_id: int) -> str | None:
        """Fetches bill text by LegiScan doc_id via op=getBillText.

        Returns the decoded UTF-8 text body, or None if the response
        contains no `doc` or decode fails. Raises ValueError on
        non-OK API status (caller decides retry policy).
        """
        resp = await self._http.get(
            "/",
            params={"key": self.api_key, "op": "getBillText", "id": doc_id},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "OK":
            raise ValueError(f"getBillText returned non-OK status: {payload!r}")
        text_record = payload.get("text") or {}
        encoded = text_record.get("doc")
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
```

with:

```python
    async def get_bill_doc(self, doc_id: int) -> BillDoc | None:
        """Fetches a bill document by LegiScan doc_id via op=getBillText.

        Returns BillDoc(raw, mime) — base64-decoded bytes plus the declared
        mime (e.g. "application/pdf", or "" when absent) — or None when the
        response carries no `doc` or the base64 fails to decode. Raises
        ValueError on non-OK API status (caller decides retry policy).

        Does NOT interpret content; see app.services.text_extraction.extract_text.
        """
        resp = await self._http.get(
            "/",
            params={"key": self.api_key, "op": "getBillText", "id": doc_id},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "OK":
            raise ValueError(f"getBillText returned non-OK status: {payload!r}")
        text_record = payload.get("text") or {}
        encoded = text_record.get("doc")
        if not encoded:
            return None
        try:
            raw = base64.b64decode(encoded)
        except binascii.Error:
            return None
        return BillDoc(raw=raw, mime=text_record.get("mime") or "")

    async def get_bill_text_by_doc_id(self, doc_id: int) -> str | None:
        """Convenience wrapper: fetch a doc and extract plain text.

        Returns extracted text (PDF via pypdf, or utf-8 for text mimes), or
        None. Used by the evidence/snippet worker, which only needs text.
        fetch_bill_texts._fetch_one calls get_bill_doc directly so it can log
        the mime on a permanent failure.
        """
        doc = await self.get_bill_doc(doc_id)
        return extract_text(doc.raw, doc.mime) if doc else None
```

- [ ] **Step 5: Run the full legiscan test file (new + existing) to verify all pass**

Run: `.venv/bin/pytest tests/test_legiscan.py -q`
Expected: all pass. The 4 pre-existing `get_bill_text_by_doc_id` tests pass unchanged (empty-mime → utf-8 reproduces old behavior; the `not-valid-base64!@#` case still hits `binascii.Error` → None), plus the 5 new tests.

- [ ] **Step 6: Commit**

```bash
git add app/services/legiscan.py tests/test_legiscan.py
git commit -m "feat(ist): add get_bill_doc; get_bill_text_by_doc_id wraps extract_text

evidence.py keeps calling get_bill_text_by_doc_id and now decodes PDFs
for free. Existing wrapper tests stay green (empty-mime -> utf-8 path).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Rewire `_fetch_one` to `get_bill_doc` + `extract_text`

**Files:**
- Modify: `backend/worker/tasks/fetch_bill_texts.py` (import near line 29; fetch block lines 88-93; success path lines 119-124)
- Test: `backend/tests/worker/test_fetch_bill_texts.py` (update existing mocks; add one garbage-PDF test)

- [ ] **Step 1: Update the existing tests + add the garbage-PDF test**

In `backend/tests/worker/test_fetch_bill_texts.py`, make these exact changes.

(a) In `test_success_path_calls_legiscan_and_commits`, replace:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_text_by_doc_id = AsyncMock(return_value="Be it enacted...")
    fake_legiscan.close = AsyncMock()
```

with:

```python
    from app.services.legiscan import BillDoc

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(
        return_value=BillDoc(raw=b"Be it enacted...", mime="text/plain")
    )
    fake_legiscan.close = AsyncMock()
```

and replace the assertion:

```python
    fake_legiscan.get_bill_text_by_doc_id.assert_awaited_once_with(999)
```

with:

```python
    fake_legiscan.get_bill_doc.assert_awaited_once_with(999)
```

(b) In `test_quota_guard_aborts_when_at_limit`, replace:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_text_by_doc_id = AsyncMock()
```

with:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock()
```

and replace:

```python
    fake_legiscan.get_bill_text_by_doc_id.assert_not_awaited()
```

with:

```python
    fake_legiscan.get_bill_doc.assert_not_awaited()
```

(c) In `test_empty_doc_is_permanent_failure`, replace:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_text_by_doc_id = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()
```

with:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()
```

(d) In `test_third_failure_escalates_to_skipped`, replace:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_text_by_doc_id = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()
```

with:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()
```

(e) In `test_transient_5xx_requeues_does_not_set_failed`, replace:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_text_by_doc_id = AsyncMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=err_response)
    )
    fake_legiscan.close = AsyncMock()
```

with:

```python
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=err_response)
    )
    fake_legiscan.close = AsyncMock()
```

(f) Append this new test at the end of the file (proves a PDF that yields no text is a permanent failure, exercising the real `extract_text` None path through `_fetch_one`):

```python
async def test_pdf_garbage_is_permanent_failure():
    from app.services.legiscan import BillDoc

    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    # application/pdf mime but the bytes are not a parseable PDF -> extract_text None
    fake_legiscan.get_bill_doc = AsyncMock(
        return_value=BillDoc(raw=b"not a pdf", mime="application/pdf")
    )
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 1  # terminal outcome
    assert bill.text_fetch_status == "failed"
    assert bill.text_fetch_attempts == 1
```

- [ ] **Step 2: Run the worker tests to verify they fail**

Run: `.venv/bin/pytest tests/worker/test_fetch_bill_texts.py -q`
Expected: FAIL — `_fetch_one` still calls `get_bill_text_by_doc_id`, so `fake_legiscan.get_bill_doc.assert_awaited_once_with(999)` fails (not awaited) and the success path returns no text.

- [ ] **Step 3: Add the `extract_text` import to the worker**

In `backend/worker/tasks/fetch_bill_texts.py`, after the line:

```python
from app.services.legiscan import LegiScanClient
```

add:

```python
from app.services.text_extraction import extract_text
```

- [ ] **Step 4: Replace the fetch block in `_fetch_one`**

In `backend/worker/tasks/fetch_bill_texts.py`, replace these lines (88-93):

```python
    # API call OUTSIDE the DB transaction
    decoded_text: str | None = None
    failure: str | None = None
    try:
        decoded_text = await client.get_bill_text_by_doc_id(doc_id)
        if not decoded_text:
            failure = "permanent"
```

with:

```python
    # API call OUTSIDE the DB transaction
    text: str | None = None
    failure: str | None = None
    try:
        doc = await client.get_bill_doc(doc_id)
        text = extract_text(doc.raw, doc.mime) if doc else None
        if not text:
            failure = "permanent"
            logger.warning(
                "fetch %d (doc=%d): no text from mime=%s → permanent",
                legiscan_id,
                doc_id,
                doc.mime if doc else "<none>",
            )
```

- [ ] **Step 5: Update the success path to use `text`**

In the same file, in the success branch (`if failure is None:`), replace these lines (119-124):

```python
            # Success path
            bill.full_text = decoded_text
            bill.text_fetched_at = datetime.now(tz=timezone.utc)
            bill.text_fetch_status = "done"

            mh = compute_minhash(decoded_text)
```

with:

```python
            # Success path
            bill.full_text = text
            bill.text_fetched_at = datetime.now(tz=timezone.utc)
            bill.text_fetch_status = "done"

            mh = compute_minhash(text)
```

- [ ] **Step 6: Run the worker tests to verify they pass**

Run: `.venv/bin/pytest tests/worker/test_fetch_bill_texts.py -q`
Expected: all pass (5 updated + 1 new = 6 in this file's `_fetch_one`/`fetch_bill_texts` group; full file green).

- [ ] **Step 7: Commit**

```bash
git add worker/tasks/fetch_bill_texts.py tests/worker/test_fetch_bill_texts.py
git commit -m "feat(ist): _fetch_one uses get_bill_doc + extract_text, logs mime on failure

The previously silent 'no text' branch now logs the mime + reason -- the
original blind spot that hid the CO PDF bug until the pilot.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Full-suite verification (invariant tripwire)

**Files:** none (verification only).

- [ ] **Step 1: Run the entire backend test suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: all tests pass (the pre-change baseline of 108 plus the new extractor/client/worker tests). 0 failures.

- [ ] **Step 2: Confirm the invariant explicitly**

Run: `.venv/bin/pytest tests/test_evidence.py tests/test_legiscan.py -q`
Expected: all pass. Confirm via `git diff --stat HEAD~3 -- tests/test_evidence.py` that `tests/test_evidence.py` has **zero** changes (evidence tests were never edited) and that the 4 original `get_bill_text_by_doc_id` tests in `tests/test_legiscan.py` are unchanged. If either was modified to make tests pass, STOP — the wrapper drifted from the old behavior; reconcile in code, not in tests.

- [ ] **Step 3: Lint/compile sanity (optional but fast)**

Run: `.venv/bin/python -c "import app.services.legiscan, app.services.text_extraction, worker.tasks.fetch_bill_texts, worker.tasks.evidence"`
Expected: no output, exit 0 (no import cycle, all modules import clean).

---

## Post-merge operational sequence (NOT code — gated, do not run during implementation)

These steps touch production and LegiScan quota. They are listed for completeness and must each be confirmed by the user before running. They are out of scope for this plan's code tasks.

1. Open PR `feat/ist-pdf-text-extraction` → main; code review (superpowers:requesting-code-review); merge after green.
2. Railway worker rebuild + deploy (picks up `pypdf` from requirements.txt).
3. Reset the pilot's stuck rows:
   ```sql
   UPDATE bills SET text_fetch_status='queued', text_fetch_attempts=0
   WHERE state='CO' AND text_fetch_status IN ('failed','skipped');
   ```
4. Re-pilot 50 CO bills → confirm `full_text` + signatures land → **measure real CO `full_text` on-disk size** (the storage-gate denominator).
5. Full CO burst — **gated on** the two open gates from the spec: (a) the 0.13% corpus-coverage decision, (b) verified Neon storage limit.

---

## Self-Review (completed by plan author)

**Spec coverage:** get_bill_doc + BillDoc (Task 3) ✓; pure extract_text PDF+text/utf-8 (Task 2) ✓; wrapper keeps evidence.py working + PDF for free (Task 3) ✓; _fetch_one mime logging (Task 4) ✓; pypdf dependency (Task 1) ✓; error table — empty doc/decode-fail/garbage-PDF/unknown-mime/non-OK all covered by Task 2+3+4 tests ✓; required wrapper PDF composition test (Task 3 Step 1) ✓; invariant tripwire (Task 5) ✓. Operational sequence is explicitly out of code scope.

**Placeholder scan:** none — every code step contains complete code; both base64 fixtures are full verified strings.

**Type consistency:** `BillDoc(raw: bytes, mime: str)` defined in legiscan.py (Task 3), imported identically in test_legiscan.py, test_fetch_bill_texts.py (Task 4). `extract_text(raw, mime) -> str | None` defined in Task 2, called identically in legiscan wrapper (Task 3) and _fetch_one (Task 4). `get_bill_doc(doc_id) -> BillDoc | None` signature consistent across definition, wrapper, _fetch_one, and all mocks.
