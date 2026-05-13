from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock


async def test_get_sessions_returns_list():
    from app.main import app
    from app.dependencies import get_db

    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [("2025A",), ("2024A",), ("2023A",)]
    mock_session.execute.return_value = execute_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == ["2025A", "2024A", "2023A"]


async def test_get_sessions_returns_empty_list_when_no_bills():
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
            resp = await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_sessions_requires_user_agent():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/bills/sessions", headers={"User-Agent": ""})
    assert resp.status_code == 400


async def test_get_sessions_query_orders_descending_and_excludes_corpus_only():
    """The query must filter is_corpus_only=False and ORDER BY session DESC."""
    from app.main import app
    from app.dependencies import get_db

    captured_statements = []

    async def execute_spy(stmt):
        captured_statements.append(str(stmt))
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
            await c.get("/bills/sessions", headers={"User-Agent": "TestClient/1.0"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert len(captured_statements) == 1
    stmt = captured_statements[0].lower()
    assert "distinct" in stmt
    assert "is_corpus_only" in stmt
    assert "order by" in stmt and "desc" in stmt
