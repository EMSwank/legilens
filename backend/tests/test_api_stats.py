import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.dependencies import get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app, get_db


async def test_stats_returns_counts(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar.return_value = 5
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/stats", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "total_co_bills" in data
    assert "copycat_alerts" in data
    assert "bills_analyzed" in data


async def test_stats_requires_user_agent(client):
    c, app, get_db = client
    resp = await c.get("/stats", headers={"User-Agent": ""})
    assert resp.status_code == 400


async def test_tags_returns_list(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [("source_cloned", 12)]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/tags", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["tag_type"] == "source_cloned"
    assert data[0]["count"] == 12


async def test_tags_requires_user_agent(client):
    c, app, get_db = client
    resp = await c.get("/tags", headers={"User-Agent": ""})
    assert resp.status_code == 400
