import base64
import binascii
import io
import json
import logging
import re
import zipfile
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import async_session
from app.models.bill import Bill
from app.models.dataset_hash import DatasetHash
from app.models.minhash_signature import MinHashSignature
from app.services.legiscan import LegiScanClient
from app.services.minhash import compute_minhash
from app.services.redis_cache import RedisCache
from app.config import settings

logger = logging.getLogger(__name__)

_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


def _zip_cache_path(session_id: int) -> Path:
    return Path(settings.legiscan_zip_cache_dir) / f"{session_id}.zip"


def _read_hash_md5(zip_bytes: bytes) -> str | None:
    """Read dataset hash manifest from a LegiScan ZIP.

    Tries 'hash.md5' by name, then falls back to the last file in the archive
    (per LegiScan_Bulk PHP utility). Returns lowercase md5 hex, or None.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return None
    with zf:
        candidates: list[bytes] = []
        try:
            candidates.append(zf.read("hash.md5"))
        except KeyError:
            pass
        names = zf.namelist()
        if names:
            try:
                candidates.append(zf.read(names[-1]))
            except KeyError:
                pass
    for raw in candidates:
        lines = [ln for ln in raw.decode("utf-8", errors="replace").splitlines() if ln.strip()]
        if not lines:
            continue
        token = lines[0].strip().split()[0].lower()
        if _MD5_RE.match(token):
            return token
    return None


def _load_cached_zip(session_id: int) -> bytes | None:
    path = _zip_cache_path(session_id)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _save_cached_zip(session_id: int, zip_bytes: bytes) -> None:
    path = _zip_cache_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".zip.tmp")
    tmp.write_bytes(zip_bytes)
    tmp.replace(path)


async def _acquire_zip(client, session_id: int, state: str, current_hash: str,
                       stored_hash: str | None, access_key: str) -> bytes:
    cached_zip = _load_cached_zip(session_id)
    if cached_zip is not None:
        cached_md5 = _read_hash_md5(cached_zip)
        if stored_hash is not None and cached_md5 is not None and cached_md5 != stored_hash:
            logger.warning(
                "dataset session_id=%s state=%s: cached ZIP hash.md5 %s diverges from stored hash %s",
                session_id, state, cached_md5, stored_hash,
            )
        if cached_md5 == current_hash:
            logger.info(
                "dataset session_id=%s state=%s: seeding from cached ZIP (hash %s)",
                session_id, state, cached_md5,
            )
            return cached_zip

    zip_bytes = await client.get_dataset(session_id, access_key)
    fresh_md5 = _read_hash_md5(zip_bytes)
    if fresh_md5 is None:
        logger.info(
            "dataset session_id=%s state=%s: no parseable hash.md5 manifest in fresh ZIP",
            session_id, state,
        )
    elif fresh_md5 != current_hash:
        raise ValueError(
            f"dataset session_id={session_id} state={state}: fresh ZIP hash.md5 "
            f"{fresh_md5} != API dataset_hash {current_hash}"
        )
    _save_cached_zip(session_id, zip_bytes)
    return zip_bytes


async def ingest_all_states(datasets: list[dict] | None = None):
    """Ingest every LegiScan dataset in `datasets`, or fetch the full list if
    None. Callers that want to scope to one state must pre-filter via
    LegiScanClient.get_dataset_list(state=...) — the datasetlist payload has
    no state_abbr field, so client-side filtering by abbr is impossible.
    """
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    cache = RedisCache(url=settings.redis_url)
    try:
        if datasets is None:
            datasets = await client.get_dataset_list()
        for ds in datasets:
            session_id = ds.get("session_id")
            state = ds.get("state", "?")
            if not isinstance(session_id, int):
                logger.warning(
                    "dataset has non-int session_id=%r state=%s, skipping",
                    session_id, state,
                )
                continue
            async with async_session() as session:
                try:
                    current_hash = ds["dataset_hash"]
                    access_key = ds["access_key"]

                    stored = await session.execute(
                        select(DatasetHash.hash).where(DatasetHash.session_id == session_id)
                    )
                    stored_hash = stored.scalar()
                    if stored_hash == current_hash:
                        continue

                    zip_bytes = await _acquire_zip(
                        client, session_id, state, current_hash, stored_hash, access_key
                    )
                    for bill in _parse_dataset_zip(zip_bytes):
                        await _process_bill(session, cache, bill, state)

                    await session.execute(
                        pg_insert(DatasetHash)
                        .values(session_id=session_id, hash=current_hash)
                        .on_conflict_do_update(
                            index_elements=["session_id"],
                            set_={"hash": current_hash, "updated_at": func.now()},
                        )
                    )
                    await session.commit()
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to ingest dataset session_id=%s state=%s - skipping", session_id, state)
                    await session.rollback()
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
            bill = data.get("bill")
            if not isinstance(bill, dict) or not bill.get("bill_id"):
                continue
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
    except (binascii.Error, UnicodeDecodeError):
        return None


async def _process_bill(session, cache, bill: dict, state: str) -> None:
    legiscan_id = bill.get("bill_id")
    if not legiscan_id:
        return
    state = bill.get("state") or state
    is_co = state == "CO"
    text = _extract_text(bill)

    existing = await session.execute(select(Bill).where(Bill.legiscan_id == legiscan_id))
    db_bill = existing.scalar_one_or_none()
    if not db_bill:
        db_bill = Bill(
            legiscan_id=legiscan_id,
            state=state,
            session=bill.get("session", {}).get("session_name", ""),
            bill_number=bill.get("bill_number", ""),
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
