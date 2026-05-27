from decimal import Decimal
from uuid import UUID
from sqlalchemy import delete, select
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.models.similarity_match import SimilarityMatch
from app.models.ist_score import ISTScore
from app.services.minhash import minhash_from_signature, jaccard_estimate, build_lsh
from datasketch import MinHash


class CorpusIndex:
    """LSH-backed lookup over corpus MinHash signatures.

    LSH bucketing makes candidate retrieval sublinear in corpus size. The
    bands threshold (0.7) is set in build_lsh() to match our 70% Jaccard
    match threshold. False negatives at the boundary are possible but rare
    with NUM_PERM=128.
    """

    def __init__(self):
        self._lsh = build_lsh()
        self._lookup: dict[str, tuple] = {}

    def add(self, bill_id, state: str, bill_number: str, m: MinHash) -> None:
        key = str(bill_id)
        self._lsh.insert(key, m)
        self._lookup[key] = (bill_id, state, bill_number, m)

    def query(self, m: MinHash) -> list[tuple]:
        return [self._lookup[k] for k in self._lsh.query(m) if k in self._lookup]

    def __len__(self) -> int:
        return len(self._lookup)


async def match_co_bills():
    async with async_session() as session:
        # Idempotency: nuke prior match output for CO bills so re-runs (nightly
        # or two-pass bootstrap) don't accumulate duplicate ISTScore /
        # SimilarityMatch rows. Bills/list and bills/detail use scalar_one_or_none
        # on ISTScore and would 500 on duplicates.
        co_bill_ids = select(Bill.id).where(Bill.is_corpus_only.is_(False))
        await session.execute(delete(SimilarityMatch).where(SimilarityMatch.bill_id.in_(co_bill_ids)))
        await session.execute(delete(ISTScore).where(ISTScore.bill_id.in_(co_bill_ids)))
        await session.commit()

        # Build LSH-backed corpus index. With NUM_PERM=128 and bands threshold
        # 0.7, candidate retrieval is sublinear in corpus size — the prior
        # implementation did a full linear scan per CO bill (O(N*M) = ~12B
        # comparisons at current scale, days of wall-clock).
        corpus_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(True))
        )
        corpus = CorpusIndex()
        for sig, bill in corpus_result:
            corpus.add(bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))

        co_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
        )
        for sig, co_bill in co_result:
            co_m = minhash_from_signature(sig.signature)
            await _find_matches_for_bill(session, co_bill.id, co_m, corpus)

async def _find_matches_for_bill(session, co_bill_id: UUID, co_m, corpus: "CorpusIndex"):
    if len(corpus) == 0:
        score = ISTScore(
            bill_id=co_bill_id,
            source_authenticity_score=Decimal("100.00"),
            copycat_alert=False,
        )
        session.add(score)
        await session.commit()
        return

    candidates = corpus.query(co_m)

    max_similarity = Decimal("0.00")
    for corpus_bill_id, corpus_state, _, corpus_m in candidates:
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
