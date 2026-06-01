"""Unit tests for fetch_bill_texts worker.

Uses AsyncMock — no real DB required. Tests verify call semantics and
outcome routing. Integration-level state assertions (actual DB rows,
quota stored values) require TEST_DATABASE_URL.
"""
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.bill import Bill
from worker.tasks.fetch_bill_texts import fetch_bill_texts


def _make_bill(legiscan_id=100, doc_id=999, attempts=0, status="queued", state="CO"):
    b = MagicMock(spec=Bill)
    b.id = uuid4()
    b.legiscan_id = legiscan_id
    b.state = state
    b.text_doc_id = doc_id
    b.text_fetch_status = status
    b.text_fetch_attempts = attempts
    b.full_text = None
    return b


def _make_db_stack(bills_in_queue):
    """Returns (async_session_cm, session_mock) with queue + per-bill session behavior."""
    session_mock = AsyncMock()
    session_mock.commit = AsyncMock()

    # First session: reset_quota_if_month_rolled + get_quota_used + next_queued_bills
    month_result = MagicMock()
    # Must equal the CURRENT UTC month so reset_quota_if_month_rolled takes the
    # no-reset path (else it issues 2 extra execute() calls and exhausts the
    # side_effect list below). Hardcoding a literal month silently breaks every
    # test in this file the moment the real month rolls over.
    from datetime import datetime, timezone
    month_result.scalar.return_value = datetime.now(tz=timezone.utc).strftime("%Y-%m")
    quota_result = MagicMock()
    quota_result.scalar.return_value = "0"
    queue_result = MagicMock()
    queue_result.scalars.return_value.all.return_value = bills_in_queue

    session_mock.execute = AsyncMock(
        side_effect=[month_result, quota_result, queue_result]
    )
    session_mock.get = AsyncMock(
        side_effect=lambda model, pk: bills_in_queue[0] if bills_in_queue else None
    )

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session_mock


async def test_success_path_calls_legiscan_and_commits():
    bill = _make_bill()
    session_cm, session_mock = _make_db_stack([bill])

    # Per-bill transaction session
    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    from app.services.legiscan import BillDoc

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(
        return_value=BillDoc(raw=b"Be it enacted...", mime="text/plain")
    )
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 1
    fake_legiscan.get_bill_doc.assert_awaited_once_with(999)
    per_bill_session.commit.assert_awaited()


async def test_quota_guard_aborts_when_at_limit():
    session_mock = AsyncMock()
    session_mock.commit = AsyncMock()

    month_result = MagicMock()
    # Current UTC month → no-reset path (see _make_db_stack note); a literal month
    # breaks this test when the real month rolls over.
    from datetime import datetime, timezone
    month_result.scalar.return_value = datetime.now(tz=timezone.utc).strftime("%Y-%m")
    quota_result = MagicMock()
    quota_result.scalar.return_value = "27000"  # AT hard limit
    session_mock.execute = AsyncMock(side_effect=[month_result, quota_result])

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock()

    with patch("worker.tasks.fetch_bill_texts.async_session", return_value=cm), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 0
    fake_legiscan.get_bill_doc.assert_not_awaited()


async def test_empty_doc_is_permanent_failure():
    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 1  # terminal outcome
    assert bill.text_fetch_status == "failed"
    assert bill.text_fetch_attempts == 1
    per_bill_session.commit.assert_awaited()


async def test_third_failure_escalates_to_skipped():
    bill = _make_bill(attempts=2)  # will be 3 after this call
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        await fetch_bill_texts(batch_size=10)

    assert bill.text_fetch_status == "skipped"
    assert bill.text_fetch_attempts == 3


async def test_transient_5xx_requeues_does_not_set_failed():
    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    err_response = MagicMock()
    err_response.status_code = 503
    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=err_response)
    )
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 0  # transient = not terminal
    assert bill.text_fetch_status == "queued"
    assert bill.text_fetch_attempts == 1


async def test_connect_timeout_is_transient_not_uncaught():
    """ConnectTimeout/WriteTimeout/PoolTimeout are httpx.TimeoutException, NOT
    subclasses of httpx.ConnectError. With connect/write/pool timeouts configured
    on the client they can fire in prod; if uncaught they propagate out of the
    `for bill in bills` loop and abort the rest of the nightly batch. They must
    be classified transient (requeue, no quota charge), like ReadTimeout."""
    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(
        side_effect=httpx.ConnectTimeout("connect timed out", request=MagicMock())
    )
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 0  # transient = not terminal, batch survives
    assert bill.text_fetch_status == "queued"
    assert bill.text_fetch_attempts == 1


async def test_pdf_garbage_is_permanent_failure(caplog):
    import logging
    from app.services.legiscan import BillDoc

    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    # application/pdf mime but the bytes are not a parseable PDF -> extract_text None
    fake_legiscan.get_bill_doc = AsyncMock(
        return_value=BillDoc(raw=b"not a pdf", mime="application/pdf")
    )
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with caplog.at_level(logging.WARNING, logger="worker.tasks.fetch_bill_texts"), \
         patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 1  # terminal outcome
    assert bill.text_fetch_status == "failed"
    assert bill.text_fetch_attempts == 1
    # The mime must appear in the warning — this was the original blind spot
    assert "application/pdf" in caplog.text


async def test_none_doc_logs_none_mime_on_permanent_failure(caplog):
    """When get_bill_doc returns None the warning log shows mime=<none>."""
    import logging

    bill = _make_bill(attempts=0)
    session_cm, _ = _make_db_stack([bill])

    per_bill_session = AsyncMock()
    per_bill_session.commit = AsyncMock()
    per_bill_session.get = AsyncMock(return_value=bill)
    per_bill_session.execute = AsyncMock(return_value=MagicMock())
    per_bill_cm = AsyncMock()
    per_bill_cm.__aenter__ = AsyncMock(return_value=per_bill_session)
    per_bill_cm.__aexit__ = AsyncMock(return_value=False)

    fake_legiscan = AsyncMock()
    fake_legiscan.get_bill_doc = AsyncMock(return_value=None)
    fake_legiscan.close = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return session_cm if call_count == 1 else per_bill_cm

    with caplog.at_level(logging.WARNING, logger="worker.tasks.fetch_bill_texts"), \
         patch("worker.tasks.fetch_bill_texts.async_session", side_effect=_session_factory), \
         patch("worker.tasks.fetch_bill_texts.LegiScanClient", return_value=fake_legiscan):
        result = await fetch_bill_texts(batch_size=10)

    assert result == 1
    assert "<none>" in caplog.text
