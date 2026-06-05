import logging
import time
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

logger = logging.getLogger(__name__)


class CorpusIndex:
    """LSH-backed lookup over corpus MinHash signatures.

    LSH bucketing makes candidate retrieval sublinear in corpus size. The
    LSH threshold (0.7) is calibrated with weights=(0.1, 0.9) in build_lsh()
    so that candidates are a SUPERSET of true matches above the 70% Jaccard
    cutoff (~92% recall at s=0.70, ~100% above s=0.80). The exact 70% filter
    in _find_matches_for_bill is the precision gate. NUM_PERM=128 controls
    variance, not recall rate.

    Memory: each entry holds the MinHash (1024 B of uint64 hashvalues) in
    the lookup plus the LSH band hashtables. At the deployed corpus scale
    (~750k-1M bills) the index resident set is ~1.5-3 GB. The Railway
    worker container must have headroom; if memory becomes the binding
    constraint, switch query() to a streaming corpus pattern (drop the
    MinHash refs after LSH insertion, re-deserialize candidate sigs from
    DB on demand).

    Duplicate keys: datasketch MinHashLSH.insert raises ValueError on
    duplicate keys. The DB schema does not enforce uniqueness on
    MinHashSignature.bill_id (ingest can produce duplicate signature rows
    if a bill is re-processed), so add() drops the duplicate with a
    warning instead of letting the entire match phase crash. Callers that
    want the freshest signature should pre-filter with
    `DISTINCT ON (bill_id) ... ORDER BY bill_id, computed_at DESC`.
    """

    def __init__(self):
        self._lsh = build_lsh()
        self._lookup: dict[str, tuple[UUID, str, str, MinHash]] = {}

    def add(self, bill_id: UUID, state: str, bill_number: str, m: MinHash) -> None:
        key = str(bill_id)
        if key in self._lookup:
            logger.warning(
                "CorpusIndex.add: duplicate bill_id=%s (state=%s number=%s); "
                "keeping first signature, dropping duplicate. Fix the ingest "
                "dedup or the corpus query DISTINCT ON to avoid this.",
                bill_id, state, bill_number,
            )
            return
        self._lsh.insert(key, m)
        self._lookup[key] = (bill_id, state, bill_number, m)

    def query(self, m: MinHash) -> list[tuple[UUID, str, str, MinHash]]:
        return [self._lookup[k] for k in self._lsh.query(m) if k in self._lookup]

    def __len__(self) -> int:
        return len(self._lookup)


# Two-pass pipeline (cross-state corpus index + CO-internal index + per-pass
# timers) inherently needs many locals; the count is structural, not bloat.
async def match_co_bills():  # pylint: disable=too-many-locals
    async with async_session() as session:
        # Idempotency: nuke prior match output for CO bills so re-runs (nightly
        # or two-pass bootstrap) don't accumulate duplicate ISTScore /
        # SimilarityMatch rows. Bills/list and bills/detail use scalar_one_or_none
        # on ISTScore and would 500 on duplicates.
        #
        # PERF (load-bearing): the DELETE is NOT committed here. The whole run —
        # delete + every CO ISTScore/SimilarityMatch insert — is staged in ONE
        # transaction and committed exactly once at the end of this function. The
        # per-bill helpers (_find_matches_for_bill / _find_co_internal_matches)
        # only session.add(); they must NEVER commit. The previous code committed
        # once per CO bill inside the pass-1 loop: 6997 serial INSERT+COMMIT round
        # trips to EU-West Neon at ~0.53s each = 3693s (61.5 min) in prod. Pass 2
        # looked ~25x faster only because its no-match commits were no-ops (no
        # pending rows → no round trip). A single batched commit collapses 6997
        # round trips to one flush and makes the delete+rebuild an atomic swap
        # (readers see last run's scores via MVCC until commit; a mid-run failure
        # rolls back to the prior night instead of leaving a half-rebuilt table).
        co_bill_ids = select(Bill.id).where(Bill.is_corpus_only.is_(False))
        await session.execute(delete(SimilarityMatch).where(SimilarityMatch.bill_id.in_(co_bill_ids)))
        await session.execute(delete(ISTScore).where(ISTScore.bill_id.in_(co_bill_ids)))

        # Build LSH-backed corpus index. With NUM_PERM=128 and bands threshold
        # 0.7, candidate retrieval is sublinear in corpus size — the prior
        # implementation did a full linear scan per CO bill (O(N*M) = ~12B
        # comparisons at current scale, days of wall-clock).
        t_index_start = time.monotonic()
        # DISTINCT ON (bill_id) + ORDER BY computed_at DESC defends against
        # ingest producing duplicate MinHashSignature rows per bill — without
        # this, MinHashLSH.insert would raise on the second occurrence and
        # crash the whole match phase. CorpusIndex.add also has a defensive
        # duplicate guard, but skipping duplicates at the query level means
        # we always load the freshest signature, not the first one.
        corpus_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(True))
            .distinct(MinHashSignature.bill_id)
            .order_by(MinHashSignature.bill_id, MinHashSignature.computed_at.desc())
        )
        corpus = CorpusIndex()
        for sig, bill in corpus_result:
            corpus.add(bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))
        logger.info(
            "match: built LSH corpus index with %d bills in %.2fs",
            len(corpus), time.monotonic() - t_index_start,
        )

        # Materialize CO signatures once; reused by both passes. Same DISTINCT ON
        # guard as the corpus side: duplicate signatures per CO bill would
        # double-score the bill (extra SimilarityMatch rows and a wrong final
        # ISTScore from re-running max_similarity).
        co_rows = (await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
            .distinct(MinHashSignature.bill_id)
            .order_by(MinHashSignature.bill_id, MinHashSignature.computed_at.desc())
        )).all()
        # (bill_id, state, bill_number, title, MinHash) — MinHash computed once.
        co_entries = [
            (bill.id, bill.state, bill.bill_number, bill.title, minhash_from_signature(sig.signature))
            for sig, bill in co_rows
        ]

        # Pass 1 — cross-state scoring (writes cross_state SimilarityMatch + ISTScore).
        t_match_start = time.monotonic()
        for bill_id, _state, _number, _title, co_m in co_entries:
            await _find_matches_for_bill(session, bill_id, co_m, corpus)
        logger.info(
            "match: scored %d CO bills against cross-state corpus in %.2fs",
            len(co_entries), time.monotonic() - t_match_start,
        )

        # Pass 2 — CO-internal related bills (writes co_internal SimilarityMatch
        # ONLY; never ISTScore — honesty guard so copycat_alert stays cross-
        # state-only). Build a second index from the CO bills themselves.
        t_co_start = time.monotonic()
        co_index = CorpusIndex()
        co_meta: dict[UUID, tuple[str, str]] = {}
        for bill_id, state, number, title, co_m in co_entries:
            co_index.add(bill_id, state, number, co_m)
            co_meta[bill_id] = (number, title)
        for bill_id, _state, _number, _title, co_m in co_entries:
            await _find_co_internal_matches(session, bill_id, co_m, co_index, co_meta)
        logger.info(
            "match: co-internal related-bills pass over %d CO bills in %.2fs",
            len(co_entries), time.monotonic() - t_co_start,
        )

        # Single batched commit for the whole run (see the PERF note at the top
        # of this function). Flushes the delete + all staged ISTScore /
        # SimilarityMatch inserts in one transaction. SQLAlchemy's
        # insertmanyvalues batches the ~7k inserts into a handful of multi-row
        # statements, so this is ~tens of round trips total, not one per bill.
        t_commit_start = time.monotonic()
        await session.commit()
        logger.info("match: committed all CO match output in %.2fs", time.monotonic() - t_commit_start)

async def _find_matches_for_bill(session, co_bill_id: UUID, co_m, corpus: CorpusIndex):
    """Stage one CO bill's ISTScore (+ any cross_state SimilarityMatch) rows.

    COMMIT CONTRACT (load-bearing perf, see match_co_bills): session.add() ONLY,
    never commit. match_co_bills batches a single commit for the whole run. A
    per-bill commit here reintroduces 6997 serial round trips to Neon (3693s).
    """
    if len(corpus) == 0:
        score = ISTScore(
            bill_id=co_bill_id,
            source_authenticity_score=Decimal("100.00"),
            copycat_alert=False,
        )
        session.add(score)
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
            # This branch never produces co_internal: Pass 1's corpus index is
            # built only from is_corpus_only=True bills (see line ~93), and CO
            # bills are always is_corpus_only=False, so corpus_state is never
            # "CO" here. Real co_internal rows are written by Pass 2
            # (_find_co_internal_matches), not this function. The ternary is kept
            # as a defensive guard for if/when CO bills ever enter this corpus
            # (which would also need a self-match guard above).
            match_type="co_internal" if corpus_state == "CO" else "cross_state",
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


def _normalize_bill_number(number: str) -> str:
    """Collapse whitespace and upcase so 'hb 1234' and 'HB1234' compare equal.

    Used by the CO-internal pass companion-noise guard: two CO bill rows with the
    same normalized number are version/session duplicates of one bill, not a real
    related pair. (Refinement deferred per spec section 8: a rare cross-session
    reintroduction that kept the same number would also be dropped; the de-risk
    probe found only 1 same-number pair total, so MVP drops it. If valuable later,
    tighten to 'same number AND same session'.)
    """
    return "".join(number.split()).upper()


async def _find_co_internal_matches(session, co_bill_id: UUID, co_m, co_index: CorpusIndex, co_meta: dict):
    """Write co_internal SimilarityMatch rows for one CO bill against the CO index.

    HONESTY GUARD: writes SimilarityMatch rows ONLY. Never creates/modifies
    ISTScore — copycat_alert is computed solely from the cross-state corpus in
    _find_matches_for_bill, which never contains CO bills. Each unordered pair
    {A,B} is found twice (A->B and B->A); accepted, each bill's detail page shows
    its own related bills (spec section 3).

    COMMIT CONTRACT (load-bearing perf, see match_co_bills): session.add() ONLY,
    never commit. The single batched commit is owned by match_co_bills.
    """
    self_number = _normalize_bill_number(co_meta[co_bill_id][0])
    for cand_id, _cand_state, cand_number, cand_m in co_index.query(co_m):
        if cand_id == co_bill_id:
            continue  # self-guard
        if _normalize_bill_number(cand_number) == self_number:
            continue  # companion-noise guard
        sim = Decimal(str(round(jaccard_estimate(co_m, cand_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue  # precision gate (LSH candidates are a superset)
        session.add(SimilarityMatch(
            bill_id=co_bill_id,
            matched_bill_id=cand_id,
            matched_state="CO",
            matched_bill_title=co_meta[cand_id][1],
            similarity_score=sim,
            snippet_status="pending",
            match_type="co_internal",
        ))
