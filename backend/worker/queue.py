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

_TOP5_STATES = ["CA", "NY", "IL", "TX", "FL"]

_STATE_PRIORITY = case(
    (Bill.state == "CO", 0),
    (Bill.state.in_(_TOP5_STATES), 1),
    else_=2,
)


async def next_queued_bills(
    session,
    *,
    batch_size: int,
    priority_state: str | None = None,
) -> list[Bill]:
    """Returns up to batch_size bills needing text fetch, ordered by priority.

    Args:
        session: async SQLAlchemy session
        batch_size: maximum rows to return
        priority_state: if set, only return bills from this state (e.g. "CO"
                        for the initial burst phase)
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

    result = await session.execute(stmt)
    return result.scalars().all()
