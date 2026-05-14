from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_session_with_result():
    def _make(scalar_value):
        result = MagicMock()
        result.scalar.return_value = scalar_value
        session = AsyncMock()
        session.execute.return_value = result
        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=None)
        return session_ctx, session

    return _make


async def test_db_is_empty_returns_true_when_no_bills(mock_session_with_result):
    from worker import scheduler

    session_ctx, _ = mock_session_with_result(None)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        assert await scheduler._db_is_empty() is True


async def test_db_is_empty_returns_false_when_bill_exists(mock_session_with_result):
    from worker import scheduler

    session_ctx, _ = mock_session_with_result(1)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        assert await scheduler._db_is_empty() is False


async def test_bootstrap_if_empty_schedules_job_when_db_empty_and_not_debounced():
    from worker import scheduler

    fake_scheduler = MagicMock()
    fake_scheduler.timezone = None
    fake_scheduler.add_job = MagicMock()

    with patch.object(scheduler, "_db_is_empty", AsyncMock(return_value=True)), patch.object(
        scheduler, "_bootstrap_recently_ran", AsyncMock(return_value=False)
    ):
        await scheduler._bootstrap_if_empty(fake_scheduler)

    fake_scheduler.add_job.assert_called_once()
    kwargs = fake_scheduler.add_job.call_args.kwargs
    assert kwargs["id"] == "bootstrap"
    assert kwargs["misfire_grace_time"] == 60


async def test_bootstrap_if_empty_skips_when_db_populated():
    from worker import scheduler

    fake_scheduler = MagicMock()
    fake_scheduler.add_job = MagicMock()

    with patch.object(scheduler, "_db_is_empty", AsyncMock(return_value=False)):
        await scheduler._bootstrap_if_empty(fake_scheduler)

    fake_scheduler.add_job.assert_not_called()


async def test_bootstrap_if_empty_skips_when_recently_ran():
    from worker import scheduler

    fake_scheduler = MagicMock()
    fake_scheduler.add_job = MagicMock()

    with patch.object(scheduler, "_db_is_empty", AsyncMock(return_value=True)), patch.object(
        scheduler, "_bootstrap_recently_ran", AsyncMock(return_value=True)
    ):
        await scheduler._bootstrap_if_empty(fake_scheduler)

    fake_scheduler.add_job.assert_not_called()


async def test_run_full_pipeline_aborts_on_ingest_failure():
    from worker import scheduler

    with patch.object(
        scheduler, "ingest_all_states", AsyncMock(side_effect=RuntimeError("boom"))
    ), patch.object(scheduler, "match_co_bills", AsyncMock()) as match_mock, patch.object(
        scheduler, "extract_all_pending_evidence", AsyncMock()
    ) as evidence_mock:
        await scheduler.run_full_pipeline()

    match_mock.assert_not_called()
    evidence_mock.assert_not_called()


async def test_bootstrap_pipeline_marks_then_runs():
    from worker import scheduler

    order = []
    mark = AsyncMock(side_effect=lambda: order.append("mark"))
    run = AsyncMock(side_effect=lambda: order.append("run"))

    with patch.object(scheduler, "_mark_bootstrap_ran", mark), patch.object(
        scheduler, "run_full_pipeline", run
    ):
        await scheduler._bootstrap_pipeline()

    assert order == ["mark", "run"]
