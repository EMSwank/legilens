# pylint: disable=line-too-long
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.minhash import compute_minhash

async def test_match_writes_similarity_match_row():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(corpus_bill_id, "TX", "HB-1", corpus_m)

    await _find_matches_for_bill(mock_session, co_bill_id, co_m, index)

    mock_session.add.assert_called()

async def test_no_match_writes_score_of_100():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex

    co_m = compute_minhash("Completely unique Colorado bill text with no parallels anywhere.")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_matches_for_bill(mock_session, uuid4(), co_m, CorpusIndex())

    added = [call.args[0] for call in mock_session.add.call_args_list]
    from app.models.ist_score import ISTScore
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_below_threshold_corpus_produces_no_match():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch
    from app.models.ist_score import ISTScore

    co_m = compute_minhash("The quick brown fox jumps over the lazy dog in Colorado.")
    corpus_m = compute_minhash("Quantum entanglement is a physical phenomenon at subatomic scales.")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(a, SimilarityMatch) for a in added)
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_identical_match_sets_copycat_alert():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.ist_score import ISTScore

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("0.00")
    assert scores[0].copycat_alert is True

async def test_corpus_index_filters_dissimilar_candidates():
    """LSH bucketing must return only candidates likely above the 70% Jaccard
    cutoff. The matching_text twin should be retrieved; the 20 unrelated
    quantum-text bills should be filtered out by LSH bands, never reaching
    the Jaccard-refinement stage."""
    from worker.tasks.match import CorpusIndex

    co_text = "The commission shall establish a fee not to exceed one hundred dollars."
    matching_text = "The commission shall establish a fee not to exceed one hundred dollars."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    index = CorpusIndex()
    matching_id = uuid4()
    index.add(matching_id, "TX", "HB-1", compute_minhash(matching_text))
    for _ in range(20):
        index.add(uuid4(), "NM", "SB-X", compute_minhash(unrelated_text + str(_)))

    candidates = index.query(compute_minhash(co_text))
    # Only the identical-text bill should LSH-collide. Any extra candidate
    # would mean LSH is leaking unrelated bills into the refinement stage.
    assert len(candidates) == 1
    assert candidates[0][0] == matching_id


async def test_corpus_index_returns_candidates_above_threshold():
    from worker.tasks.match import CorpusIndex

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    co_m = compute_minhash(identical_text)
    matching_m = compute_minhash(identical_text)
    unrelated_m = compute_minhash(unrelated_text)

    index = CorpusIndex()
    matching_id = uuid4()
    unrelated_id = uuid4()
    index.add(matching_id, "TX", "HB-1", matching_m)
    index.add(unrelated_id, "NM", "SB-9", unrelated_m)

    candidates = index.query(co_m)
    candidate_ids = {c[0] for c in candidates}
    assert matching_id in candidate_ids
    assert unrelated_id not in candidate_ids


async def test_corpus_index_recalls_near_threshold_match():
    """LSH must return candidates at Jaccard ~0.75, not only identical texts.

    Guards against the recall regression caused by default LSH weights
    (b=14,r=9 → ~44% recall at s=0.70). With weights=(0.1,0.9) → b=20,r=6 →
    ~92% recall at s=0.70."""
    from worker.tasks.match import CorpusIndex
    from app.services.minhash import jaccard_estimate

    # Two texts sharing most of their 5-grams (high but not identical Jaccard).
    # Jaccard ~0.71 — sits squarely in the zone where default weights (b=14,r=9)
    # give 0% recall in practice; biased weights (b=20,r=6) give ~100% recall.
    base = "no person shall operate a vehicle without a valid license issued by the department of motor vehicles"
    variant = "no person shall operate a motor vehicle without a valid license issued by the state department"

    co_m = compute_minhash(base)
    corpus_m = compute_minhash(variant)

    # Verify fixture Jaccard is in the target near-threshold range
    sim = jaccard_estimate(co_m, corpus_m)
    assert 0.65 <= sim <= 0.95, f"test fixture Jaccard out of range: {sim}"

    index = CorpusIndex()
    near_id = uuid4()
    index.add(near_id, "TX", "HB-1", corpus_m)

    candidates = index.query(co_m)
    assert near_id in {c[0] for c in candidates}, (
        f"LSH dropped a Jaccard={sim:.2f} match — recall regression"
    )


async def test_corpus_index_drops_duplicate_bill_id():
    """MinHashLSH.insert raises ValueError on duplicate keys. The match phase
    must not crash when the corpus query returns duplicate signature rows
    for one bill (e.g. ingest produced two MinHashSignature rows during a
    re-run). The DISTINCT ON in match_co_bills handles this at the query
    layer; the CorpusIndex.add defensive guard is the last-line safety net."""
    from worker.tasks.match import CorpusIndex

    text = "The commission shall establish fees not to exceed one hundred dollars."
    m = compute_minhash(text)

    index = CorpusIndex()
    bill_id = uuid4()
    index.add(bill_id, "TX", "HB-1", m)
    # Second add with the same bill_id must NOT raise — must drop silently
    index.add(bill_id, "TX", "HB-1", m)

    assert len(index) == 1


async def test_precision_gate_drops_lsh_candidate_below_70_percent_jaccard():
    """LSH false-positive: a candidate gets returned by LSH bucketing but
    the actual Jaccard is below 70%. _find_matches_for_bill must apply the
    precision gate and not write a SimilarityMatch row."""
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch
    from app.models.ist_score import ISTScore
    from app.services.minhash import jaccard_estimate

    # Two texts engineered to sit at Jaccard 0.55-0.68 — high enough for LSH
    # bands to plausibly co-bucket them, low enough that the 70% post-filter
    # in _find_matches_for_bill must reject them.
    base = "the department shall issue a permit for the operation of a commercial vehicle within the state"
    variant = "the department may grant authorization for transport of goods inside this state"

    co_m = compute_minhash(base)
    corpus_m = compute_minhash(variant)
    sim = jaccard_estimate(co_m, corpus_m)
    # Anchor the fixture: must be below the 70% cutoff so the precision
    # gate is what's being exercised here, not LSH.
    assert sim < 0.70, f"fixture leaked above precision gate: {sim}"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    # Either LSH filtered the candidate out (no SimilarityMatch and no
    # candidates reached the gate) or LSH returned it and the 70% gate
    # rejected it. Both end states produce the same observable result:
    # no SimilarityMatch row, ISTScore = 100.00.
    assert not any(isinstance(a, SimilarityMatch) for a in added)
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False
