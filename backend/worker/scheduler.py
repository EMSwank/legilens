import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.database import async_session
from app.models.bill import Bill
from worker.tasks.evidence import extract_all_pending_evidence
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_full_pipeline():
    logger.info("Pipeline start: ingesting all states")
    await ingest_all_states()
    logger.info("Ingestion complete. Running match phase.")
    await match_co_bills()
    logger.info("Match phase complete. Extracting evidence.")
    await extract_all_pending_evidence()
    logger.info("Pipeline complete.")


async def _db_is_empty() -> bool:
    async with async_session() as session:
        result = await session.execute(select(func.count(Bill.id)))
        return (result.scalar() or 0) == 0


async def _bootstrap_if_empty(scheduler: AsyncIOScheduler) -> None:
    if await _db_is_empty():
        run_at = datetime.now() + timedelta(seconds=5)
        scheduler.add_job(run_full_pipeline, "date", run_date=run_at, id="bootstrap")
        logger.info("DB empty — bootstrap pipeline scheduled at %s.", run_at.isoformat())
    else:
        logger.info("DB already populated — skipping bootstrap run.")


async def _main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_full_pipeline, "cron", hour=3, minute=0, id="nightly")
    scheduler.start()
    logger.info("Scheduler started. Nightly run at 03:00.")
    await _bootstrap_if_empty(scheduler)
    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        scheduler.shutdown()


def start():
    try:
        asyncio.run(_main())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    start()
