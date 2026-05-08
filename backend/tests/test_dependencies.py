import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from app.dependencies import require_user_agent


async def test_require_user_agent_passes_with_header():
    result = await require_user_agent(user_agent="Mozilla/5.0")
    assert result is None


async def test_require_user_agent_raises_without_header():
    with pytest.raises(HTTPException) as exc:
        await require_user_agent(user_agent=None)
    assert exc.value.status_code == 400
    assert "User-Agent" in exc.value.detail


async def test_get_db_yields_async_session():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies.async_session", return_value=mock_cm):
        from app.dependencies import get_db
        gen = get_db()
        session = await gen.__anext__()
        assert isinstance(session, AsyncMock)
        try:
            await gen.aclose()
        except StopAsyncIteration:
            pass
