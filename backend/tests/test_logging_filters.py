import logging

from app.logging_filters import RedactAPIKeyFilter


def _record(msg, args=None):
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=None,
    )


def test_redacts_key_in_message():
    rec = _record("getDatasetList returned non-OK status: /?key=64c1f9cd497d&op=x")
    RedactAPIKeyFilter().filter(rec)
    assert "64c1f9cd497d" not in rec.getMessage()
    assert "key=***" in rec.getMessage()


def test_redacts_key_in_args():
    rec = _record(
        'HTTP Request: %s "%s"',
        ("https://api.legiscan.com/?key=64c1f9cd497d&op=getDatasetList", "200 OK"),
    )
    RedactAPIKeyFilter().filter(rec)
    assert "64c1f9cd497d" not in rec.getMessage()
    assert "key=***" in rec.getMessage()


class _FakeURL:
    """Mimics httpx.URL — logged by httpx as a positional arg, not a str."""

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return self._value


def test_redacts_key_in_non_str_arg():
    rec = _record(
        'HTTP Request: %s %s',
        ("GET", _FakeURL("https://api.legiscan.com/?key=64c1f9cd497d&op=getDatasetList")),
    )
    RedactAPIKeyFilter().filter(rec)
    assert "64c1f9cd497d" not in rec.getMessage()
    assert "key=***" in rec.getMessage()


def test_leaves_unrelated_message_untouched():
    rec = _record("Pipeline complete.")
    RedactAPIKeyFilter().filter(rec)
    assert rec.getMessage() == "Pipeline complete."
