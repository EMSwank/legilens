import pytest
from fastapi import HTTPException
from app.dependencies import require_user_agent


async def test_require_user_agent_passes_with_header():
    result = await require_user_agent(user_agent="Mozilla/5.0")
    assert result is None


async def test_require_user_agent_raises_without_header():
    with pytest.raises(HTTPException) as exc:
        await require_user_agent(user_agent=None)
    assert exc.value.status_code == 400
    assert "User-Agent" in exc.value.detail
