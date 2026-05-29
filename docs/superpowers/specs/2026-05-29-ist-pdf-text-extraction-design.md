# IST PDF Text Extraction — Design

**Date:** 2026-05-29
**Status:** Approved (brainstorm), pending implementation plan
**Amends:** `docs/superpowers/specs/2026-05-28-ist-text-fetch-design.md`

## Problem

The text-fetch pipeline marks every Colorado bill as a permanent failure. After
the `text_doc_id` backfill (11,954 CO bills populated), a 50-bill pilot burst
produced **0 successes, 50 failures, 0 signatures**.

### Root cause (evidence-backed)

`LegiScanClient.get_bill_text_by_doc_id` does:

```python
return base64.b64decode(encoded).decode("utf-8")
```

The 2026-05-28 text-fetch spec assumed `getBillText` returns base64-encoded
**UTF-8 text**. It does not for Colorado. Live `getBillText` probes across CO
sessions 2010–2026 show every record is:

```
mime: application/pdf   alt_mime: (empty)   alt_doc: none
```

The base64 `doc` decodes to **PDF bytes**, so `.decode("utf-8")` raises
`UnicodeDecodeError`. The current code swallows that into `None` (no log line),
which `_fetch_one` classifies as a permanent failure. That silent `None` is why
the failure was invisible until the pilot.

Text-layer extractability was verified: `pypdf` 6.x extracts clean legislative
text from 6 random CO bills (2016–2021, 2–15 pages, 2.7k–29k chars) — bill
titles, sponsors, body. No scanned/image-only PDFs in the sample. The `%PDF`
magic-byte check confirms the bytes are genuine PDFs (not merely the mime label).

## Goal

Extract real text from `getBillText` responses regardless of document format, so
CO bills get `full_text` + MinHash signatures and the match phase can run.

## Scope

**In:** `application/pdf` (pypdf) and `text/*` (utf-8) extraction. CO is the live
need and is PDF; the utf-8 path stays as a fallback for text mimes.

**Out (deferred, YAGNI):**
- HTML extraction (no CO bill returns HTML; revisit when a non-CO state's text is populated).
- OCR for scanned/image PDFs (none seen in CO; different project, likely infeasible on free tier).
- Corpus population beyond the current 1,000 seed (separate strategic decision — see Open Gates).
- Snippet-only storage optimization (not needed at CO scale).

## Architecture (isolated units)

### 1. `app/services/legiscan.py` — HTTP + decode only

Replace `get_bill_text_by_doc_id(doc_id) -> str | None` with:

```python
@dataclass(frozen=True)
class BillDoc:
    raw: bytes      # base64-decoded document bytes
    mime: str       # e.g. "application/pdf", "text/html", or "" when absent

async def get_bill_doc(self, doc_id: int) -> BillDoc | None:
    # GET getBillText; raise_for_status; ValueError on non-OK envelope.
    # text.doc missing/empty -> return None.
    # else: return BillDoc(raw=base64decode(doc), mime=text.get("mime") or "")
```

The client no longer interprets document content. It still raises `ValueError`
on a non-OK LegiScan envelope (caller's retry policy unchanged) and returns
`None` when the response carries no `doc`.

**Sole caller:** `worker/tasks/fetch_bill_texts.py::_fetch_one`. No other module
imports the old method.

### 2. `app/services/text_extraction.py` — pure extractor (new)

```python
def extract_text(raw: bytes, mime: str) -> str | None:
    # application/pdf  -> pypdf: join page.extract_text() across pages, strip.
    #                     empty result or any pypdf exception -> None.
    # text/* or mime "" -> raw.decode("utf-8") ; UnicodeDecodeError -> None.
    # anything else     -> None.
```

Pure function: bytes + mime in, text or None out. No network, no DB. pypdf is
imported only here.

### 3. `worker/tasks/fetch_bill_texts.py::_fetch_one` — orchestration

```python
doc = await client.get_bill_doc(doc_id)          # ValueError -> permanent (as today)
text = extract_text(doc.raw, doc.mime) if doc else None
if not text:
    failure = "permanent"
    logger.warning("fetch %d (doc=%d): no text from mime=%s -> permanent",
                   legiscan_id, doc_id, doc.mime if doc else "<none>")
# success/transient/permanent transaction logic unchanged
```

## Data flow

`getBillText` → `BillDoc{raw, mime}` → `extract_text` → text | None →
on text: `compute_minhash` → persist `bills.full_text`, upsert
`minhash_signatures`, `increment_quota(1)`, commit. Downstream (match phase,
ISTScore) unchanged.

## Error handling

| Condition | Class | Quota charged | Status |
|---|---|---|---|
| PDF parses, non-empty text | success | yes | done |
| PDF parse raises / extracts empty | permanent | yes | failed → skipped at 3 attempts |
| `text/*` utf-8 decode fails | permanent | yes | failed → skipped |
| Unsupported mime (logged) | permanent | yes | failed → skipped |
| No `doc` in response | permanent | yes | failed → skipped |
| HTTP 5xx / 429 / timeout | transient | no | stays queued |
| Non-OK envelope (`ValueError`) | permanent | yes | failed → skipped |

Every permanent path logs `mime` + reason. The previously silent
`if not decoded_text` branch now logs — the original blind spot.

## Testing (TDD)

**Pure extractor** (`tests/test_text_extraction.py`), committed fixtures:
- real CO PDF bytes (small, checked-in) → expected substring present
- empty / non-PDF garbage bytes with `application/pdf` mime → `None`
- `text/html` and `text/plain` bytes → utf-8 string
- empty mime → utf-8 path
- unknown mime (`application/zip`) → `None`
- valid PDF with no text layer (image-only fixture, if feasible) → `None`

**Client** (`tests/test_legiscan*.py`, mock httpx):
- OK envelope with `doc` → `BillDoc(raw=<bytes>, mime="application/pdf")`
- missing/empty `doc` → `None`
- non-OK envelope → `ValueError`

**`_fetch_one`** (existing AsyncMock pattern):
- PDF `BillDoc` that extracts text → `"success"`, signature upserted, quota++
- `BillDoc` that extracts empty → `"permanent_failure"`, status failed

Update the existing `get_bill_text_by_doc_id` shape test to the new contract.

## Operational sequence (post-merge, not code)

1. `pypdf` added to `requirements.txt`; Railway worker rebuild + deploy.
2. Reset the pilot's stuck rows:
   `UPDATE bills SET text_fetch_status='queued', text_fetch_attempts=0
    WHERE state='CO' AND text_fetch_status IN ('failed','skipped');`
3. Re-pilot 50 CO bills → confirm `full_text` + signatures land → **measure real
   CO `full_text` on-disk size** (the storage-gate denominator).
4. Full CO burst — **gated on** the two Open Gates below.

## Open gates (carried, not resolved here)

- **Corpus coverage 0.13%** (1,000 / 789,776 corpus bills have signatures). CO
  bills will match against this small reference set. Whether to populate the
  corpus (signatures ~1KB/bill ≈ 790MB, vs full_text ≈ 12GB) before spending
  quota on the full CO burst is a separate strategic decision. Does **not** block
  this bug fix — text extraction is required regardless of corpus size.
- **Neon plan storage limit** unverified. Must confirm (dashboard) before the
  full burst; re-pilot supplies the real per-bill size.

## Out of scope

OCR, HTML extraction, corpus population, snippet-only storage, re-ingest. No
schema change (uses existing `full_text`, `text_doc_id`, `text_fetch_*`,
`minhash_signatures`).
