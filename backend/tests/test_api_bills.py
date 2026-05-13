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
    execute_result = MagicMock()
    execute_result.all.return_value = []
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
    execute_result = MagicMock()
    execute_result.all.return_value = []
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


async def test_get_bills_propagates_copycat_alert(client):
    c, app, get_db = client
    bill_id = uuid4()
    mock_bill = MagicMock()
    mock_bill.id = bill_id
    mock_bill.bill_number = "HB22-9999"
    mock_bill.title = "Copycat Bill"
    mock_bill.state = "CO"
    mock_bill.session = "2022"
    mock_bill.status = "Introduced"
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [(mock_bill, True)]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/bills", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json()[0]["copycat_alert"] is True


async def test_search_bills_propagates_copycat_alert(client):
    c, app, get_db = client
    bill_id = uuid4()
    mock_bill = MagicMock()
    mock_bill.id = bill_id
    mock_bill.bill_number = "HB22-9998"
    mock_bill.title = "Cloned Policy Act"
    mock_bill.state = "CO"
    mock_bill.session = "2022"
    mock_bill.status = "Introduced"
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [(mock_bill, True)]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get("/bills/search?q=clone", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json()[0]["copycat_alert"] is True


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


async def test_get_bills_with_tag_type_filter():
    """When tag_type is passed, the query uses an IN subquery on friction_tags to avoid duplicate rows."""
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=source_cloned",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "friction_tag" in stmt
    assert "tag_type" in stmt


async def test_get_bills_tag_type_combines_with_session_and_status():
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=source_cloned&session=2025A&status=Passed",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "tag_type" in stmt
    assert "session" in stmt
    assert "status" in stmt


async def test_get_bills_invalid_tag_type_returns_empty_list():
    """An unknown tag_type returns 200 with [], not 500."""
    from app.main import app
    from app.dependencies import get_db

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = []
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/bills?tag_type=not_a_real_tag",
                headers={"User-Agent": "TestClient/1.0"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_bills_without_tag_type_does_not_join_friction_tags():
    """Regression: unfiltered list_bills must NOT join friction_tags."""
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/bills", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    stmt = captured[0].lower()
    assert "friction_tag" not in stmt


async def test_get_bills_tag_type_uses_subquery_not_join():
    """tag_type filter must use IN subquery, not a join, to prevent duplicate rows
    when a bill has multiple friction_tags with the same tag_type."""
    from app.main import app
    from app.dependencies import get_db

    captured = []

    async def execute_spy(stmt):
        captured.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_spy

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.get("/bills?tag_type=source_cloned", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    stmt = captured[0].lower()
    assert "bills.id in" in stmt or "bills.id in(" in stmt
    assert "join friction_tags" not in stmt
