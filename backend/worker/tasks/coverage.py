import json
import logging
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.models.worker_state import WorkerState
from app.services.coverage import build_snapshot_payload

logger = logging.getLogger(__name__)

COVERAGE_SNAPSHOT_KEY = "coverage_snapshot"


async def compute_and_store_coverage_snapshot() -> None:
    """Nightly coverage snapshot: one boolean-per-bill read, aggregate in Python,
    upsert the JSON into worker_state.

    The read emits (state, text_doc_id IS NOT NULL, EXISTS(signature)) per bill —
    EXISTS, never a join, so duplicate signature rows cannot fan-out double-count
    fetchable. Aggregation lives in app.services.coverage (pure, unit-tested).
    """
    sig_exists = (
        select(MinHashSignature.id)
        .where(MinHashSignature.bill_id == Bill.id)
        .exists()
    )
    stmt = select(
        Bill.state,
        Bill.text_doc_id.isnot(None),
        sig_exists,
    )

    async with async_session() as session:
        rows = (await session.execute(stmt)).all()
        payload = build_snapshot_payload(rows)
        await session.execute(
            pg_insert(WorkerState)
            .values(key=COVERAGE_SNAPSHOT_KEY, value=payload)
            .on_conflict_do_update(
                # updated_at MUST be set explicitly — onupdate=func.now() does NOT
                # fire on the on_conflict_do_update path (see scheduler._mark_bootstrap_ran).
                index_elements=["key"],
                set_={"value": payload, "updated_at": func.now()},
            )
        )
        await session.commit()
    logger.info("coverage: snapshot stored (%d states)", len(json.loads(payload)["states"]))
