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


async def test_get_bills_search_returns_200(client):
    c, app, get_db = client
    mock_session = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/bills/search?q=fees", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_bill_detail_returns_200(client):
    c, app, get_db = client

    bill_id = uuid4()
    mock_bill = MagicMock()
    mock_bill.id = bill_id
    mock_bill.bill_number = "HB22-1234"
    mock_bill.title = "Fee Modernization Act"
    mock_bill.description = "Modernizes fee structure"
    mock_bill.state = "CO"
    mock_bill.session = "2022"
    mock_bill.status = "Passed"
    mock_bill.sponsors = None

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_bill

    # First execute: IST score query
    score_result = MagicMock()
    score_result.scalar_one_or_none.return_value = None

    # Second execute: tags query
    tags_result = MagicMock()
    tags_scalars = MagicMock()
    tags_scalars.all.return_value = []
    tags_result.scalars.return_value = tags_scalars

    mock_session.execute.side_effect = [score_result, tags_result]

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{bill_id}", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["bill_number"] == "HB22-1234"
    assert data["ist_score"] is None
    assert data["tags"] == []


async def test_get_bills_search_requires_user_agent(client):
    c, app, get_db = client
    resp = await c.get("/bills/search?q=fees", headers={"User-Agent": ""})
    assert resp.status_code == 400
