import logging
import re

_KEY_RE = re.compile(r"(key=)[^&\s'\"]+")


class RedactAPIKeyFilter(logging.Filter):
    """Redacts `key=<value>` query params from log records so the LegiScan API key
    never reaches stdout (httpx logs full request URLs at INFO level)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _KEY_RE.sub(r"\1***", record.msg)
        if record.args:
            record.args = tuple(
                _KEY_RE.sub(r"\1***", a) if isinstance(a, str) else a
                for a in record.args
            )
        return True
