"""Pure coverage-tracker helpers — no DB access, fully unit-testable.

The counting logic lives here (not in SQL) because the test suite has no real
DB engine and the models are Postgres-locked, so the GROUP BY could not be
exercised in CI. The worker feeds aggregate_coverage() one boolean-per-bill row
(state, has_doc, has_sig) produced by an EXISTS query — no join, so duplicate
signature rows cannot fan-out double-count.

SCOPE must stay in sync with backend/worker/queue.py _STATE_PRIORITY tiers 0+1
(CO + top-5). If the fetch scope changes, change both.
"""
import json
from collections.abc import Iterable

# CO (tier 0) + the five comparison states (tier 1 in queue._STATE_PRIORITY).
SCOPE: tuple[str, ...] = ("CO", "CA", "NY", "IL", "TX", "FL")


def aggregate_coverage(rows: Iterable[tuple[str, bool, bool]]) -> dict[str, dict[str, int]]:
    """Fold (state, has_doc, has_sig) rows into per-state {fetchable, with_sig}.

    with_sig is AND-gated on has_doc so a signature attached to a bill with no
    text_doc_id never inflates the matchable count — this keeps with_sig <=
    fetchable, hence the matchable ratio <= 1.0.
    """
    acc: dict[str, dict[str, int]] = {}
    for state, has_doc, has_sig in rows:
        bucket = acc.setdefault(state, {"fetchable": 0, "with_sig": 0})
        if has_doc:
            bucket["fetchable"] += 1
            if has_sig:
                bucket["with_sig"] += 1
    return acc


def build_snapshot_payload(rows: Iterable[tuple[str, bool, bool]]) -> str:
    """Aggregate rows and serialize to the stored snapshot JSON (states sorted)."""
    agg = aggregate_coverage(rows)
    states = [
        {"state": s, "fetchable": c["fetchable"], "with_sig": c["with_sig"]}
        for s, c in sorted(agg.items())
    ]
    return json.dumps({"states": states})


def derive_state_status(fetchable: int, with_sig: int) -> str:
    """complete (>=95% matchable) / in_progress / not_started (no signatures)."""
    if with_sig == 0:
        return "not_started"
    if fetchable > 0 and with_sig / fetchable >= 0.95:
        return "complete"
    return "in_progress"


def scoped_matchable_pct(per_state: dict[str, dict[str, int]]) -> float | None:
    """Headline metric: in-scope with_sig / in-scope fetchable, as a 0-100 float.

    Returns None when no in-scope bill is fetchable yet (distinct from 0.0).
    """
    numerator = sum(v["with_sig"] for s, v in per_state.items() if s in SCOPE)
    denominator = sum(v["fetchable"] for s, v in per_state.items() if s in SCOPE)
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)
