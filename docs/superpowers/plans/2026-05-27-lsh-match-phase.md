# LSH-Backed Match Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the O(N×M) linear scan in `match_co_bills` with an LSH-backed candidate lookup so the match phase finishes in seconds instead of days when pass=2 ingest completes.

**Architecture:** Introduce a `CorpusIndex` wrapper around `MinHashLSH` plus a metadata dict. Build it once at the start of `match_co_bills` by streaming corpus signatures into the index. For each CO bill, call `index.query(co_m)` to get candidate matches (sublinear via LSH bands), then refine via exact Jaccard. Memory profile unchanged from today (same in-memory corpus footprint), but per-CO-bill comparisons drop from ~1,000,000 to ~10s of candidates. The 70% Jaccard match threshold and `copycat_alert` < 30 cutoff stay intact — only the lookup is faster.

**Tech Stack:** Python async, SQLAlchemy 2.0 async, `datasketch` library (already imported in `app/services/minhash.py`), pytest-asyncio with `unittest.mock.patch` for worker tests.

---

## Background

Current `backend/worker/tasks/match.py`:

```python
corpus_entries = [(bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))
                  for sig, bill in corpus_result]

for sig, co_bill in co_result:
    co_m = minhash_from_signature(sig.signature)
    await _find_matches_for_bill(session, co_bill.id, co_m, corpus_entries)

async def _find_matches_for_bill(session, co_bill_id, co_m, corpus_entries):
    for corpus_bill_id, corpus_state, _, corpus_m in corpus_entries:
        sim = Decimal(str(round(jaccard_estimate(co_m, corpus_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue
        ...
```

`build_lsh()` exists in `backend/app/services/minhash.py:25` but is unused. LSH bands threshold already matches our match threshold (0.7).

---

## File Structure

- `backend/worker/tasks/match.py` — add `CorpusIndex` class, refactor `match_co_bills` + `_find_matches_for_bill`
- `backend/tests/test_match.py` — update existing tests for new signature, add LSH-specific test
- `backend/app/services/minhash.py` — no changes (verify `build_lsh()` still exports MinHashLSH)
- `CLAUDE.md` — update "Design decisions" with LSH note

---

## Task 1: Add CorpusIndex helper class

**Files:**
- Modify: `backend/worker/tasks/match.py` (add class above `match_co_bills`)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_match.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/`: `.venv/bin/python -m pytest tests/test_match.py::test_corpus_index_returns_candidates_above_threshold -v`
Expected: FAIL with `ImportError: cannot import name 'CorpusIndex' from 'worker.tasks.match'`

- [ ] **Step 3: Write minimal implementation**

In `backend/worker/tasks/match.py`, add imports + class at top (after existing imports, before `match_co_bills`):

```python
from datasketch import MinHash
from app.services.minhash import minhash_from_signature, jaccard_estimate, build_lsh


class CorpusIndex:
    """LSH-backed lookup over corpus MinHash signatures.

    LSH bucketing makes candidate retrieval sublinear in corpus size. The
    bands threshold (0.7) is set in build_lsh() to match our 70% Jaccard
    match threshold. False negatives at the boundary are possible but rare
    with NUM_PERM=128.
    """

    def __init__(self):
        self._lsh = build_lsh()
        self._lookup: dict[str, tuple] = {}

    def add(self, bill_id, state: str, bill_number: str, m: MinHash) -> None:
        key = str(bill_id)
        self._lsh.insert(key, m)
        self._lookup[key] = (bill_id, state, bill_number, m)

    def query(self, m: MinHash) -> list[tuple]:
        return [self._lookup[k] for k in self._lsh.query(m) if k in self._lookup]

    def __len__(self) -> int:
        return len(self._lookup)
```

Keep the existing `from app.services.minhash import minhash_from_signature, jaccard_estimate` import — delete if duplicated.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_match.py::test_corpus_index_returns_candidates_above_threshold -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/worker/tasks/match.py backend/tests/test_match.py
git commit -m "feat(worker): add CorpusIndex LSH wrapper for match phase

Wraps datasketch MinHashLSH with a metadata lookup. Sublinear candidate
retrieval — replaces the O(N) linear scan currently in match_co_bills."
```

---

## Task 2: Refactor `_find_matches_for_bill` to accept CorpusIndex

**Files:**
- Modify: `backend/worker/tasks/match.py:41-74`
- Modify: `backend/tests/test_match.py:8-87` (4 existing tests use old signature)

- [ ] **Step 1: Update the first existing test to use CorpusIndex**

Replace `test_match_writes_similarity_match_row` body:

```python
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
```

- [ ] **Step 2: Update the other three existing tests the same way**

Replace each of `test_no_match_writes_score_of_100`, `test_below_threshold_corpus_produces_no_match`, `test_identical_match_sets_copycat_alert` so they build a `CorpusIndex` instead of `corpus_entries = [...]`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_match.py -v`
Expected: 4 tests FAIL because `_find_matches_for_bill` still expects `corpus_entries: list`, not `CorpusIndex`.

- [ ] **Step 4: Refactor `_find_matches_for_bill` to accept CorpusIndex**

Replace `_find_matches_for_bill` body in `backend/worker/tasks/match.py`:

```python
async def _find_matches_for_bill(session, co_bill_id: UUID, co_m, corpus: "CorpusIndex"):
    if len(corpus) == 0:
        score = ISTScore(
            bill_id=co_bill_id,
            source_authenticity_score=Decimal("100.00"),
            copycat_alert=False,
        )
        session.add(score)
        await session.commit()
        return

    candidates = corpus.query(co_m)

    max_similarity = Decimal("0.00")
    for corpus_bill_id, corpus_state, _, corpus_m in candidates:
        sim = Decimal(str(round(jaccard_estimate(co_m, corpus_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue
        match = SimilarityMatch(
            bill_id=co_bill_id,
            matched_bill_id=corpus_bill_id,
            matched_state=corpus_state,
            similarity_score=sim,
            snippet_status="pending",
        )
        session.add(match)
        max_similarity = max(max_similarity, sim)

    authenticity = Decimal("100.00") - max_similarity
    score = ISTScore(
        bill_id=co_bill_id,
        source_authenticity_score=authenticity,
        copycat_alert=authenticity < Decimal("30.00"),
    )
    session.add(score)
    await session.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_match.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/worker/tasks/match.py backend/tests/test_match.py
git commit -m "refactor(worker): _find_matches_for_bill takes CorpusIndex

Switches the per-CO-bill match path from iterating a corpus_entries list
to querying an LSH-backed index for candidates. Existing tests updated
to build CorpusIndex instead of raw tuples — same expected behavior."
```

---

## Task 3: Refactor `match_co_bills` to build and use CorpusIndex

**Files:**
- Modify: `backend/worker/tasks/match.py:11-39`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_match.py`:

```python
async def test_match_co_bills_skips_unrelated_corpus_via_lsh():
    """When LSH filters out unrelated bills, _find_matches_for_bill should
    never be called with them as candidates — verified by checking the
    candidate count exposed by CorpusIndex."""
    from worker.tasks.match import CorpusIndex

    co_text = "The commission shall establish a fee not to exceed one hundred dollars."
    matching_text = "The commission shall establish a fee not to exceed one hundred dollars."
    unrelated_text = "Quantum entanglement is a physical phenomenon at subatomic scales."

    index = CorpusIndex()
    index.add(uuid4(), "TX", "HB-1", compute_minhash(matching_text))
    for _ in range(20):
        index.add(uuid4(), "NM", "SB-X", compute_minhash(unrelated_text + str(_)))

    candidates = index.query(compute_minhash(co_text))
    # LSH should return only the truly similar bill, not all 21 corpus entries
    assert 1 <= len(candidates) < 5
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_match.py::test_match_co_bills_skips_unrelated_corpus_via_lsh -v`
Expected: PASS (this validates the LSH filtering invariant; we use it next).

- [ ] **Step 3: Refactor `match_co_bills` to build CorpusIndex**

Replace the body of `match_co_bills` in `backend/worker/tasks/match.py`:

```python
async def match_co_bills():
    async with async_session() as session:
        # Idempotency: nuke prior match output for CO bills so re-runs (nightly
        # or two-pass bootstrap) don't accumulate duplicate ISTScore /
        # SimilarityMatch rows. Bills/list and bills/detail use scalar_one_or_none
        # on ISTScore and would 500 on duplicates.
        co_bill_ids = select(Bill.id).where(Bill.is_corpus_only.is_(False))
        await session.execute(delete(SimilarityMatch).where(SimilarityMatch.bill_id.in_(co_bill_ids)))
        await session.execute(delete(ISTScore).where(ISTScore.bill_id.in_(co_bill_ids)))
        await session.commit()

        # Build LSH-backed corpus index. With NUM_PERM=128 and bands threshold
        # 0.7, candidate retrieval is sublinear in corpus size — the prior
        # implementation did a full linear scan per CO bill (O(N*M) = ~12B
        # comparisons at current scale, days of wall-clock).
        corpus_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(True))
        )
        index = CorpusIndex()
        for sig, bill in corpus_result:
            index.add(bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))

        co_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
        )
        for sig, co_bill in co_result:
            co_m = minhash_from_signature(sig.signature)
            await _find_matches_for_bill(session, co_bill.id, co_m, index)
```

- [ ] **Step 4: Run full match test suite**

Run: `.venv/bin/python -m pytest tests/test_match.py -v`
Expected: all tests PASS (6 total now).

- [ ] **Step 5: Run full backend suite**

Run: `.venv/bin/python -m pytest -q`
Expected: 103+ tests PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/worker/tasks/match.py backend/tests/test_match.py
git commit -m "perf(worker): match_co_bills builds LSH index from corpus

Sublinear candidate retrieval replaces the O(N*M) linear scan over every
corpus signature. Current corpus = ~750k bills * 12k CO bills = ~9B
Jaccard estimates today; with LSH bands at threshold 0.7 each CO bill
checks only the small candidate set from its LSH buckets. Wall-clock
drops from days to seconds at this scale, and the design now scales to
national / historical corpus sizes."
```

---

## Task 4: Add timing log so we can see match phase duration in prod

**Files:**
- Modify: `backend/worker/tasks/match.py` (add logger import + timing)

- [ ] **Step 1: Add logging to match.py**

At top of `backend/worker/tasks/match.py`:

```python
import logging
import time

logger = logging.getLogger(__name__)
```

Wrap the LSH build and CO match loop with timing:

```python
        t_index_start = time.monotonic()
        index = CorpusIndex()
        for sig, bill in corpus_result:
            index.add(bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))
        logger.info(
            "match: built LSH corpus index with %d bills in %.2fs",
            len(index), time.monotonic() - t_index_start,
        )

        t_match_start = time.monotonic()
        co_count = 0
        co_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
        )
        for sig, co_bill in co_result:
            co_m = minhash_from_signature(sig.signature)
            await _find_matches_for_bill(session, co_bill.id, co_m, index)
            co_count += 1
        logger.info(
            "match: scored %d CO bills against corpus in %.2fs",
            co_count, time.monotonic() - t_match_start,
        )
```

- [ ] **Step 2: Run full backend suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests PASS, no regression from logging.

- [ ] **Step 3: Commit**

```bash
git add backend/worker/tasks/match.py
git commit -m "obs(worker): log LSH build + CO match phase durations

Surfaces real timing in Railway logs so we stop guessing on perf."
```

---

## Task 5: Update CLAUDE.md with the design decision

**Files:**
- Modify: `CLAUDE.md` — "Design decisions to remember" section

- [ ] **Step 1: Add bullet under backend design decisions**

In `CLAUDE.md` after the existing `match.py` bullet, add:

```markdown
- `match_co_bills` uses `CorpusIndex` (LSH wrapper) for candidate retrieval — never iterate the full corpus per CO bill. The bands threshold in `build_lsh()` (0.7) matches our 70% Jaccard match cutoff; raising one without the other breaks the invariant that LSH candidates are a superset of real matches.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record LSH match invariant"
```

---

## Task 6: Push branch + open PR

**Files:**
- None (git/gh commands only)

- [ ] **Step 1: Create branch from main** (only if not already on a feature branch)

```bash
git checkout -b perf/match-lsh-index
```

- [ ] **Step 2: Push**

```bash
git push -u origin perf/match-lsh-index
```

- [ ] **Step 3: Open PR**

```bash
gh pr create --title "perf(worker): LSH-backed match phase (sublinear candidate retrieval)" --body "$(cat <<'EOF'
## Summary
- Match phase did a full linear scan of the corpus for each CO bill: at current scale that's ~12,430 × ~750,000 = ~9B Jaccard estimates per nightly run, days of wall-clock. The MinHashLSH helper for exactly this lookup already existed in app/services/minhash.py:build_lsh() but was never wired in.
- New CorpusIndex wraps MinHashLSH plus a metadata dict. match_co_bills builds it once from corpus signatures, then queries per-CO-bill — sublinear in N. The 70% Jaccard match cutoff and copycat_alert (< 30 authenticity) thresholds are unchanged; only the lookup path is fast.
- Timing logs added so we can see the real numbers in Railway instead of guessing.

## Why this matters now
- pass=2 bootstrap is ~41% through (~580 datasets remaining at ~3-5 datasets/hr). When it finishes and the pipeline fires match_co_bills, the old linear scan would take days or OOM the worker. This unblocks first-real-data on the live site once ingest catches up — and is the prerequisite for the tier-1 national expansion (without LSH, match doesn't scale past ~CO-sized lookups).

## Test plan
- [x] backend && pytest -q → all pass, including new CorpusIndex tests
- [ ] After merge: observe match phase duration in Railway logs (should be seconds, not hours)
EOF
)"
```

- [ ] **Step 4: Wait for CI + merge**

Use `gh pr checks <num>` to confirm green. Then `gh pr merge <num> --auto --squash --delete-branch`.

---

## Self-Review

### Spec coverage
- ✓ Goal: O(N×M) → sublinear. Task 3 swaps in LSH.
- ✓ Backward compat: same thresholds, same DB writes. Tests verify.
- ✓ Existing tests don't break. Task 2 updates them.
- ✓ Observability. Task 4 adds timing logs.
- ✓ Docs. Task 5 updates CLAUDE.md.
- ✓ Ship to prod. Task 6 PR + merge.

### Placeholder scan
None. Every code block is concrete.

### Type consistency
- `CorpusIndex.add(bill_id, state: str, bill_number: str, m: MinHash)` — same tuple shape returned by `.query()` as the prior `corpus_entries` had: `(bill_id, state, bill_number, MinHash)`. `_find_matches_for_bill` unpacks identically.
- `len(corpus)` works because `CorpusIndex` defines `__len__`.
- `MinHashLSH` imported transitively via `build_lsh()` — no new direct import needed.

### Risks called out
- LSH false negatives at threshold boundary: rare with NUM_PERM=128; acceptable trade.
- Memory: same as today (corpus MinHashes still resident; LSH bands are small additional structure).
- Match output schema: unchanged.
