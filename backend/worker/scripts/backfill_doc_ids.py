"""One-shot script: backfill bills.text_doc_id for bills using cached ZIPs.

Reads every ZIP under settings.legiscan_zip_cache_dir, parses bill records,
extracts texts[-1].doc_id, and UPDATEs the matching Bill row by legiscan_id
WHERE text_doc_id IS NULL.

Idempotent — safe to re-run. Reports counts to stdout.

Usage on Railway:
    python -m worker.scripts.backfill_doc_ids
    python -m worker.scripts.backfill_doc_ids --state CO
"""
import argparse
import asyncio
import json
import logging
import sys
import zipfile
from pathlib import Path

from sqlalchemy import update

from app.config import settings
from app.database import async_session
from app.models.bill import Bill

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _iter_bills_in_zip(zip_path: Path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                with zf.open(name) as f:
                    data = json.load(f)
                bill = data.get("bill")
                if isinstance(bill, dict):
                    yield bill
    except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
        logger.warning("Skipping corrupt ZIP %s: %s", zip_path, exc)


async def backfill(state_filter: str | None) -> None:
    cache_dir = Path(settings.legiscan_zip_cache_dir)
    if not cache_dir.exists():
        logger.error("Cache dir %s does not exist — no ZIPs to scan", cache_dir)
        sys.exit(1)

    zips = sorted(cache_dir.glob("*.zip"))
    logger.info("Scanning %d cached ZIPs (state filter=%s)", len(zips), state_filter or "<all>")

    updates = 0
    skipped = 0
    async with async_session() as session:
        for zip_path in zips:
            for bill_record in _iter_bills_in_zip(zip_path):
                bill_state = bill_record.get("state") or ""
                if state_filter and bill_state != state_filter:
                    continue
                legiscan_id = bill_record.get("bill_id")
                texts = bill_record.get("texts", [])
                if not legiscan_id or not texts:
                    skipped += 1
                    continue
                raw_doc_id = texts[-1].get("doc_id")
                try:
                    doc_id = int(raw_doc_id) if raw_doc_id is not None else None
                except (TypeError, ValueError):
                    doc_id = None
                if doc_id is None:
                    skipped += 1
                    continue

                result = await session.execute(
                    update(Bill)
                    .where(Bill.legiscan_id == legiscan_id)
                    .where(Bill.text_doc_id.is_(None))
                    .values(text_doc_id=doc_id)
                )
                if result.rowcount and result.rowcount > 0:
                    updates += 1

        await session.commit()

    logger.info("Done. rows_updated=%d skipped=%d", updates, skipped)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill bills.text_doc_id from cached ZIP files"
    )
    parser.add_argument("--state", help="State filter (e.g. CO). Omit for all states.")
    args = parser.parse_args()
    asyncio.run(backfill(args.state))


if __name__ == "__main__":
    main()
