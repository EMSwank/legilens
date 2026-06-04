"""Priority queue for bill text fetch.

Bills are fetched in priority order:
  0 — Colorado (focus state)
  1 — CA, NY, IL, TX, FL (top corpus states)
  2 — all remaining states (alphabetical)

Exclusion rules (applied in SQL):
  - text_fetch_status != 'queued'
  - full_text IS NOT NULL (already have text)
  - text_fetch_attempts >= 3 (permanent failure)
  - text_doc_id IS NULL (no LegiScan doc to fetch)
"""
from sqlalchemy import case, select

from app.models.bill import Bill

# Keep tiers 0 (CO) + 1 (these states) in sync with app.services.coverage.SCOPE,
# the coverage tracker's matchable-% denominator. Change both together.
# NY is intentionally NOT here in WS2 v1: it is ~150k bills (~6.5 months alone) and is
# deferred to tier 2. Re-promote NY to this list AND to coverage.SCOPE together when the
# national tail is funded (and bump the Neon spend cap at the same time).
_TIER1_STATES = ["CA", "IL", "TX", "FL"]


def tier_for(state: str) -> int:
    """Pure-Python mirror of the SQL _STATE_PRIORITY case below.

    Exists so the mock-only test suite can verify tier membership (esp. that NY is
    excluded from tier 1) without a real DB — the SQL case() itself is exercised by a
    read-only Neon probe, not by unit tests.
    """
    if state == "CO":
        return 0
    if state in _TIER1_STATES:
        return 1
    return 2


_STATE_PRIORITY = case(
    (Bill.state == "CO", 0),
    (Bill.state.in_(_TIER1_STATES), 1),
    else_=2,
)


async def next_queued_bills(
    session,
    *,
    batch_size: int,
    priority_state: str | None = None,
    max_priority_tier: int | None = None,
) -> list[Bill]:
    """Returns up to batch_size bills needing text fetch, ordered by priority.

    Args:
        session: async SQLAlchemy session
        batch_size: maximum rows to return
        priority_state: if set, only return bills from this state (e.g. "CO"
                        for the initial burst phase)
        max_priority_tier: if set, only return bills whose state priority tier is
                           <= this value (0=CO, 1=tier-1 comparison states, 2=rest).
                           max_priority_tier=1 is the steady-state corpus build (CO +
                           tier-1, NY excluded — NY is tier 2).
    """
    stmt = (
        select(Bill)
        .where(Bill.text_fetch_status == "queued")
        .where(Bill.full_text.is_(None))
        .where(Bill.text_fetch_attempts < 3)
        .where(Bill.text_doc_id.is_not(None))
        .order_by(_STATE_PRIORITY, Bill.state, Bill.legiscan_id)
        .limit(batch_size)
    )

    if priority_state is not None:
        stmt = stmt.where(Bill.state == priority_state)

    if max_priority_tier is not None:
        stmt = stmt.where(_STATE_PRIORITY <= max_priority_tier)

    result = await session.execute(stmt)
    return result.scalars().all()
