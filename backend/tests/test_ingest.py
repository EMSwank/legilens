import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

async def test_process_bill_stores_signature():
    from worker.tasks.ingest import _process_bill

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cache = AsyncMock()

    raw_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted."
    bill_data = {
        "bill_id": 42,
        "number": "SB-1",
        "title": "Test Bill",
        "session": {"session_name": "2024A"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "TX")

    mock_session.add.assert_called()
    mock_cache.set_bill_text.assert_called_once_with(42, raw_text)

async def test_process_bill_stores_bill_only_when_no_text():
    from worker.tasks.ingest import _process_bill
    from app.models.minhash_signature import MinHashSignature

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cache = AsyncMock()

    bill_data = {
        "bill_id": 1,
        "number": "HB-1",
        "title": "No Text Bill",
        "session": {"session_name": "2024A"},
        "texts": [],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "TX")

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(obj, MinHashSignature) for obj in added)
    mock_cache.set_bill_text.assert_not_called()

async def test_process_bill_sets_corpus_only_for_non_co_state():
    from worker.tasks.ingest import _process_bill
    from app.models.bill import Bill

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cache = AsyncMock()

    raw_text = "The commission shall establish fees not to exceed one hundred dollars per application."
    bill_data = {
        "bill_id": 55,
        "number": "HB-55",
        "title": "TX Bill",
        "session": {"session_name": "2024R"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "TX")

    added = [call.args[0] for call in mock_session.add.call_args_list]
    bills = [a for a in added if isinstance(a, Bill)]
    assert len(bills) == 1
    assert bills[0].is_corpus_only is True
    assert bills[0].full_text is None

async def test_process_bill_skips_insert_for_existing_bill():
    from worker.tasks.ingest import _process_bill
    from app.models.bill import Bill

    existing_bill = MagicMock()
    existing_bill.id = uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_bill
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cache = AsyncMock()

    raw_text = "The commission shall establish fees not to exceed one hundred dollars."
    bill_data = {
        "bill_id": 42,
        "number": "SB-1",
        "title": "Existing Bill",
        "session": {"session_name": "2024A"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "CO")

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(a, Bill) for a in added)

async def test_extract_text_returns_none_for_invalid_base64():
    from worker.tasks.ingest import _extract_text

    result = _extract_text({"texts": [{"doc": "!!!not-valid-base64!!!"}]})
    assert result is None

async def test_ingest_skips_unchanged_dataset():
    from worker.tasks.ingest import ingest_all_states

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 1, "state": "CO", "access_key": "abc", "dataset_hash": "same_hash"}
    ]
    mock_cache = AsyncMock()
    mock_cache.get_dataset_hash.return_value = "same_hash"

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache):
        await ingest_all_states()

    mock_client.get_dataset.assert_not_called()

async def test_ingest_downloads_changed_dataset():
    import io, json, zipfile
    from worker.tasks.ingest import ingest_all_states

    raw_text = "The commission shall establish fees."
    bill_json = json.dumps({
        "bill": {
            "bill_id": 99,
            "number": "HB-99",
            "title": "Changed Bill",
            "session": {"session_name": "2024A"},
            "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
        }
    }).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("99.json", bill_json)
    zip_bytes = buf.getvalue()

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 2, "state": "TX", "access_key": "xyz", "dataset_hash": "new_hash"}
    ]
    mock_client.get_dataset.return_value = zip_bytes

    mock_cache = AsyncMock()
    mock_cache.get_dataset_hash.return_value = "old_hash"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_client.get_dataset.assert_called_once_with("xyz")
    mock_cache.set_dataset_hash.assert_called_once_with(2, "new_hash")
