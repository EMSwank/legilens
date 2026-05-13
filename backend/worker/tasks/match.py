from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.models.similarity_match import SimilarityMatch
from app.models.ist_score import ISTScore
from app.services.minhash import minhash_from_signature, jaccard_estimate

async def match_co_bills():
    async with async_session() as session:
        corpus_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(True))
        )
        corpus_entries = [
            (bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))
            for sig, bill in corpus_result
        ]

        co_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
        )
        for sig, co_bill in co_result:
            co_m = minhash_from_signature(sig.signature)
            await _find_matches_for_bill(session, co_bill.id, co_m, corpus_entries)

async def _find_matches_for_bill(session, co_bill_id: UUID, co_m, corpus_entries: list):
    if not corpus_entries:
        score = ISTScore(
            bill_id=co_bill_id,
            source_authenticity_score=Decimal("100.00"),
            copycat_alert=False,
        )
        session.add(score)
        await session.commit()
        return

    max_similarity = Decimal("0.00")
    for corpus_bill_id, corpus_state, _, corpus_m in corpus_entries:
        sim = Decimal(str(round(jaccard_estimate(co_m, corpus_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue
        match = SimilarityMatch(
            bill_id=co_bill_id,
            matched_bill_id=corpus_bill_id,
            matched_state=corpus_state,
            similarity_score=sim,
            snippet_status="pending",
        )
        session.add(match)
        max_similarity = max(max_similarity, sim)

    authenticity = Decimal("100.00") - max_similarity
    score = ISTScore(
        bill_id=co_bill_id,
        source_authenticity_score=authenticity,
        copycat_alert=authenticity < Decimal("30.00"),
    )
    session.add(score)
    await session.commit()
