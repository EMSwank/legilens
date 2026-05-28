"""Tests for adaptive LegiScan API quota tracking."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from worker.quota import get_quota_used, increment_quota, reset_quota_if_month_rolled


async def test_get_quota_used_returns_zero_when_no_row():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    assert await get_quota_used(session) == 0


async def test_get_quota_used_returns_stored_value():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = "1234"
    session.execute = AsyncMock(return_value=result_mock)

    assert await get_quota_used(session) == 1234


async def test_increment_quota_writes_new_value():
    """increment_quota performs an upsert; verifies at least one execute call."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = "10"
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    new_val = await increment_quota(session, n=1)
    assert new_val == 11
    session.execute.assert_awaited()


async def test_reset_quota_zeroes_counter_on_month_rollover():
    """Stored month differs from current UTC month — counter resets to 0."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = "2026-04"
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rolled = await reset_quota_if_month_rolled(session, now=now)
    assert rolled is True
    session.execute.assert_awaited()


async def test_reset_quota_no_op_when_same_month():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = "2026-05"
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    now = datetime(2026, 5, 28, tzinfo=timezone.utc)
    rolled = await reset_quota_if_month_rolled(session, now=now)
    assert rolled is False
