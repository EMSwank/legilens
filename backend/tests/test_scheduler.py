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


def _fake_client_two_lists(co_list, all_list):
    """LegiScanClient whose get_dataset_list returns co_list when state="CO"
    is passed, all_list otherwise. Mirrors the two-pass bootstrap pipeline."""
    client = AsyncMock()

    async def _get(state=None):
        return co_list if state == "CO" else all_list

    client.get_dataset_list = AsyncMock(side_effect=_get)
    client.close = AsyncMock()
    return client


async def test_run_full_pipeline_fetches_co_then_tier1_then_full_and_passes_each_to_its_ingest():
    from worker import scheduler

    all_list = [{"session_id": 1}, {"session_id": 2}]
    client = _fake_client_per_state(all_list)

    calls: list[tuple[str, object]] = []

    async def fake_ingest(datasets=None):
        calls.append(("ingest", datasets))

    async def fake_match():
        calls.append(("match", None))

    async def fake_evidence():
        calls.append(("evidence", None))

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", fake_ingest
    ), patch.object(scheduler, "match_co_bills", fake_match), patch.object(
        scheduler, "extract_all_pending_evidence", fake_evidence
    ):
        result = await scheduler.run_full_pipeline()

    assert result is True
    # getDatasetList: CO, then each tier-1 comparison state, then unfiltered (pass 2).
    states = [c.kwargs.get("state") for c in client.get_dataset_list.await_args_list]
    assert states == ["CO", "CA", "IL", "TX", "FL", None]
    # Ingest order mirrors that, then match + evidence.
    assert calls == [
        ("ingest", [{"_state": "CO"}]),
        ("ingest", [{"_state": "CA"}]),
        ("ingest", [{"_state": "IL"}]),
        ("ingest", [{"_state": "TX"}]),
        ("ingest", [{"_state": "FL"}]),
        ("ingest", all_list),
        ("match", None),
        ("evidence", None),
    ]


async def test_run_full_pipeline_tier1_state_failure_does_not_abort():
    """A single tier-1 state failing (transient getDataset/parse error) must not
    abort the pipeline: the other states, pass 2, and match/evidence still run, and
    the run still reports success so the nightly rerun simply retries the failed
    state (dataset dedup makes successful states a no-op on retry)."""
    from worker import scheduler

    client = _fake_client_per_state([{"session_id": 1}])
    ingested = []

    async def fake_ingest(datasets=None):
        if datasets == [{"_state": "TX"}]:
            raise RuntimeError("TX dataset download failed")
        ingested.append(datasets)

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", fake_ingest
    ), patch.object(scheduler, "match_co_bills", AsyncMock()) as match_mock, patch.object(
        scheduler, "extract_all_pending_evidence", AsyncMock()
    ) as evidence_mock:
        result = await scheduler.run_full_pipeline()

    assert result is True
    match_mock.assert_awaited_once()
    evidence_mock.assert_awaited_once()
    # CO, the tier-1 state after TX (FL), and pass 2 all ingested despite TX failing.
    assert [{"_state": "CO"}] in ingested
    assert [{"_state": "FL"}] in ingested
    assert [{"session_id": 1}] in ingested


async def test_run_full_pipeline_aborts_on_ingest_failure():
    from worker import scheduler

    client = _fake_client_two_lists([], [])

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


async def test_fetch_and_match_runs_fetch_then_match():
    from worker.scheduler import fetch_and_match
    from unittest.mock import patch, AsyncMock

    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=42)) as fetch, \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()) as match, \
         patch("worker.scheduler.compute_and_store_coverage_snapshot", new=AsyncMock()):
        await fetch_and_match()

    fetch.assert_awaited_once_with(batch_size=1000, max_priority_tier=1)
    match.assert_awaited_once()


async def test_fetch_and_match_skips_match_when_zero_fetched():
    from worker.scheduler import fetch_and_match
    from unittest.mock import patch, AsyncMock

    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=0)), \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()) as match, \
         patch("worker.scheduler.compute_and_store_coverage_snapshot", new=AsyncMock()):
        await fetch_and_match()

    match.assert_not_awaited()


async def test_fetch_and_match_computes_coverage_snapshot():
    from worker.scheduler import fetch_and_match
    from unittest.mock import patch, AsyncMock

    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=0)), \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()), \
         patch("worker.scheduler.compute_and_store_coverage_snapshot", new=AsyncMock()) as snap:
        await fetch_and_match()

    # Snapshot runs even when 0 bills were fetched (coverage refreshes nightly).
    snap.assert_awaited_once()


async def test_fetch_and_match_survives_snapshot_failure():
    from worker.scheduler import fetch_and_match
    from unittest.mock import patch, AsyncMock

    with patch("worker.scheduler.fetch_bill_texts", new=AsyncMock(return_value=5)), \
         patch("worker.scheduler.match_co_bills", new=AsyncMock()), \
         patch("worker.scheduler.compute_and_store_coverage_snapshot",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        await fetch_and_match()  # must not raise


def _fake_client_per_state(all_list):
    """LegiScanClient whose get_dataset_list(state=X) returns a per-state marker
    [{"_state": X}], and the unfiltered call returns all_list. Lets a test assert
    which states' datasets flowed to ingest_all_states."""
    client = AsyncMock()

    async def _get(state=None):
        return all_list if state is None else [{"_state": state}]

    client.get_dataset_list = AsyncMock(side_effect=_get)
    client.close = AsyncMock()
    return client


async def test_run_full_pipeline_ingests_tx_in_scope_pass():
    """Regression guard for prod TX=0: TX (LegiScan state_id 43) lives in the
    state_id>=34 tail that pass 2's state_id-ordered march never reaches, so it
    was never ingested. run_full_pipeline must ingest TX directly via the bounded
    tier-1 scope pass, independent of whether pass 2 ever completes a full sweep."""
    from worker import scheduler

    client = _fake_client_per_state([{"session_id": 9}])
    ingested = []

    async def fake_ingest(datasets=None):
        ingested.append(datasets)

    with patch.object(scheduler, "LegiScanClient", return_value=client), patch.object(
        scheduler, "ingest_all_states", fake_ingest
    ), patch.object(scheduler, "match_co_bills", AsyncMock()), patch.object(
        scheduler, "extract_all_pending_evidence", AsyncMock()
    ):
        result = await scheduler.run_full_pipeline()

    assert result is True
    # TX datasets (from getDatasetList(state="TX")) were handed to ingest.
    assert [{"_state": "TX"}] in ingested
    # And TX was fetched via the server-side state filter, exactly once.
    tx_calls = [
        c for c in client.get_dataset_list.await_args_list if c.kwargs.get("state") == "TX"
    ]
    assert len(tx_calls) == 1
