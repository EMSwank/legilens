from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.ist_score import ISTScore
from app.schemas.stats import StatsOut

router = APIRouter(dependencies=[Depends(require_user_agent)])


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(
        select(func.count()).select_from(Bill).where(Bill.is_corpus_only.is_(False))
    )
    alerts = await db.execute(
        select(func.count()).select_from(ISTScore).where(ISTScore.copycat_alert.is_(True))
    )
    analyzed = await db.execute(select(func.count()).select_from(ISTScore))
    return StatsOut(
        total_co_bills=total.scalar() or 0,
        copycat_alerts=alerts.scalar() or 0,
        bills_analyzed=analyzed.scalar() or 0,
    )
