"""One-shot burst fetcher for CO bills.

Drains the CO queue (or hits max_calls budget), then triggers match_co_bills.
Intended for end-of-May quota burn before steady-state nightly cron takes over.

Always calls match_co_bills once at the end, even if zero bills were fetched,
to preserve match-phase idempotency.
"""
import logging

from worker.tasks.fetch_bill_texts import fetch_bill_texts
from worker.tasks.match import match_co_bills

logger = logging.getLogger(__name__)


async def fetch_bill_texts_burst(*, max_calls: int = 3000, batch_size: int = 50) -> int:
    """Fetch CO bills in batches until queue exhausted or max_calls reached.

    Returns total number of terminal outcomes across all batches.
    """
    total = 0
    while total < max_calls:
        remaining = max_calls - total
        this_batch = min(batch_size, remaining)
        fetched = await fetch_bill_texts(batch_size=this_batch, priority_state="CO")
        if fetched == 0:
            logger.info("burst: CO queue exhausted at %d/%d", total, max_calls)
            break
        total += fetched

    logger.info("burst: fetched %d bills total, triggering match_co_bills", total)
    await match_co_bills()
    return total
