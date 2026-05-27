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

async def test_match_co_bills_skips_unrelated_corpus_via_lsh():
    """When LSH filters out unrelated bills, _find_matches_for_bill should
    never be called with them as candidates — verified by checking the
    candidate count exposed by CorpusIndex."""
    from worker.tasks.match import CorpusIndex

    co_text = "The commission shall establish a fee not to exceed one hundred dollars."
    matching_text = "The commission shall establish a fee not to exceed one hundred dollars."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", compute_minhash(matching_text))
    for _ in range(20):
        index.add(uuid4(), "NM", "SB-X", compute_minhash(unrelated_text + str(_)))

    candidates = index.query(compute_minhash(co_text))
    # LSH should return only the truly similar bill, not all 21 corpus entries
    assert 1 <= len(candidates) < 5


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
