import json
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.worker_state import WorkerState
from app.schemas.coverage import CoverageOut, StateCoverage
from app.services.coverage import derive_state_status, scoped_matchable_pct

router = APIRouter(dependencies=[Depends(require_user_agent)])

COVERAGE_SNAPSHOT_KEY = "coverage_snapshot"


@router.get("/coverage", response_model=CoverageOut)
async def get_coverage(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(WorkerState.value, WorkerState.updated_at).where(
                WorkerState.key == COVERAGE_SNAPSHOT_KEY
            )
        )
    ).first()

    if row is None or row[0] is None:
        return CoverageOut(status="pending", as_of=None, matchable_pct=None, states=[])

    value, updated_at = row
    per_state = {
        s["state"]: {"fetchable": s["fetchable"], "with_sig": s["with_sig"]}
        for s in json.loads(value)["states"]
    }
    states = [
        StateCoverage(
            state=state,
            fetchable=counts["fetchable"],
            with_sig=counts["with_sig"],
            status=derive_state_status(counts["fetchable"], counts["with_sig"]),
        )
        for state, counts in per_state.items()
    ]
    return CoverageOut(
        status="ready",
        as_of=updated_at,
        matchable_pct=scoped_matchable_pct(per_state),
        states=states,
    )
