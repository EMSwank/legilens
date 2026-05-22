import logging
import re

_KEY_RE = re.compile(r"(key=)[^&\s'\"]+")


class RedactAPIKeyFilter(logging.Filter):
    """Redacts `key=<value>` query params from log records so the LegiScan API key
    never reaches stdout (httpx logs full request URLs at INFO level)."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _KEY_RE.sub(r"\1***", message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True
