import json
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.dialects import postgresql


async def test_compute_snapshot_aggregates_and_upserts():
    # One boolean-per-bill row each: a fully-matchable CO bill, a CO bill whose
    # signature has NULL text_doc_id (must NOT inflate counts), a fetchable-only TX bill.
    rows = [("CO", True, True), ("CO", False, True), ("TX", True, False)]

    mock_session = AsyncMock()
    read_result = MagicMock()
    read_result.all.return_value = rows
    # First execute() = read query, second = upsert.
    mock_session.execute.side_effect = [read_result, AsyncMock()]
    mock_session.commit = AsyncMock()

    fake_ctx = MagicMock()
    fake_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.coverage.async_session", return_value=fake_ctx):
        from worker.tasks.coverage import compute_and_store_coverage_snapshot
        await compute_and_store_coverage_snapshot()

    # Read + upsert both issued, and committed.
    assert mock_session.execute.await_count == 2
    mock_session.commit.assert_awaited()

    # Inspect the upsert statement's bound params. Assert by membership in
    # params.values(), NOT by bind name — pg on_conflict_do_update bind-naming
    # is version-sensitive. The NULL-doc CO row contributes nothing, so CO
    # with_sig stays 1 (the hazard guard, end-to-end through aggregation).
    upsert_stmt = mock_session.execute.await_args_list[1].args[0]
    compiled = upsert_stmt.compile(dialect=postgresql.dialect())
    values = list(compiled.params.values())
    assert "coverage_snapshot" in values
    expected = json.dumps({"states": [
        {"state": "CO", "fetchable": 1, "with_sig": 1},
        {"state": "TX", "fetchable": 1, "with_sig": 0},
    ]})
    assert expected in values
    # updated_at is set explicitly in the conflict path (func.now(), not a bind).
    assert "updated_at" in str(compiled)
