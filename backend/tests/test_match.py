# pylint: disable=line-too-long
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.minhash import compute_minhash

async def test_match_writes_similarity_match_row():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(corpus_bill_id, "TX", "HB-1", corpus_m)

    await _find_matches_for_bill(mock_session, co_bill_id, co_m, index)

    mock_session.add.assert_called()

async def test_no_match_writes_score_of_100():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex

    co_m = compute_minhash("Completely unique Colorado bill text with no parallels anywhere.")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_matches_for_bill(mock_session, uuid4(), co_m, CorpusIndex())

    added = [call.args[0] for call in mock_session.add.call_args_list]
    from app.models.ist_score import ISTScore
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_below_threshold_corpus_produces_no_match():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch
    from app.models.ist_score import ISTScore

    co_m = compute_minhash("The quick brown fox jumps over the lazy dog in Colorado.")
    corpus_m = compute_minhash("Quantum entanglement is a physical phenomenon at subatomic scales.")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(a, SimilarityMatch) for a in added)
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False

async def test_identical_match_sets_copycat_alert():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.ist_score import ISTScore

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("0.00")
    assert scores[0].copycat_alert is True

async def test_corpus_index_filters_dissimilar_candidates():
    """LSH bucketing must return only candidates likely above the 70% Jaccard
    cutoff. The matching_text twin should be retrieved; the 20 unrelated
    quantum-text bills should be filtered out by LSH bands, never reaching
    the Jaccard-refinement stage."""
    from worker.tasks.match import CorpusIndex

    co_text = "The commission shall establish a fee not to exceed one hundred dollars."
    matching_text = "The commission shall establish a fee not to exceed one hundred dollars."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    index = CorpusIndex()
    matching_id = uuid4()
    index.add(matching_id, "TX", "HB-1", compute_minhash(matching_text))
    for _ in range(20):
        index.add(uuid4(), "NM", "SB-X", compute_minhash(unrelated_text + str(_)))

    candidates = index.query(compute_minhash(co_text))
    # Only the identical-text bill should LSH-collide. Any extra candidate
    # would mean LSH is leaking unrelated bills into the refinement stage.
    assert len(candidates) == 1
    assert candidates[0][0] == matching_id


async def test_corpus_index_returns_candidates_above_threshold():
    from worker.tasks.match import CorpusIndex

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    co_m = compute_minhash(identical_text)
    matching_m = compute_minhash(identical_text)
    unrelated_m = compute_minhash(unrelated_text)

    index = CorpusIndex()
    matching_id = uuid4()
    unrelated_id = uuid4()
    index.add(matching_id, "TX", "HB-1", matching_m)
    index.add(unrelated_id, "NM", "SB-9", unrelated_m)

    candidates = index.query(co_m)
    candidate_ids = {c[0] for c in candidates}
    assert matching_id in candidate_ids
    assert unrelated_id not in candidate_ids


async def test_corpus_index_recalls_near_threshold_match():
    """LSH must return candidates at Jaccard ~0.75, not only identical texts.

    Guards against the recall regression caused by default LSH weights
    (b=14,r=9 → ~44% recall at s=0.70). With weights=(0.1,0.9) → b=20,r=6 →
    ~92% recall at s=0.70."""
    from worker.tasks.match import CorpusIndex
    from app.services.minhash import jaccard_estimate

    # Two texts sharing most of their 5-grams (high but not identical Jaccard).
    # Jaccard ~0.71 — sits squarely in the zone where default weights (b=14,r=9)
    # give 0% recall in practice; biased weights (b=20,r=6) give ~100% recall.
    base = "no person shall operate a vehicle without a valid license issued by the department of motor vehicles"
    variant = "no person shall operate a motor vehicle without a valid license issued by the state department"

    co_m = compute_minhash(base)
    corpus_m = compute_minhash(variant)

    # Verify fixture Jaccard is in the target near-threshold range
    sim = jaccard_estimate(co_m, corpus_m)
    assert 0.65 <= sim <= 0.95, f"test fixture Jaccard out of range: {sim}"

    index = CorpusIndex()
    near_id = uuid4()
    index.add(near_id, "TX", "HB-1", corpus_m)

    candidates = index.query(co_m)
    assert near_id in {c[0] for c in candidates}, (
        f"LSH dropped a Jaccard={sim:.2f} match — recall regression"
    )


async def test_corpus_index_drops_duplicate_bill_id():
    """MinHashLSH.insert raises ValueError on duplicate keys. The match phase
    must not crash when the corpus query returns duplicate signature rows
    for one bill (e.g. ingest produced two MinHashSignature rows during a
    re-run). The DISTINCT ON in match_co_bills handles this at the query
    layer; the CorpusIndex.add defensive guard is the last-line safety net."""
    from worker.tasks.match import CorpusIndex

    text = "The commission shall establish fees not to exceed one hundred dollars."
    m = compute_minhash(text)

    index = CorpusIndex()
    bill_id = uuid4()
    index.add(bill_id, "TX", "HB-1", m)
    # Second add with the same bill_id must NOT raise — must drop silently
    index.add(bill_id, "TX", "HB-1", m)

    assert len(index) == 1


async def test_precision_gate_drops_lsh_candidate_below_70_percent_jaccard():
    """LSH false-positive: a candidate gets returned by LSH bucketing but
    the actual Jaccard is below 70%. _find_matches_for_bill must apply the
    precision gate and not write a SimilarityMatch row."""
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch
    from app.models.ist_score import ISTScore
    from app.services.minhash import jaccard_estimate

    # Two texts engineered to sit at Jaccard 0.55-0.68 — high enough for LSH
    # bands to plausibly co-bucket them, low enough that the 70% post-filter
    # in _find_matches_for_bill must reject them.
    base = "the department shall issue a permit for the operation of a commercial vehicle within the state"
    variant = "the department may grant authorization for transport of goods inside this state"

    co_m = compute_minhash(base)
    corpus_m = compute_minhash(variant)
    sim = jaccard_estimate(co_m, corpus_m)
    # Anchor the fixture: must be below the 70% cutoff so the precision
    # gate is what's being exercised here, not LSH.
    assert sim < 0.70, f"fixture leaked above precision gate: {sim}"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", corpus_m)
    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    # Either LSH filtered the candidate out (no SimilarityMatch and no
    # candidates reached the gate) or LSH returned it and the 70% gate
    # rejected it. Both end states produce the same observable result:
    # no SimilarityMatch row, ISTScore = 100.00.
    assert not any(isinstance(a, SimilarityMatch) for a in added)
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False


async def test_match_type_is_co_internal_when_corpus_state_is_co():
    # NOTE: hand-builds a "CO" corpus entry, which the production corpus query
    # (Bill.is_corpus_only.is_(True) in match_co_bills) can never produce — CO
    # bills are is_corpus_only=False. This exercises the ternary branch in
    # isolation; NOT end-to-end coverage of a reachable production path.
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    # Synthetic CO corpus entry — see NOTE above; unreachable in production.
    index = CorpusIndex()
    index.add(corpus_bill_id, "CO", "HB-1", corpus_m)

    await _find_matches_for_bill(mock_session, co_bill_id, co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    matches = [a for a in added if isinstance(a, SimilarityMatch)]
    assert len(matches) == 1
    assert matches[0].match_type == "co_internal"


async def test_match_type_is_cross_state_when_corpus_state_is_not_co():
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    # Use "TX" state to ensure cross-state match calculation
    index = CorpusIndex()
    index.add(corpus_bill_id, "TX", "HB-1", corpus_m)

    await _find_matches_for_bill(mock_session, co_bill_id, co_m, index)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    matches = [a for a in added if isinstance(a, SimilarityMatch)]
    assert len(matches) == 1
    assert matches[0].match_type == "cross_state"


async def test_normalize_bill_number_strips_and_uppercases():
    from worker.tasks.match import _normalize_bill_number
    assert _normalize_bill_number("hb 1234") == "HB1234"
    assert _normalize_bill_number(" SB24-005 ") == "SB24-005"
    assert _normalize_bill_number("Hb1234") == "HB1234"


async def test_co_internal_writes_match_for_distinct_numbers():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_index.add(b, "CO", "SB-2", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    matches = [x for x in added if isinstance(x, SimilarityMatch)]
    assert len(matches) == 1
    assert matches[0].match_type == "co_internal"
    assert matches[0].matched_bill_id == b
    assert matches[0].matched_state == "CO"
    assert matches[0].matched_bill_title == "Bill B"
    assert matches[0].snippet_status == "pending"


async def test_co_internal_pass_does_not_write_ist_score():
    """HONESTY GUARD: the CO-internal pass must never create an ISTScore, so
    copycat_alert stays cross-state-only. If this fails, the feature is wrong."""
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.ist_score import ISTScore

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_index.add(b, "CO", "SB-2", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, ISTScore) for x in added)


async def test_co_internal_self_guard_skips_same_bill():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a = uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)


async def test_co_internal_companion_noise_guard_skips_identical_bill_number():
    """Same normalized bill_number = version/session duplicate of one bill, not a
    distinct related bill. Drop it (the 1 noise pair from the de-risk probe)."""
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB24-1234", compute_minhash(text))
    co_index.add(b, "CO", " hb24-1234 ", compute_minhash(text))  # same number, case/whitespace variant
    co_meta = {a: ("HB24-1234", "Bill v1"), b: (" hb24-1234 ", "Bill v2")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)


async def test_co_internal_below_threshold_writes_no_match():
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex
    from app.models.similarity_match import SimilarityMatch

    base = "no person shall operate a vehicle without a valid license issued by the department of motor vehicles"
    far = "quantum entanglement is a physical phenomenon observed at subatomic scales in laboratory settings"
    a, b = uuid4(), uuid4()

    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(base))
    co_index.add(b, "CO", "SB-2", compute_minhash(far))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(base), co_index, co_meta)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    assert not any(isinstance(x, SimilarityMatch) for x in added)


async def test_find_matches_for_bill_does_not_commit():
    """Perf guard: a per-bill commit cost 6997 serial INSERT+COMMIT round trips
    to EU-West Neon (~0.53s each = 3693s in prod). Commit ownership belongs to
    match_co_bills, which batches a single commit per run. The per-bill helper
    must NOT commit."""
    from worker.tasks.match import _find_matches_for_bill, CorpusIndex

    co_m = compute_minhash("Unique Colorado bill text with no parallels anywhere.")
    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", compute_minhash("Quantum entanglement at subatomic scales."))

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_matches_for_bill(mock_session, uuid4(), co_m, index)

    mock_session.commit.assert_not_called()


async def test_find_co_internal_matches_does_not_commit():
    """Mirror of the cross-state guard: the CO-internal helper must not commit
    either; match_co_bills owns the single batched commit."""
    from worker.tasks.match import _find_co_internal_matches, CorpusIndex

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    a, b = uuid4(), uuid4()
    co_index = CorpusIndex()
    co_index.add(a, "CO", "HB-1", compute_minhash(text))
    co_index.add(b, "CO", "SB-2", compute_minhash(text))
    co_meta = {a: ("HB-1", "Bill A"), b: ("SB-2", "Bill B")}

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_co_internal_matches(mock_session, a, compute_minhash(text), co_index, co_meta)

    mock_session.commit.assert_not_called()


async def test_match_co_bills_commits_once_not_per_bill():
    """Root-cause regression guard. The old code committed once per CO bill
    inside the pass loops (6997 serial round trips). match_co_bills must
    accumulate all writes and commit exactly once for the whole run, regardless
    of bill count. Also guards against dropping the commit entirely (no persist).
    """
    import worker.tasks.match as match_mod
    from worker.tasks.match import match_co_bills

    text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    sig_vals = [int(x) for x in compute_minhash(text).hashvalues]

    def make_sig():
        return MagicMock(signature=list(sig_vals))

    bill_a = MagicMock(id=uuid4(), state="CO", bill_number="HB-1", title="Bill A")
    bill_b = MagicMock(id=uuid4(), state="CO", bill_number="SB-2", title="Bill B")
    co_rows_result = MagicMock()
    co_rows_result.all = MagicMock(return_value=[(make_sig(), bill_a), (make_sig(), bill_b)])

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    # execute() call order in match_co_bills: delete SimilarityMatch, delete
    # ISTScore, select(cross-state corpus) [iterated], select(CO rows) [.all()].
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(),     # delete SimilarityMatch
        MagicMock(),     # delete ISTScore
        [],              # empty cross-state corpus (iterated -> no corpus bills)
        co_rows_result,  # 2 CO bills (.all())
    ])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(match_mod, "async_session", return_value=cm):
        await match_co_bills()

    # 2 CO bills. Old per-bill code: 1 (delete) + 2 (pass 1) + 2 (pass 2) = 5.
    # Batched code: exactly 1 commit for the whole run, independent of count.
    assert mock_session.commit.await_count == 1, (
        f"committed {mock_session.commit.await_count}x — per-bill commit, not batched"
    )
