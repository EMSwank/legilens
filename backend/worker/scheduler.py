import asyncio
import logging
import signal
from datetime import datetime

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.logging_filters import RedactAPIKeyFilter
from app.models.bill import Bill
from worker.tasks.evidence import extract_all_pending_evidence
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills

logger = logging.getLogger(__name__)

BOOTSTRAP_DEBOUNCE_KEY = "worker:bootstrap:last_run"
BOOTSTRAP_DEBOUNCE_TTL = 3600


async def _run_match_and_evidence() -> bool:
    try:
        await match_co_bills()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Match phase failed")
        return False
    try:
        await extract_all_pending_evidence()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Evidence phase failed")
        return False
    return True


async def run_full_pipeline() -> bool:
    """Bootstrap-friendly pipeline: ingest CO first so the live site has data
    quickly, then ingest the remaining 49 states and re-match against the
    fuller corpus.
    """
    logger.info("Pipeline start: ingesting CO first")
    try:
        await ingest_all_states(only_state="CO")
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("CO ingest failed; aborting pipeline run")
        return False
    logger.info("CO ingest complete. Running initial match + evidence.")
    if not await _run_match_and_evidence():
        return False

    logger.info("Initial pass complete. Ingesting remaining states for full corpus.")
    try:
        await ingest_all_states()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Full corpus ingest failed; aborting pipeline run")
        return False
    logger.info("Full ingest complete. Re-running match + evidence against full corpus.")
    if not await _run_match_and_evidence():
        return False

    logger.info("Pipeline complete.")
    return True


async def _db_is_empty() -> bool:
    async with async_session() as session:
        result = await session.execute(select(Bill.id).where(Bill.is_corpus_only.is_(False)).limit(1))
        return result.scalar() is None


async def _bootstrap_recently_ran() -> bool:
    redis = aioredis.from_url(settings.redis_url)
    try:
        return (await redis.get(BOOTSTRAP_DEBOUNCE_KEY)) is not None
    finally:
        await redis.aclose()


async def _mark_bootstrap_ran() -> None:
    redis = aioredis.from_url(settings.redis_url)
    try:
        await redis.setex(BOOTSTRAP_DEBOUNCE_KEY, BOOTSTRAP_DEBOUNCE_TTL, b"1")
    finally:
        await redis.aclose()


async def _bootstrap_pipeline() -> None:
    if await run_full_pipeline():
        await _mark_bootstrap_ran()


async def _bootstrap_if_empty(scheduler: AsyncIOScheduler) -> None:
    if not await _db_is_empty():
        logger.info("DB already populated — skipping bootstrap run.")
        return
    if await _bootstrap_recently_ran():
        logger.info(
            "Bootstrap ran within last %ss — skipping to avoid LegiScan re-fetch.",
            BOOTSTRAP_DEBOUNCE_TTL,
        )
        return
    scheduler.add_job(
        _bootstrap_pipeline,
        "date",
        run_date=datetime.now(scheduler.timezone),
        id="bootstrap",
        misfire_grace_time=60,
    )
    logger.info("DB empty — bootstrap pipeline scheduled immediately.")


async def _main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_full_pipeline, "cron", hour=3, minute=0, id="nightly")
    scheduler.start()
    logger.info("Scheduler started. Nightly run at 03:00 %s.", scheduler.timezone)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    await _bootstrap_if_empty(scheduler)

    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=True)


def start() -> None:
    logging.basicConfig(level=logging.INFO)
    redact = RedactAPIKeyFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redact)
    asyncio.run(_main())


if __name__ == "__main__":
    start()
