from uuid import UUID
from pydantic import TypeAdapter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.similarity_match import SimilarityMatch
from app.models.bill import Bill
from app.schemas.match import MatchOut, SnippetOrGhost, GhostMessage

router = APIRouter(prefix="/bills", dependencies=[Depends(require_user_agent)])

_snippet_list_adapter = TypeAdapter(list[SnippetOrGhost])


@router.get("/{bill_id}/matches", response_model=list[MatchOut])
async def get_matches(bill_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SimilarityMatch, Bill.bill_number)
        .outerjoin(Bill, Bill.id == SimilarityMatch.matched_bill_id)
        .where(SimilarityMatch.bill_id == bill_id)
    )
    matches = result.all()

    out = []
    for m, bill_number in matches:
        if m.snippet_status == "source_verified_text_missing":
            snippets = [GhostMessage(message="Source text unavailable for extraction")]
        elif m.matched_snippets is not None:
            snippets = _snippet_list_adapter.validate_python(m.matched_snippets)
        else:
            snippets = None

        out.append(MatchOut(
            id=m.id,
            matched_bill_title=m.matched_bill_title,
            matched_state=m.matched_state,
            similarity_score=m.similarity_score,
            snippet_status=m.snippet_status,
            matched_snippets=snippets,
            match_type=m.match_type,
            matched_bill_id=m.matched_bill_id,
            matched_bill_number=bill_number,
        ))
    return out
