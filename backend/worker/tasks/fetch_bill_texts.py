"""Fetches bill text via LegiScan getBillText, persists, computes MinHash.

Behavior contract (see docs/superpowers/specs/2026-05-28-ist-text-fetch-design.md):

1. One atomic DB transaction per bill containing:
   - bill row update (status, full_text, text_fetched_at, text_fetch_attempts)
   - minhash_signatures upsert (success path only)
   - worker_state quota counter increment (success + permanent failure only)
2. API call happens OUTSIDE the DB transaction — no held connections during I/O.
3. Quota guard: quota_used >= 27000 → return 0 immediately.
4. Failure classification:
   - Permanent (empty doc, decode fail, ValueError, 4xx ≠ 429):
     increment attempts + charge quota. 3rd failure → 'skipped'.
   - Transient (5xx, 429, timeout): increment attempts, leave 'queued',
     do NOT charge quota.
"""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.services.legiscan import LegiScanClient
from app.services.minhash import compute_minhash
from app.services.text_extraction import extract_text
from worker.queue import next_queued_bills
from worker.quota import get_quota_used, increment_quota, reset_quota_if_month_rolled

logger = logging.getLogger(__name__)

QUOTA_HARD_LIMIT = 27_000  # leaves 3k headroom for ingest + retries


async def fetch_bill_texts(
    *, batch_size: int = 50, priority_state: str | None = None
) -> int:
    """Fetches up to batch_size bills needing text.

    Returns count of terminal outcomes (success or permanent failure).
    Transient retries are not counted.
    """
    async with async_session() as session:
        await reset_quota_if_month_rolled(session)
        await session.commit()

        quota = await get_quota_used(session)
        if quota >= QUOTA_HARD_LIMIT:
            logger.warning(
                "fetch_bill_texts: quota_used=%d >= hard limit %d — aborting batch",
                quota,
                QUOTA_HARD_LIMIT,
            )
            return 0

        bills = await next_queued_bills(
            session, batch_size=batch_size, priority_state=priority_state
        )

    if not bills:
        return 0

    client = LegiScanClient(api_key=settings.legiscan_api_key)
    try:
        terminal = 0
        for bill in bills:
            outcome = await _fetch_one(client, bill)
            if outcome in ("success", "permanent_failure"):
                terminal += 1
        return terminal
    finally:
        await client.close()


async def _fetch_one(client: LegiScanClient, bill_summary: Bill) -> str:
    """Fetches and persists one bill's text.

    Returns one of: 'success', 'permanent_failure', 'transient_failure'.
    """
    bill_id = bill_summary.id
    doc_id = bill_summary.text_doc_id
    legiscan_id = bill_summary.legiscan_id

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
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 429 or 500 <= status < 600:
            failure = "transient"
        else:
            failure = "permanent"
        logger.warning(
            "fetch %d (doc=%d): HTTP %s → %s", legiscan_id, doc_id, status, failure
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        # httpx.TimeoutException is the base for ConnectTimeout, ReadTimeout,
        # WriteTimeout, and PoolTimeout. The client configures connect/write/pool
        # timeouts (legiscan.py), so all four can fire; catching only ReadTimeout
        # let the other three propagate uncaught and abort the rest of the batch.
        # ConnectError is a NetworkError (not a TimeoutException), so it stays.
        failure = "transient"
        logger.warning("fetch %d (doc=%d): network error → transient: %s", legiscan_id, doc_id, exc)
    except ValueError as exc:
        # Non-OK LegiScan envelope
        failure = "permanent"
        logger.warning("fetch %d (doc=%d): %s → permanent", legiscan_id, doc_id, exc)

    # One atomic DB transaction per bill
    async with async_session() as session:
        bill = await session.get(Bill, bill_id)
        if bill is None:
            logger.warning("fetch %d: bill gone from DB mid-batch", legiscan_id)
            return "permanent_failure"

        if failure is None:
            # Success path
            bill.full_text = text
            bill.text_fetched_at = datetime.now(tz=timezone.utc)
            bill.text_fetch_status = "done"

            mh = compute_minhash(text)
            sig = mh.hashvalues.tolist()
            await session.execute(
                pg_insert(MinHashSignature)
                .values(bill_id=bill.id, signature=sig)
                .on_conflict_do_update(
                    index_elements=["bill_id"],
                    set_={"signature": sig, "computed_at": func.now()},
                )
            )
            await increment_quota(session, n=1)
            await session.commit()
            return "success"

        if failure == "transient":
            bill.text_fetch_attempts = (bill.text_fetch_attempts or 0) + 1
            # Leave status='queued' — eligible for retry next batch
            await session.commit()
            return "transient_failure"

        # Permanent failure
        bill.text_fetch_attempts = (bill.text_fetch_attempts or 0) + 1
        if bill.text_fetch_attempts >= 3:
            bill.text_fetch_status = "skipped"
        else:
            bill.text_fetch_status = "failed"
        await increment_quota(session, n=1)
        await session.commit()
        return "permanent_failure"
