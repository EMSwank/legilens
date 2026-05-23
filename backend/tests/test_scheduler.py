from datetime import datetime, timedelta, timezone
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


def _fake_client(datasets):
    """LegiScanClient whose get_dataset_list returns the given list."""
    client = AsyncMock()
    client.get_dataset_list = AsyncMock(return_value=datasets)
    client.close = AsyncMock()
    return client


async def test_run_full_pipeline_fetches_dataset_list_once_and_passes_to_both_ingests():
    from worker import scheduler

    fake_list = [{"session_id": 1, "state": "CO"}]
    client = _fake_client(fake_list)

    calls: list[tuple[str, dict]] = []

    async def fake_ingest(only_state=None, datasets=None):
        calls.append(("ingest", {"only_state": only_state, "datasets": datasets}))

    async def fake_match():
        calls.append(("match", {}))

    async def fake_evidence():
        calls.append(("evidence", {}))

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", fake_ingest
    ), patch.object(scheduler, "match_co_bills", fake_match), patch.object(
        scheduler, "extract_all_pending_evidence", fake_evidence
    ):
        result = await scheduler.run_full_pipeline()

    assert result is True
    # One getDatasetList call, both passes use it
    client.get_dataset_list.assert_awaited_once()
    assert calls == [
        ("ingest", {"only_state": "CO", "datasets": fake_list}),
        ("ingest", {"only_state": None, "datasets": fake_list}),
        ("match", {}),
        ("evidence", {}),
    ]


async def test_run_full_pipeline_aborts_on_ingest_failure():
    from worker import scheduler

    client = _fake_client([])

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", AsyncMock(side_effect=RuntimeError("boom"))
    ), patch.object(scheduler, "match_co_bills", AsyncMock()) as match_mock, patch.object(
        scheduler, "extract_all_pending_evidence", AsyncMock()
    ) as evidence_mock:
        result = await scheduler.run_full_pipeline()

    assert result is False
    match_mock.assert_not_called()
    evidence_mock.assert_not_called()


async def test_run_full_pipeline_aborts_when_get_dataset_list_fails():
    from worker import scheduler

    client = AsyncMock()
    client.get_dataset_list = AsyncMock(side_effect=RuntimeError("locked key"))
    client.close = AsyncMock()

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", AsyncMock()
    ) as ingest_mock:
        result = await scheduler.run_full_pipeline()

    assert result is False
    ingest_mock.assert_not_called()
    client.close.assert_awaited_once()


async def test_bootstrap_recently_ran_false_when_no_row(mock_session_with_result):
    from worker import scheduler

    session_ctx, _ = mock_session_with_result(None)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        assert await scheduler._bootstrap_recently_ran() is False


async def test_bootstrap_recently_ran_true_when_row_within_ttl(mock_session_with_result):
    from worker import scheduler

    recent = datetime.now(timezone.utc) - timedelta(days=1)
    session_ctx, _ = mock_session_with_result(recent)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        assert await scheduler._bootstrap_recently_ran() is True


async def test_bootstrap_recently_ran_false_when_row_past_ttl(mock_session_with_result):
    from worker import scheduler

    stale = datetime.now(timezone.utc) - timedelta(days=14)
    session_ctx, _ = mock_session_with_result(stale)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        assert await scheduler._bootstrap_recently_ran() is False


async def test_mark_bootstrap_ran_upserts_worker_state(mock_session_with_result):
    from worker import scheduler

    session_ctx, session = mock_session_with_result(None)
    with patch.object(scheduler, "async_session", return_value=session_ctx):
        await scheduler._mark_bootstrap_ran()

    session.execute.assert_awaited()
    session.commit.assert_awaited_once()


async def test_bootstrap_pipeline_runs_then_marks_on_success():
    from worker import scheduler

    order = []
    mark = AsyncMock(side_effect=lambda: order.append("mark"))
    run = AsyncMock(return_value=True, side_effect=lambda: order.append("run") or True)

    with patch.object(scheduler, "_mark_bootstrap_ran", mark), patch.object(
        scheduler, "run_full_pipeline", run
    ):
        await scheduler._bootstrap_pipeline()

    assert order == ["run", "mark"]


async def test_bootstrap_pipeline_skips_mark_on_failure():
    from worker import scheduler

    mark = AsyncMock()

    with patch.object(scheduler, "run_full_pipeline", AsyncMock(return_value=False)), patch.object(
        scheduler, "_mark_bootstrap_ran", mark
    ):
        await scheduler._bootstrap_pipeline()

    mark.assert_not_called()
