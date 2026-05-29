import base64

from app.services.text_extraction import extract_text

# Minimal valid PDF with a text layer reading:
# "Be it enacted by the General Assembly LegiLens"
# Verified against pypdf 6.12.2.
PDF_WITH_TEXT_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
    "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
    "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
    "NzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4g"
    "Pj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA3NyA+PgpzdHJlYW0KQlQgL0YxIDI0IFRm"
    "IDcyIDcwMCBUZCAoQmUgaXQgZW5hY3RlZCBieSB0aGUgR2VuZXJhbCBBc3NlbWJseSBMZWdpTGVu"
    "cykgVGogRVQKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9TdWJ0eXBl"
    "IC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAw"
    "MCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAw"
    "MDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzNjggMDAwMDAgbiAKdHJh"
    "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0Y="
)

# Minimal valid PDF, single blank page, no text content stream.
# pypdf parses it successfully and extracts the empty string.
PDF_NO_TEXT_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
    "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
    "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
    "NzkyXSA+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAw"
    "MDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAp0cmFpbGVyCjw8"
    "IC9TaXplIDQgL1Jvb3QgMSAwIFIgPj4Kc3RhcnR4cmVmCjE4NgolJUVPRg=="
)


def _pdf_with_text() -> bytes:
    return base64.b64decode(PDF_WITH_TEXT_B64)


def _pdf_no_text() -> bytes:
    return base64.b64decode(PDF_NO_TEXT_B64)


def test_extract_pdf_returns_text():
    result = extract_text(_pdf_with_text(), "application/pdf")
    assert result is not None
    assert "enacted" in result


def test_extract_pdf_via_magic_bytes_when_mime_empty():
    # mime absent but bytes are a genuine PDF -> still routed to pypdf
    result = extract_text(_pdf_with_text(), "")
    assert result is not None
    assert "LegiLens" in result


def test_extract_pdf_no_text_layer_returns_none():
    assert extract_text(_pdf_no_text(), "application/pdf") is None


def test_extract_pdf_garbage_bytes_returns_none():
    assert extract_text(b"not a pdf at all", "application/pdf") is None


def test_extract_text_html_mime_decodes_utf8():
    assert extract_text(b"<html>hi</html>", "text/html") == "<html>hi</html>"


def test_extract_text_plain_mime_decodes_utf8():
    assert extract_text(b"plain bill text", "text/plain") == "plain bill text"


def test_extract_empty_mime_non_pdf_uses_utf8():
    assert extract_text(b"some legislative text", "") == "some legislative text"


def test_extract_text_invalid_utf8_returns_none():
    assert extract_text(b"\xff\xfe\x00 bad", "text/plain") is None


def test_extract_unknown_mime_returns_none():
    assert extract_text(b"PK\x03\x04zipdata", "application/zip") is None
