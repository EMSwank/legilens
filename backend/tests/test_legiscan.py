import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.legiscan import LegiScanClient

@pytest.fixture
async def client():
    c = LegiScanClient(api_key="test_key")
    yield c
    await c.close()

async def test_get_dataset_list_returns_sessions(client):
    mock_response = {
        "status": "OK",
        "datasetlist": [
            {"session_id": 1, "state": "CO", "session_name": "2024A", "access_key": "abc123", "dataset_hash": "aaa"},
            {"session_id": 2, "state": "TX", "session_name": "2024R", "access_key": "def456", "dataset_hash": "bbb"},
        ]
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset_list()
    assert len(result) == 2
    assert result[0]["state"] == "CO"
    assert result[0]["dataset_hash"] == "aaa"

async def test_get_dataset_list_returns_empty_on_missing_key(client):
    mock_response = {"status": "OK"}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset_list()
    assert result == []

async def test_get_dataset_list_raises_on_error_status(client):
    payload = {"status": "ERROR", "alert": {"message": "API key has been administratively locked by LegiScan"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="non-OK status"):
            await client.get_dataset_list()


async def test_get_dataset_returns_bytes(client):
    import base64
    fake_zip = b"PK\x03\x04fakezipbytes"
    payload = {"status": "OK", "dataset": {"zip": base64.b64encode(fake_zip).decode()}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset(2243, "abc123")
    assert result == fake_zip


async def test_get_dataset_passes_id_and_access_key(client):
    import base64
    fake_zip = b"PK\x03\x04ok"
    payload = {"status": "OK", "dataset": {"zip": base64.b64encode(fake_zip).decode()}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        await client.get_dataset(2243, "abc123")
    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["id"] == 2243
    assert sent_params["access_key"] == "abc123"
    assert sent_params["op"] == "getDataset"


async def test_get_dataset_raises_on_error_status(client):
    payload = {"status": "ERROR", "alert": {"message": "Invalid session id"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="non-OK status"):
            await client.get_dataset(2243, "abc123")


async def test_get_dataset_raises_when_decoded_not_zip(client):
    import base64
    not_zip = base64.b64encode(b"not a zip file").decode()
    payload = {"status": "OK", "dataset": {"zip": not_zip}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="not a zip"):
            await client.get_dataset(2243, "abc123")

async def test_get_bill_returns_envelope(client):
    mock_response = {
        "status": "OK",
        "bill": {"bill_id": 12345, "texts": [{"doc_id": 999}]},
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        bill = await client.get_bill(12345)
    assert bill["bill_id"] == 12345
    assert bill["texts"][0]["doc_id"] == 999


async def test_get_bill_raises_on_non_ok(client):
    payload = {"status": "ERROR", "alert": {"message": "Bill not found"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="getBill returned non-OK"):
            await client.get_bill(12345)


async def test_get_bill_text_by_doc_id_decodes_base64(client):
    import base64 as b64
    body = "Be it enacted by the General Assembly..."
    encoded = b64.b64encode(body.encode("utf-8")).decode("ascii")
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": encoded}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text_by_doc_id(999)
    assert result == body


async def test_get_bill_text_by_doc_id_returns_none_on_empty_doc(client):
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": ""}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text_by_doc_id(999)
    assert result is None


async def test_get_bill_text_by_doc_id_returns_none_on_decode_error(client):
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": "not-valid-base64!@#"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text_by_doc_id(999)
    assert result is None


async def test_get_bill_text_by_doc_id_raises_on_non_ok(client):
    payload = {"status": "ERROR", "alert": {"message": "Doc not found"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="getBillText returned non-OK"):
            await client.get_bill_text_by_doc_id(999)
