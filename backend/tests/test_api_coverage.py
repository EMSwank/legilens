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


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.dependencies import get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app, get_db


async def test_coverage_ready(client):
    c, app, get_db = client
    snapshot = json.dumps({"states": [
        {"state": "CO", "fetchable": 100, "with_sig": 95},
        {"state": "WY", "fetchable": 10, "with_sig": 0},
    ]})
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.first.return_value = (snapshot, datetime(2026, 6, 3, 4, 0, tzinfo=timezone.utc))
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/coverage", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["matchable_pct"] == 95.0  # CO only in scope; WY excluded
    co = next(s for s in data["states"] if s["state"] == "CO")
    assert co["status"] == "complete"
    wy = next(s for s in data["states"] if s["state"] == "WY")
    assert wy["status"] == "not_started"


async def test_coverage_pending_when_no_snapshot(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/coverage", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["matchable_pct"] is None
    assert data["states"] == []


async def test_coverage_requires_user_agent(client):
    c, app, get_db = client
    resp = await c.get("/coverage", headers={"User-Agent": ""})
    assert resp.status_code == 400
