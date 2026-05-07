from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

async def test_evidence_sets_verified_when_text_available():
    from worker.tasks.evidence import _extract_evidence_for_match

    co_text = "Preamble. The commission shall establish fees not to exceed one hundred dollars. End."
    src_text = "Intro. The commission shall establish fees not to exceed one hundred dollars. Close."

    mock_match = MagicMock()
    mock_match.id = uuid4()
    mock_match.bill_id = uuid4()
    mock_match.matched_bill_id = uuid4()

    mock_co_bill = MagicMock()
    mock_co_bill.legiscan_id = 1
    mock_corpus_bill = MagicMock()
    mock_corpus_bill.legiscan_id = 2

    mock_session = AsyncMock()
    mock_session.get.side_effect = [mock_co_bill, mock_corpus_bill]
    mock_session.commit = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_bill_text.side_effect = [co_text, src_text]
    mock_client = AsyncMock()

    await _extract_evidence_for_match(mock_session, mock_match, mock_cache, mock_client)

    assert mock_match.snippet_status == "verified"
    assert mock_match.matched_snippets is not None
    assert len(mock_match.matched_snippets) >= 1

async def test_evidence_sets_ghost_when_text_unavailable():
    from worker.tasks.evidence import _extract_evidence_for_match

    mock_match = MagicMock()
    mock_match.bill_id = uuid4()
    mock_match.matched_bill_id = uuid4()

    mock_co_bill = MagicMock()
    mock_co_bill.legiscan_id = 1
    mock_corpus_bill = MagicMock()
    mock_corpus_bill.legiscan_id = 2

    mock_session = AsyncMock()
    mock_session.get.side_effect = [mock_co_bill, mock_corpus_bill]
    mock_session.commit = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_bill_text.return_value = None
    mock_client = AsyncMock()
    mock_client.get_bill_text.return_value = None

    await _extract_evidence_for_match(mock_session, mock_match, mock_cache, mock_client)

    assert mock_match.snippet_status == "source_verified_text_missing"
