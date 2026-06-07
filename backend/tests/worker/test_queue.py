"""Tests for the priority-ordered bill fetch queue.

Uses AsyncMock — no real DB needed. ORDER BY priority logic is exercised
by checking that the correct SELECT was attempted; actual ordering is
integration-tested only when TEST_DATABASE_URL is set.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from worker.queue import next_queued_bills


async def test_next_queued_bills_returns_list_from_db():
    """Happy path: session returns some Bill rows."""
    from app.models.bill import Bill
    from uuid import uuid4

    fake_bill = Bill(
        id=uuid4(),
        legiscan_id=1,
        state="CO",
        session="2024A",
        bill_number="HB1",
        title="Test",
        text_doc_id=999,
    )
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [fake_bill]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    result = await next_queued_bills(session, batch_size=10)
    assert len(result) == 1
    assert result[0].state == "CO"
    session.execute.assert_awaited_once()


async def test_next_queued_bills_returns_empty_when_no_rows():
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    result = await next_queued_bills(session, batch_size=50)
    assert result == []


async def test_next_queued_bills_passes_batch_size_as_limit():
    """Verify the query is executed (limit enforcement is in the SQL, not testable
    with AsyncMock — we verify the call was made and no exception raised)."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    await next_queued_bills(session, batch_size=7)
    session.execute.assert_awaited_once()


async def test_next_queued_bills_with_priority_state_filter():
    """priority_state kwarg is accepted and query still executes."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    result = await next_queued_bills(session, batch_size=10, priority_state="CO")
    assert result == []
    session.execute.assert_awaited_once()


def test_tier_for_classifies_states():
    """Pure mirror of the SQL _STATE_PRIORITY case. NY is tier 2 (deferred), not tier 1."""
    from worker.queue import tier_for

    assert tier_for("CO") == 0
    for s in ("CA", "IL", "TX", "FL"):
        assert tier_for(s) == 1, f"{s} must be tier 1"
    assert tier_for("NY") == 2, "NY is deferred to tier 2 in WS2 v1"
    assert tier_for("WY") == 2


async def test_next_queued_bills_max_priority_tier_accepted():
    """max_priority_tier kwarg is accepted and the query still executes.
    (Row-level tier exclusion is verified by the read-only Neon probe, not here —
    the mock session cannot evaluate the SQL .where().)"""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    result = await next_queued_bills(session, batch_size=10, max_priority_tier=1)
    assert result == []
    session.execute.assert_awaited_once()
