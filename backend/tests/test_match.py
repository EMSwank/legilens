import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.minhash import compute_minhash

async def test_match_writes_similarity_match_row():
    from worker.tasks.match import _find_matches_for_bill

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    corpus_entries = [(corpus_bill_id, "TX", "HB-1", corpus_m)]
    await _find_matches_for_bill(mock_session, co_bill_id, co_m, corpus_entries)

    mock_session.add.assert_called()

async def test_no_match_writes_score_of_100():
    from worker.tasks.match import _find_matches_for_bill

    co_m = compute_minhash("Completely unique Colorado bill text with no parallels anywhere.")
    corpus_entries = []

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_matches_for_bill(mock_session, uuid4(), co_m, corpus_entries)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    from app.models.ist_score import ISTScore
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_below_threshold_corpus_produces_no_match():
    from worker.tasks.match import _find_matches_for_bill
    from app.models.similarity_match import SimilarityMatch
    from app.models.ist_score import ISTScore

    co_m = compute_minhash("The quick brown fox jumps over the lazy dog in Colorado.")
    corpus_m = compute_minhash("Quantum entanglement is a physical phenomenon at subatomic scales.")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    corpus_entries = [(uuid4(), "TX", "HB-1", corpus_m)]
    await _find_matches_for_bill(mock_session, uuid4(), co_m, corpus_entries)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(a, SimilarityMatch) for a in added)
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_identical_match_sets_copycat_alert():
    from worker.tasks.match import _find_matches_for_bill
    from app.models.ist_score import ISTScore

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    corpus_entries = [(uuid4(), "TX", "HB-1", corpus_m)]
    await _find_matches_for_bill(mock_session, uuid4(), co_m, corpus_entries)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("0.00")
    assert scores[0].copycat_alert is True
