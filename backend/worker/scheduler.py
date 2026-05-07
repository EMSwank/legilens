import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills
from worker.tasks.evidence import extract_all_pending_evidence

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


def start():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_full_pipeline, "cron", hour=3, minute=0)
    scheduler.start()
    logger.info("Scheduler started. Next run at 03:00.")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    start()
