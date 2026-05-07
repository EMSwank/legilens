import base64
import io
import json
import zipfile
from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.services.legiscan import LegiScanClient
from app.services.minhash import compute_minhash
from app.services.redis_cache import RedisCache
from app.config import settings


async def ingest_all_states():
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    cache = RedisCache(url=settings.redis_url)
    try:
        datasets = await client.get_dataset_list()
        async with async_session() as session:
            for ds in datasets:
                session_id = ds["session_id"]
                current_hash = ds["dataset_hash"]

                stored_hash = await cache.get_dataset_hash(session_id)
                if stored_hash == current_hash:
                    continue

                zip_bytes = await client.get_dataset(ds["access_key"])
                bills = _parse_dataset_zip(zip_bytes)
                for bill in bills:
                    await _process_bill(session, cache, bill, ds["state"])

                await cache.set_dataset_hash(session_id, current_hash)
    finally:
        await client.close()
        await cache.close()


def _parse_dataset_zip(zip_bytes: bytes) -> list[dict]:
    bills = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as f:
                data = json.load(f)
            bill = data.get("bill", data)
            bills.append(bill)
    return bills


def _extract_text(bill: dict) -> str | None:
    texts = bill.get("texts", [])
    if not texts:
        return None
    doc = texts[-1].get("doc", "")
    if not doc:
        return None
    try:
        return base64.b64decode(doc).decode("utf8")
    except Exception:
        return None


async def _process_bill(session, cache, bill: dict, state: str) -> None:
    legiscan_id = bill["bill_id"]
    is_co = state == "CO"
    text = _extract_text(bill)

    existing = await session.execute(select(Bill).where(Bill.legiscan_id == legiscan_id))
    db_bill = existing.scalar_one_or_none()
    if not db_bill:
        db_bill = Bill(
            legiscan_id=legiscan_id,
            state=state,
            session=bill.get("session", {}).get("session_name", ""),
            bill_number=bill.get("number", ""),
            title=bill.get("title", ""),
            is_corpus_only=not is_co,
            full_text=text if is_co else None,
        )
        session.add(db_bill)
        await session.flush()

    if not text:
        await session.commit()
        return

    m = compute_minhash(text)
    sig = MinHashSignature(bill_id=db_bill.id, signature=m.hashvalues.tolist())
    session.add(sig)
    await session.commit()
    await cache.set_bill_text(legiscan_id, text)
