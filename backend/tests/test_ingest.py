import base64
import io
import json
import logging
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.fixture(autouse=True)
def _zip_cache_tmpdir(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "legiscan_zip_cache_dir", str(tmp_path / "zip_cache"))
    yield tmp_path / "zip_cache"


def _make_zip(bills: list[dict], hash_md5_content: bytes | None = b"") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i, bill in enumerate(bills):
            zf.writestr(f"{i}.json", json.dumps({"bill": bill}).encode())
        if hash_md5_content is not None:
            zf.writestr("hash.md5", hash_md5_content)
    return buf.getvalue()

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
        "bill_number": "SB-1",
        "title": "Test Bill",
        "session": {"session_name": "2024A"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "TX")

    # bill select + signature upsert
    assert mock_session.execute.call_count == 2
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
        "bill_number": "HB-1",
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
        "bill_number": "HB-55",
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
        "bill_number": "SB-1",
        "title": "Existing Bill",
        "session": {"session_name": "2024A"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "CO")

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(a, Bill) for a in added)

async def test_process_bill_upserts_signature_on_repeat():
    """Second call for same bill_id must not raise — upsert replaces the signature."""
    from worker.tasks.ingest import _process_bill

    existing_bill = MagicMock()
    existing_bill.id = uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_bill
    sig_upsert_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [mock_result, sig_upsert_result]
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cache = AsyncMock()

    raw_text = "The commission shall establish fees not to exceed one hundred dollars."
    bill_data = {
        "bill_id": 42,
        "bill_number": "SB-1",
        "title": "Existing Bill",
        "session": {"session_name": "2024A"},
        "texts": [{"doc": base64.b64encode(raw_text.encode()).decode()}],
    }

    await _process_bill(mock_session, mock_cache, bill_data, "CO")

    # bill select + sig upsert — no session.add for MinHashSignature
    assert mock_session.execute.call_count == 2
    mock_session.add.assert_not_called()


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

    hash_result = MagicMock()
    hash_result.scalar.return_value = "same_hash"
    mock_session = AsyncMock()
    mock_session.execute.return_value = hash_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_client.get_dataset.assert_not_called()

async def test_ingest_downloads_changed_dataset():
    import io, json, zipfile
    from worker.tasks.ingest import ingest_all_states

    raw_text = "The commission shall establish fees."
    bill_json = json.dumps({
        "bill": {
            "bill_id": 99,
            "bill_number": "HB-99",
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

    hash_result = MagicMock()
    hash_result.scalar.return_value = "old_hash"
    bill_result = MagicMock()
    bill_result.scalar_one_or_none.return_value = None
    sig_upsert_result = MagicMock()
    dataset_hash_upsert_result = MagicMock()
    mock_session = AsyncMock()
    # hash check, bill select, sig upsert, dataset_hash upsert
    mock_session.execute.side_effect = [hash_result, bill_result, sig_upsert_result, dataset_hash_upsert_result]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_client.get_dataset.assert_called_once_with(2, "xyz")
    assert mock_session.execute.call_count == 4


async def test_ingest_continues_after_failed_dataset():
    import io
    import json
    import zipfile
    from worker.tasks.ingest import ingest_all_states

    good_bill_json = json.dumps({
        "bill": {
            "bill_id": 7, "bill_number": "HB-7", "title": "Good", "session": {"session_name": "2024A"},
            "texts": [],
        }
    }).encode()
    good_buf = io.BytesIO()
    with zipfile.ZipFile(good_buf, "w") as zf:
        zf.writestr("7.json", good_bill_json)
    good_zip = good_buf.getvalue()

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 1, "state": "TX", "access_key": "bad", "dataset_hash": "h1"},
        {"session_id": 2, "state": "CO", "access_key": "good", "dataset_hash": "h2"},
    ]
    mock_client.get_dataset.side_effect = [
        ValueError("getDataset returned non-zip response"),
        good_zip,
    ]

    mock_cache = AsyncMock()

    # Dataset 1 (TX): hash check only — get_dataset raises, rollback
    # Dataset 2 (CO): hash check, bill lookup (no text), upsert
    hash_miss = MagicMock()
    hash_miss.scalar.return_value = None
    bill_result = MagicMock()
    bill_result.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [hash_miss, hash_miss, bill_result, upsert_result]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_session.rollback.assert_awaited_once()
    assert mock_session.execute.call_count == 4


def test_read_hash_md5_plain_hash():
    from worker.tasks.ingest import _read_hash_md5
    h = "a" * 32
    zb = _make_zip([], hash_md5_content=h.encode())
    assert _read_hash_md5(zb) == h


def test_read_hash_md5_md5sum_format():
    from worker.tasks.ingest import _read_hash_md5
    h = "b" * 32
    zb = _make_zip([], hash_md5_content=f"{h}  payload.json\n".encode())
    assert _read_hash_md5(zb) == h


def test_read_hash_md5_missing_file():
    from worker.tasks.ingest import _read_hash_md5
    zb = _make_zip([], hash_md5_content=None)
    assert _read_hash_md5(zb) is None


def test_read_hash_md5_falls_back_to_last_file():
    from worker.tasks.ingest import _read_hash_md5
    # ZIP without hash.md5, last file is a manifest with an md5 hex string
    h = "9" * 32
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1.json", json.dumps({"bill": {"bill_id": 1}}).encode())
        zf.writestr("zz_manifest", h.encode())  # last file, no .md5 name
    assert _read_hash_md5(buf.getvalue()) == h


def test_read_hash_md5_invalid_returns_none():
    from worker.tasks.ingest import _read_hash_md5
    zb = _make_zip([], hash_md5_content=b"not-a-real-hash\n")
    assert _read_hash_md5(zb) is None


def test_zip_cache_roundtrip(_zip_cache_tmpdir):
    from worker.tasks.ingest import _load_cached_zip, _save_cached_zip
    assert _load_cached_zip(42) is None
    _save_cached_zip(42, b"payload")
    assert _load_cached_zip(42) == b"payload"


async def test_ingest_seeds_from_cached_zip_skips_download(_zip_cache_tmpdir):
    from worker.tasks.ingest import ingest_all_states, _save_cached_zip

    api_hash = "c" * 32
    bill = {
        "bill_id": 50, "bill_number": "HB-50", "title": "Cached",
        "session": {"session_name": "2024A"}, "texts": [],
    }
    cached_zip = _make_zip([bill], hash_md5_content=api_hash.encode())
    _save_cached_zip(7, cached_zip)

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 7, "state": "CO", "access_key": "k", "dataset_hash": api_hash}
    ]
    mock_cache = AsyncMock()

    hash_miss = MagicMock(); hash_miss.scalar.return_value = None
    bill_result = MagicMock(); bill_result.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [hash_miss, bill_result, upsert_result]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_client.get_dataset.assert_not_called()
    assert mock_session.execute.call_count == 3


async def test_ingest_warns_on_cached_vs_stored_divergence(_zip_cache_tmpdir, caplog):
    from worker.tasks.ingest import ingest_all_states, _save_cached_zip

    stored_hash = "d" * 32
    cached_hash = "e" * 32  # different from stored
    api_hash = "f" * 32     # different from both — forces download
    bill = {
        "bill_id": 51, "bill_number": "HB-51", "title": "Diverge",
        "session": {"session_name": "2024A"}, "texts": [],
    }
    cached_zip = _make_zip([bill], hash_md5_content=cached_hash.encode())
    _save_cached_zip(8, cached_zip)
    fresh_zip = _make_zip([bill], hash_md5_content=api_hash.encode())

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 8, "state": "CO", "access_key": "k", "dataset_hash": api_hash}
    ]
    mock_client.get_dataset.return_value = fresh_zip
    mock_cache = AsyncMock()

    hash_hit = MagicMock(); hash_hit.scalar.return_value = stored_hash
    bill_result = MagicMock(); bill_result.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [hash_hit, bill_result, upsert_result]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with caplog.at_level(logging.WARNING, logger="worker.tasks.ingest"), \
         patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    assert any("diverges from stored hash" in r.message for r in caplog.records)
    mock_client.get_dataset.assert_called_once_with(8, "k")


async def test_ingest_aborts_dataset_on_fresh_zip_hash_mismatch(_zip_cache_tmpdir, caplog):
    from worker.tasks.ingest import ingest_all_states

    api_hash = "1" * 32
    zip_internal_hash = "2" * 32  # corruption: ZIP says different hash than API
    bill = {
        "bill_id": 60, "bill_number": "HB-60", "title": "Corrupt",
        "session": {"session_name": "2024A"}, "texts": [],
    }
    fresh_zip = _make_zip([bill], hash_md5_content=zip_internal_hash.encode())

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 9, "state": "TX", "access_key": "k", "dataset_hash": api_hash}
    ]
    mock_client.get_dataset.return_value = fresh_zip
    mock_cache = AsyncMock()

    hash_miss = MagicMock(); hash_miss.scalar.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [hash_miss]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_called()


async def test_ingest_skips_non_int_session_id(_zip_cache_tmpdir, caplog):
    from worker.tasks.ingest import ingest_all_states

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": "../../etc/passwd", "state": "??", "access_key": "k", "dataset_hash": "x" * 32}
    ]
    mock_cache = AsyncMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with caplog.at_level(logging.WARNING, logger="worker.tasks.ingest"), \
         patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_client.get_dataset.assert_not_called()
    mock_session.execute.assert_not_called()
    assert any("non-int session_id" in r.message for r in caplog.records)


async def test_ingest_skips_dataset_with_missing_schema_keys():
    import io
    import json
    import zipfile
    from worker.tasks.ingest import ingest_all_states

    good_bill_json = json.dumps({
        "bill": {
            "bill_id": 11, "bill_number": "HB-11", "title": "Good", "session": {"session_name": "2024A"},
            "texts": [],
        }
    }).encode()
    good_buf = io.BytesIO()
    with zipfile.ZipFile(good_buf, "w") as zf:
        zf.writestr("11.json", good_bill_json)
    good_zip = good_buf.getvalue()

    mock_client = AsyncMock()
    mock_client.get_dataset_list.return_value = [
        {"session_id": 99},
        {"session_id": 2, "state": "CO", "access_key": "good", "dataset_hash": "h2"},
    ]
    mock_client.get_dataset.return_value = good_zip

    mock_cache = AsyncMock()

    # Dataset 99: KeyError at ds["dataset_hash"] — no execute calls, rollback
    # Dataset 2 (CO): hash check, bill lookup (no text), upsert
    hash_miss = MagicMock()
    hash_miss.scalar.return_value = None
    bill_result = MagicMock()
    bill_result.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [hash_miss, bill_result, upsert_result]
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingest.LegiScanClient", return_value=mock_client), \
         patch("worker.tasks.ingest.RedisCache", return_value=mock_cache), \
         patch("worker.tasks.ingest.async_session", return_value=mock_session):
        await ingest_all_states()

    mock_session.rollback.assert_awaited_once()
    assert mock_session.execute.call_count == 3
