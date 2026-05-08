from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.friction_tag import FrictionTag
from app.schemas.stats import TagCountOut

router = APIRouter(dependencies=[Depends(require_user_agent)])


@router.get("/tags", response_model=list[TagCountOut])
async def list_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FrictionTag.tag_type, func.count().label("count"))
        .group_by(FrictionTag.tag_type)
        .order_by(func.count().desc())
    )
    return [TagCountOut(tag_type=row[0], count=row[1]) for row in result.all()]
