from typing import AsyncGenerator
from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def require_user_agent(user_agent: str | None = Header(default=None)) -> None:
    if not user_agent:
        raise HTTPException(status_code=400, detail="User-Agent header required")
