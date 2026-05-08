import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.dependencies import get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app, get_db


async def test_get_bills_returns_200(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    # scalars() and all() are synchronous on the Result object; only execute() is async
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/bills", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_bills_requires_user_agent(client):
    c, app, get_db = client
    # Pass an empty User-Agent to trigger the 400 — httpx sends its own UA by default
    resp = await c.get("/bills", headers={"User-Agent": ""})
    assert resp.status_code == 400


async def test_get_bill_detail_404_on_missing(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{uuid4()}", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404
