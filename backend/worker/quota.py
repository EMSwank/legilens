"""Adaptive LegiScan API quota tracking.

State persists in worker_state table under two keys:
  legiscan_quota_used  — integer-as-string, calls made this month
  legiscan_quota_month — YYYY-MM string of the month the counter belongs to

All functions accept an open session and do NOT commit — callers decide
when to commit. For atomic increment-with-other-writes, callers that need
a single transaction should perform the upsert inline (see fetch_bill_texts).

NOTE: increment_quota is a read-then-write, not a true DB-level atomic op.
Concurrent workers could double-count. Worst case: a few extra API calls
within the 3k headroom (27k hard limit vs 30k monthly). Acceptable for
a single-worker Railway deployment.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.worker_state import WorkerState

QUOTA_USED_KEY = "legiscan_quota_used"
QUOTA_MONTH_KEY = "legiscan_quota_month"


async def get_quota_used(session) -> int:
    """Returns the current month's quota counter, defaulting to 0."""
    result = await session.execute(
        select(WorkerState.value).where(WorkerState.key == QUOTA_USED_KEY)
    )
    raw = result.scalar()
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


async def increment_quota(session, n: int = 1) -> int:
    """Increments the quota counter by n. Returns new value.

    Uses pg_insert ON CONFLICT to upsert. Not atomic under concurrency
    (read-then-write) but acceptable for single-worker deployment.
    Caller is responsible for commit.
    """
    current = await get_quota_used(session)
    new_value = current + n
    await session.execute(
        pg_insert(WorkerState)
        .values(key=QUOTA_USED_KEY, value=str(new_value))
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": str(new_value)},
        )
    )
    return new_value


async def reset_quota_if_month_rolled(session, *, now: datetime | None = None) -> bool:
    """If the stored month differs from current UTC month, reset counter to 0.

    Returns True if a reset happened. Caller commits.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    current_month = now.strftime("%Y-%m")

    result = await session.execute(
        select(WorkerState.value).where(WorkerState.key == QUOTA_MONTH_KEY)
    )
    stored_month = result.scalar()

    if stored_month == current_month:
        return False

    await session.execute(
        pg_insert(WorkerState)
        .values(key=QUOTA_USED_KEY, value="0")
        .on_conflict_do_update(index_elements=["key"], set_={"value": "0"})
    )
    await session.execute(
        pg_insert(WorkerState)
        .values(key=QUOTA_MONTH_KEY, value=current_month)
        .on_conflict_do_update(index_elements=["key"], set_={"value": current_month})
    )
    return True
