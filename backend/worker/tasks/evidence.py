from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.similarity_match import SimilarityMatch
from app.services.legiscan import LegiScanClient
from app.services.redis_cache import RedisCache
from app.services.snippet_extractor import extract_snippets
from app.config import settings


def _add_kind_to_snippets(snippets: list[dict]) -> list[dict]:
    """Add 'kind': 'snippet' to each snippet dict for discriminated union.

    Snippets are stored in the DB with kind='snippet'. GhostMessages (kind='ghost')
    are never stored; they are synthesized at read time by the router when
    snippet_status == 'source_verified_text_missing' and matched_snippets is None.
    """
    return [{"kind": "snippet", **snippet} for snippet in snippets]


async def _fetch_text_via_api(bill: Bill, client: LegiScanClient) -> str | None:
    """Two-step fallback: use stored text_doc_id if available, else discover via getBill.

    Using the correct LegiScan endpoints:
      1. getBillText(doc_id) → base64 body  (preferred — 1 API call)
      2. getBill(bill_id) → texts[].doc_id, then getBillText(doc_id)  (2 calls, discovery path)
    """
    doc_id = bill.text_doc_id
    if not doc_id:
        try:
            envelope = await client.get_bill(bill.legiscan_id)
            texts = envelope.get("texts", [])
            if texts:
                doc_id = texts[-1].get("doc_id")
        except Exception:  # pylint: disable=broad-exception-caught
            return None
    if not doc_id:
        return None
    try:
        return await client.get_bill_text_by_doc_id(doc_id)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


async def extract_all_pending_evidence():
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    cache = RedisCache(url=settings.redis_url)
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SimilarityMatch).where(SimilarityMatch.snippet_status == "pending")
            )
            for match in result.scalars():
                await _extract_evidence_for_match(session, match, cache, client)
    finally:
        await client.close()
        await cache.close()


async def _extract_evidence_for_match(session, match, cache, client):
    co_bill = await session.get(Bill, match.bill_id)
    corpus_bill = await session.get(Bill, match.matched_bill_id)

    # CO bill: full_text set after fetch phase; fall back to cache then API
    co_text = co_bill.full_text or await cache.get_bill_text(co_bill.legiscan_id)
    if not co_text:
        co_text = await _fetch_text_via_api(co_bill, client)
        if co_text:
            await cache.set_bill_text(co_bill.legiscan_id, co_text)

    # Corpus bill: stored in cache from ingest; fall back to API on cache miss
    src_text = await cache.get_bill_text(corpus_bill.legiscan_id)
    if not src_text:
        src_text = await _fetch_text_via_api(corpus_bill, client)
        if src_text:
            await cache.set_bill_text(corpus_bill.legiscan_id, src_text)

    if not co_text or not src_text:
        match.snippet_status = "source_verified_text_missing"
        match.matched_snippets = None
        await session.commit()
        return

    snippets = extract_snippets(co_text, src_text)
    match.matched_snippets = _add_kind_to_snippets(snippets)
    match.snippet_status = "verified"
    await session.commit()
