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


async def test_get_bill_doc_returns_billdoc_with_mime(client):
    import base64 as b64
    from app.services.legiscan import BillDoc

    body = b"%PDF-1.4 minimal pdf bytes"
    encoded = b64.b64encode(body).decode("ascii")
    mock_response = {
        "status": "OK",
        "text": {"doc_id": 999, "doc": encoded, "mime": "application/pdf"},
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert isinstance(result, BillDoc)
    assert result.raw == body
    assert result.mime == "application/pdf"


async def test_get_bill_doc_defaults_mime_to_empty_when_absent(client):
    import base64 as b64
    from app.services.legiscan import BillDoc

    body = b"some bytes"
    encoded = b64.b64encode(body).decode("ascii")
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": encoded}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert isinstance(result, BillDoc)
    assert result.mime == ""


async def test_get_bill_doc_returns_none_on_empty_doc(client):
    mock_response = {"status": "OK", "text": {"doc_id": 999, "doc": ""}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_doc(999)
    assert result is None


async def test_get_bill_doc_raises_on_non_ok(client):
    payload = {"status": "ERROR", "alert": {"message": "Doc not found"}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=payload)
        mock_get.return_value.raise_for_status = lambda: None
        with pytest.raises(ValueError, match="getBillText returned non-OK"):
            await client.get_bill_doc(999)


async def test_get_bill_text_by_doc_id_extracts_pdf(client):
    """Wrapper composition get_bill_doc -> extract_text on a REAL PDF.

    This is the only test that proves the evidence.py 'free fix' actually
    decodes PDFs. The doc field is the base64 of the minimal text-bearing PDF
    verified against pypdf 6.12.2.
    """
    pdf_b64 = (
        "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
        "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
        "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
        "NzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4g"
        "Pj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA3NyA+PgpzdHJlYW0KQlQgL0YxIDI0IFRm"
        "IDcyIDcwMCBUZCAoQmUgaXQgZW5hY3RlZCBieSB0aGUgR2VuZXJhbCBBc3NlbWJseSBMZWdpTGVu"
        "cykgVGogRVQKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9TdWJ0eXBl"
        "IC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAw"
        "MCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgniAKMDAwMDAw"
        "MDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzNjggMDAwMDAgniAKdHJh"
        "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0Y="
    )
    mock_response = {
        "status": "OK",
        "text": {"doc_id": 999, "doc": pdf_b64, "mime": "application/pdf"},
    }
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text_by_doc_id(999)
    assert result is not None
    assert "enacted" in result
