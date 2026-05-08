import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from decimal import Decimal


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.dependencies import get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app, get_db


async def test_get_matches_returns_list(client):
    c, app, get_db = client

    bill_id = uuid4()
    match_id = uuid4()

    mock_match = MagicMock()
    mock_match.id = match_id
    mock_match.matched_bill_title = "HB 1234 - Fee Act"
    mock_match.matched_state = "TX"
    mock_match.similarity_score = Decimal("0.85")
    mock_match.snippet_status = "verified"
    mock_match.matched_snippets = [
        {
            "kind": "snippet",
            "co_context_before": "Intro.",
            "co_match": "The commission shall establish fees.",
            "co_context_after": "End.",
            "source_context_before": "Preamble.",
            "source_match": "The commission shall establish fees.",
            "source_context_after": "Close.",
        }
    ]

    mock_session = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [mock_match]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{bill_id}/matches", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == str(match_id)
    assert data[0]["matched_bill_title"] == "HB 1234 - Fee Act"
    assert data[0]["matched_state"] == "TX"
    assert data[0]["snippet_status"] == "verified"
    assert data[0]["matched_snippets"] is not None
    assert len(data[0]["matched_snippets"]) == 1
    assert data[0]["matched_snippets"][0]["kind"] == "snippet"


async def test_ghost_match_returns_message(client):
    c, app, get_db = client

    bill_id = uuid4()
    match_id = uuid4()

    mock_match = MagicMock()
    mock_match.id = match_id
    mock_match.matched_bill_title = "SB 99 - Ghost Bill"
    mock_match.matched_state = "CA"
    mock_match.similarity_score = Decimal("0.72")
    mock_match.snippet_status = "source_verified_text_missing"
    mock_match.matched_snippets = None

    mock_session = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [mock_match]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{bill_id}/matches", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["snippet_status"] == "source_verified_text_missing"
    assert data[0]["matched_snippets"] is not None
    assert len(data[0]["matched_snippets"]) == 1
    assert data[0]["matched_snippets"][0]["kind"] == "ghost"
    assert data[0]["matched_snippets"][0]["message"] == "Source text unavailable for extraction"


async def test_pending_match_has_null_snippets(client):
    c, app, get_db = client

    bill_id = uuid4()
    match_id = uuid4()

    mock_match = MagicMock()
    mock_match.id = match_id
    mock_match.matched_bill_title = "HB 500 - Pending Bill"
    mock_match.matched_state = "WA"
    mock_match.similarity_score = Decimal("0.91")
    mock_match.snippet_status = "pending"
    mock_match.matched_snippets = None

    mock_session = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [mock_match]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        resp = await c.get(f"/bills/{bill_id}/matches", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["snippet_status"] == "pending"
    assert data[0]["matched_snippets"] is None
