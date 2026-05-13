from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.ist_score import ISTScore
from app.models.friction_tag import FrictionTag
from app.schemas.bill import BillListItem, BillDetail, ISTScoreOut, FrictionTagOut

router = APIRouter(prefix="/bills", dependencies=[Depends(require_user_agent)])


@router.get("", response_model=list[BillListItem])
async def list_bills(
    session: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Bill, ISTScore.copycat_alert)
        .outerjoin(ISTScore, ISTScore.bill_id == Bill.id)
        .where(Bill.is_corpus_only.is_(False))
    )
    if session:
        q = q.where(Bill.session == session)
    if status:
        q = q.where(Bill.status == status)
    q = q.offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    rows = result.all()
    return [
        BillListItem(
            id=b.id,
            bill_number=b.bill_number,
            title=b.title,
            state=b.state,
            session=b.session,
            status=b.status,
            copycat_alert=copycat_alert,
        )
        for b, copycat_alert in rows
    ]


@router.get("/search", response_model=list[BillListItem])
async def search_bills(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bill, ISTScore.copycat_alert)
        .outerjoin(ISTScore, ISTScore.bill_id == Bill.id)
        .where(Bill.is_corpus_only.is_(False))
        .where(func.similarity(Bill.full_text, q) > 0.1)
        .order_by(func.similarity(Bill.full_text, q).desc())
        .limit(20)
    )
    rows = result.all()
    return [
        BillListItem(
            id=b.id,
            bill_number=b.bill_number,
            title=b.title,
            state=b.state,
            session=b.session,
            status=b.status,
            copycat_alert=copycat_alert,
        )
        for b, copycat_alert in rows
    ]


@router.get("/sessions", response_model=list[str])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bill.session)
        .where(Bill.is_corpus_only.is_(False))
        .distinct()
        .order_by(Bill.session.desc())
    )
    return [row[0] for row in result.all()]


@router.get("/{bill_id}", response_model=BillDetail)
async def get_bill(bill_id: UUID, db: AsyncSession = Depends(get_db)):
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    score_result = await db.execute(select(ISTScore).where(ISTScore.bill_id == bill_id))
    score = score_result.scalar_one_or_none()

    tags_result = await db.execute(select(FrictionTag).where(FrictionTag.bill_id == bill_id))
    tags = tags_result.scalars().all()

    return BillDetail(
        id=bill.id,
        bill_number=bill.bill_number,
        title=bill.title,
        description=bill.description,
        state=bill.state,
        session=bill.session,
        status=bill.status,
        sponsors=bill.sponsors,
        ist_score=ISTScoreOut(
            source_authenticity_score=score.source_authenticity_score,
            copycat_alert=score.copycat_alert,
            analyzed_at=score.analyzed_at,
        ) if score else None,
        tags=[FrictionTagOut(tag_type=t.tag_type, confidence=t.confidence) for t in tags],
    )
