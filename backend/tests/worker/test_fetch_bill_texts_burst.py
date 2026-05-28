"""Tests for the burst fetcher (CO-first, run-once)."""
from unittest.mock import AsyncMock, patch

from worker.tasks.fetch_bill_texts_burst import fetch_bill_texts_burst


async def test_burst_stops_when_queue_exhausted():
    with patch(
        "worker.tasks.fetch_bill_texts_burst.fetch_bill_texts",
        new=AsyncMock(side_effect=[10, 10, 0]),
    ) as fake_fetch, patch(
        "worker.tasks.fetch_bill_texts_burst.match_co_bills",
        new=AsyncMock(),
    ) as fake_match:
        total = await fetch_bill_texts_burst(max_calls=500, batch_size=50)

    assert total == 20
    assert fake_fetch.await_count == 3
    fake_match.assert_awaited_once()


async def test_burst_stops_when_max_calls_hit():
    with patch(
        "worker.tasks.fetch_bill_texts_burst.fetch_bill_texts",
        new=AsyncMock(return_value=50),
    ) as fake_fetch, patch(
        "worker.tasks.fetch_bill_texts_burst.match_co_bills",
        new=AsyncMock(),
    ) as fake_match:
        total = await fetch_bill_texts_burst(max_calls=100, batch_size=50)

    assert total == 100
    assert fake_fetch.await_count == 2
    fake_match.assert_awaited_once()


async def test_burst_passes_priority_state_co():
    with patch(
        "worker.tasks.fetch_bill_texts_burst.fetch_bill_texts",
        new=AsyncMock(side_effect=[0]),
    ) as fake_fetch, patch(
        "worker.tasks.fetch_bill_texts_burst.match_co_bills",
        new=AsyncMock(),
    ):
        await fetch_bill_texts_burst(max_calls=500, batch_size=50)

    fake_fetch.assert_awaited_with(batch_size=50, priority_state="CO")


async def test_burst_triggers_match_even_when_nothing_fetched():
    with patch(
        "worker.tasks.fetch_bill_texts_burst.fetch_bill_texts",
        new=AsyncMock(return_value=0),
    ), patch(
        "worker.tasks.fetch_bill_texts_burst.match_co_bills",
        new=AsyncMock(),
    ) as fake_match:
        total = await fetch_bill_texts_burst(max_calls=500, batch_size=50)

    assert total == 0
    fake_match.assert_awaited_once()
