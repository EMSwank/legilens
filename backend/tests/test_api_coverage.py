# All imports at top to avoid pylint C0413 (wrong-import-position) — CI fails on
# ANY pylint message. The json/AsyncClient/AsyncMock imports are used by the
# endpoint tests appended in Task 3; they're declared here so Task 3 adds only
# functions, never mid-file imports.
import json
from datetime import datetime, timezone
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.schemas.coverage import StateCoverage, CoverageOut


def test_coverage_schema_round_trips():
    out = CoverageOut(
        status="ready",
        as_of=datetime(2026, 6, 3, 4, 0, tzinfo=timezone.utc),
        matchable_pct=78.4,
        states=[StateCoverage(state="CO", fetchable=4000, with_sig=3999, status="complete")],
    )
    dumped = out.model_dump()
    assert dumped["status"] == "ready"
    assert dumped["matchable_pct"] == 78.4
    assert dumped["states"][0]["status"] == "complete"


def test_coverage_schema_allows_pending_nulls():
    out = CoverageOut(status="pending", as_of=None, matchable_pct=None, states=[])
    assert out.matchable_pct is None
    assert out.states == []
