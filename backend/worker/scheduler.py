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
from worker.queue import _TIER1_STATES
from worker.tasks.evidence import extract_all_pending_evidence
from worker.tasks.fetch_bill_texts import fetch_bill_texts
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills
from worker.tasks.coverage import compute_and_store_coverage_snapshot

logger = logging.getLogger(__name__)

BOOTSTRAP_DEBOUNCE_KEY = "bootstrap:last_run"
BOOTSTRAP_DEBOUNCE = timedelta(days=7)


async def fetch_and_match() -> None:
    """Daily steady-state: fetch ~1k queued bill texts (CO + tier-1 comparison
    states, NY excluded) then run the match phase.

    Runs after run_full_pipeline (03:00). Quota guard inside fetch_bill_texts
    (QUOTA_HARD_LIMIT=27_000/mo) prevents overrun even if called extra times.

    max_priority_tier=1 un-gates the fetch from CO-only (PR #58) to CO + tier-1.
    This is the WS2 decision (docs/superpowers/specs/
    2026-06-02-co-related-bills-coverage-tracker-design.md §4): fund a bounded
    cross-state corpus so real cross-state copycat alerts can surface. New York
    is deliberately deferred — it is ~150k bills (~6.5 months at the quota cap)
    and is demoted to tier 2 in worker/queue.py; it is fetched only when the
    national tail is explicitly funded and the Neon spend cap is raised.

    Reassess trigger: when CO + tier-1 reach ~complete on /coverage, evaluate
    whether real cross-state copycat_alerts appeared. If yes, plan widening
    (re-promote NY, then the rest). If no, stop. Document in a follow-up.
    """
    logger.info("fetch_and_match: start")
    count = await fetch_bill_texts(batch_size=1000, max_priority_tier=1)
    logger.info("fetch_and_match: fetched %d bills (CO + tier-1, NY deferred)", count)
    if count > 0:
        await match_co_bills()
    # Refresh the coverage snapshot every night regardless of fetch count, and
    # never let a snapshot failure break the cron.
    try:
        await compute_and_store_coverage_snapshot()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Coverage snapshot failed")
    logger.info("fetch_and_match: done")


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


# The cross-state comparison states are queue._TIER1_STATES (CA/IL/TX/FL) — imported so
# this stays the single source of truth shared with the steady-state fetch tier and
# coverage.SCOPE (one list, not three). They are ingested via the bounded per-state pass
# below so the comparison corpus never depends on pass 2's full 995-dataset,
# state_id-ordered march completing — which in practice it does not. getDatasetList is
# ordered by state_id; pass 2 restarts from index 0 every run and re-downloads
# weekly-changed early-state datasets, so the frontier never crosses the state_id>=34
# tail. TX is state_id 43 → the never-reached tail (prod symptom: bills.TX = 0), even
# though CA(5)/IL(13)/FL(9) land in pass 2's early window. CO is ingested in pass 1; NY
# (state_id 32, already ~185k bills) is excluded — see queue._TIER1_STATES for why.
async def _ingest_scope_states(client: LegiScanClient, states: list[str]) -> None:
    """Ingest each state's datasets via the server-side getDatasetList(state=)
    filter — the same mechanism pass 1 uses for CO.

    Best-effort per state: one state failing is logged and skipped so it can never
    abort the pipeline, and the nightly rerun retries it (dataset dedup makes the
    retry a no-op once the state has landed). Already-present states (CA/IL/FL)
    dedup-skip without a download; only the genuinely-missing tail state (TX)
    actually transfers data.
    """
    for state in states:
        try:
            datasets = await client.get_dataset_list(state=state)
            logger.info(
                "Pipeline (pass=tier1): ingesting state=%s (%d datasets)",
                state, len(datasets),
            )
            await ingest_all_states(datasets=datasets)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "tier-1 scope ingest for state=%s failed; continuing", state
            )


async def run_full_pipeline() -> bool:
    """Bootstrap-friendly pipeline: ingest CO first so the live site has data
    quickly, then ingest the tier-1 comparison states, then the remaining states,
    and finally run match + evidence against the full corpus.

    Pass tier1 (_ingest_scope_states) is a bounded per-state ingest of the
    cross-state comparison states (queue._TIER1_STATES). It exists because pass 2
    iterates all ~995 datasets in state_id order from the top each run and never
    completes a full sweep, so the state_id>=34 tail — which includes TX — was
    never ingested. Running the wanted comparison states directly, up front, makes
    the corpus independent of pass 2 finishing.

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

        # Pass tier1: bounded ingest of the cross-state comparison states so the
        # corpus is built regardless of whether pass 2's full march ever completes.
        logger.info(
            "Pipeline (pass=tier1): ingesting tier-1 comparison states %s",
            _TIER1_STATES,
        )
        await _ingest_scope_states(client, _TIER1_STATES)

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
    scheduler.add_job(
        fetch_and_match,
        "cron",
        hour=4,
        minute=0,
        id="fetch_and_match",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "Scheduler started. Nightly ingest at 03:00, fetch_and_match at 04:00 %s.",
        scheduler.timezone,
    )

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
