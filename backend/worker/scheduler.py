import asyncio
import logging
import signal
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.logging_filters import RedactAPIKeyFilter
from app.models.bill import Bill
from app.models.worker_state import WorkerState
from app.services.legiscan import LegiScanClient
from worker.tasks.evidence import extract_all_pending_evidence
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills

logger = logging.getLogger(__name__)

BOOTSTRAP_DEBOUNCE_KEY = "bootstrap:last_run"
BOOTSTRAP_DEBOUNCE = timedelta(days=7)


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
    quickly, then ingest the remaining 49 states and run match + evidence
    against the full corpus.

    Pass 1 uses LegiScan's server-side state filter (getDatasetList?state=CO)
    rather than client-side filtering — the datasetlist payload has no
    state_abbr field, only state_id, so filtering by abbr in Python silently
    matches nothing. Two getDatasetList calls per bootstrap is trivial against
    the 30k/month quota.

    Pass 1 deliberately skips match + evidence: with an empty corpus the only
    output would be stub ISTScore rows that pass 2 would have to overwrite,
    and the bill list endpoint outerjoins ISTScore so CO bills render fine
    without a score row.
    """
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    try:
        try:
            co_datasets = await client.get_dataset_list(state="CO")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("getDatasetList(state=CO) failed; aborting pipeline run")
            return False

        logger.info("Pipeline start (pass=1): ingesting CO only for fast visibility")
        try:
            await ingest_all_states(datasets=co_datasets)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("CO ingest failed; aborting pipeline run")
            return False

        try:
            all_datasets = await client.get_dataset_list()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("getDatasetList failed; aborting pipeline run")
            return False

        logger.info("Pipeline (pass=2): ingesting remaining states for full corpus")
        try:
            await ingest_all_states(datasets=all_datasets)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Full corpus ingest failed; aborting pipeline run")
            return False
    finally:
        await client.close()
    logger.info("Full ingest complete. Running match + evidence against full corpus.")
    if not await _run_match_and_evidence():
        return False

    logger.info("Pipeline complete.")
    return True


async def _db_is_empty() -> bool:
    async with async_session() as session:
        result = await session.execute(select(Bill.id).where(Bill.is_corpus_only.is_(False)).limit(1))
        return result.scalar() is None


async def _bootstrap_recently_ran() -> bool:
    """Postgres-backed debounce. Survives Redis restarts and ephemeral disk —
    losing this check is exactly what burns a 50-dataset API run."""
    cutoff = datetime.now(timezone.utc) - BOOTSTRAP_DEBOUNCE
    async with async_session() as session:
        result = await session.execute(
            select(WorkerState.updated_at).where(WorkerState.key == BOOTSTRAP_DEBOUNCE_KEY)
        )
        last_run = result.scalar()
    return last_run is not None and last_run > cutoff


async def _mark_bootstrap_ran() -> None:
    async with async_session() as session:
        await session.execute(
            pg_insert(WorkerState)
            .values(key=BOOTSTRAP_DEBOUNCE_KEY)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"updated_at": func.now()},
            )
        )
        await session.commit()


async def _bootstrap_pipeline() -> None:
    if await run_full_pipeline():
        await _mark_bootstrap_ran()


async def _bootstrap_if_empty(scheduler: AsyncIOScheduler) -> None:
    if not await _db_is_empty():
        logger.info("DB already populated — skipping bootstrap run.")
        return
    if await _bootstrap_recently_ran():
        logger.info(
            "Bootstrap ran within last %s — skipping to avoid LegiScan re-fetch.",
            BOOTSTRAP_DEBOUNCE,
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
