import json
from app.services.coverage import (
    SCOPE,
    aggregate_coverage,
    build_snapshot_payload,
    derive_state_status,
    scoped_matchable_pct,
)


def test_scope_is_co_plus_top5():
    assert set(SCOPE) == {"CO", "CA", "NY", "IL", "TX", "FL"}


def test_aggregate_counts_fetchable_and_with_sig():
    rows = [("CO", True, True), ("CO", True, False), ("CO", True, True)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 3, "with_sig": 2}}


def test_aggregate_excludes_null_doc_bill_from_both():
    # Hazard #2: a signature with text_doc_id IS NULL must count toward neither.
    rows = [("CO", False, True)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 0, "with_sig": 0}}


def test_aggregate_doc_without_sig_counts_fetchable_only():
    rows = [("CO", True, False)]
    assert aggregate_coverage(rows) == {"CO": {"fetchable": 1, "with_sig": 0}}


def test_aggregate_with_sig_never_exceeds_fetchable():
    rows = [("CO", True, True), ("CO", False, True), ("CO", True, False)]
    agg = aggregate_coverage(rows)["CO"]
    assert agg["with_sig"] <= agg["fetchable"]


def test_aggregate_groups_by_state():
    rows = [("CO", True, True), ("TX", True, False)]
    assert aggregate_coverage(rows) == {
        "CO": {"fetchable": 1, "with_sig": 1},
        "TX": {"fetchable": 1, "with_sig": 0},
    }


def test_derive_status_not_started_when_no_sig():
    assert derive_state_status(120, 0) == "not_started"


def test_derive_status_complete_at_95_percent():
    assert derive_state_status(100, 95) == "complete"


def test_derive_status_in_progress_below_95():
    assert derive_state_status(100, 94) == "in_progress"


def test_scoped_pct_counts_only_scope_states():
    per_state = {
        "CO": {"fetchable": 100, "with_sig": 80},
        "TX": {"fetchable": 100, "with_sig": 20},  # in scope
        "WY": {"fetchable": 100, "with_sig": 100},  # tier-2, excluded
    }
    # (80 + 20) / (100 + 100) = 50.0 ; WY excluded from numerator AND denominator
    assert scoped_matchable_pct(per_state) == 50.0


def test_scoped_pct_none_when_no_inscope_fetchable():
    assert scoped_matchable_pct({"WY": {"fetchable": 100, "with_sig": 100}}) is None
    assert scoped_matchable_pct({}) is None


def test_build_snapshot_payload_is_sorted_json_states():
    rows = [("TX", True, False), ("CO", True, True)]
    payload = json.loads(build_snapshot_payload(rows))
    assert payload == {
        "states": [
            {"state": "CO", "fetchable": 1, "with_sig": 1},
            {"state": "TX", "fetchable": 1, "with_sig": 0},
        ]
    }
