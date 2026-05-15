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

async def test_get_bill_text_returns_text(client):
    mock_response = {"status": "OK", "bill": {"texts": [{"doc": "The bill text here."}]}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(12345)
    assert result == "The bill text here."

async def test_get_bill_text_returns_none_when_no_texts(client):
    mock_response = {"status": "OK", "bill": {"texts": []}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(99)
    assert result is None

async def test_get_bill_text_returns_none_when_doc_is_none(client):
    mock_response = {"status": "OK", "bill": {"texts": [{"doc": None}]}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(12345)
    assert result is None
