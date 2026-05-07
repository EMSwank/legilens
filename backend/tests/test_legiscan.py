import pytest
from unittest.mock import AsyncMock, patch
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
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset_list()
    assert len(result) == 2
    assert result[0]["state"] == "CO"
    assert result[0]["dataset_hash"] == "aaa"

async def test_get_dataset_list_returns_empty_on_missing_key(client):
    mock_response = {"status": "OK"}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset_list()
    assert result == []

async def test_get_dataset_returns_bytes(client):
    fake_zip = b"PK\x03\x04fakezipbytes"
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.content = fake_zip
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_dataset("abc123")
    assert result == fake_zip

async def test_get_bill_text_returns_text(client):
    mock_response = {"status": "OK", "bill": {"texts": [{"doc": "The bill text here."}]}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(12345)
    assert result == "The bill text here."

async def test_get_bill_text_returns_none_when_no_texts(client):
    mock_response = {"status": "OK", "bill": {"texts": []}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(99)
    assert result is None
