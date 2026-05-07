import pytest
from app.services.minhash import compute_minhash, jaccard_estimate, NUM_PERM, LSH_THRESHOLD

def test_compute_minhash_returns_128_bands():
    m = compute_minhash("The commission shall establish fees not to exceed.")
    assert len(m.hashvalues) == NUM_PERM

def test_identical_texts_have_similarity_one():
    text = "The commission shall establish fees."
    m1 = compute_minhash(text)
    m2 = compute_minhash(text)
    assert jaccard_estimate(m1, m2) == pytest.approx(1.0)

def test_unrelated_texts_have_low_similarity():
    m1 = compute_minhash("The quick brown fox jumps over the lazy dog.")
    m2 = compute_minhash("Quantum entanglement is a physical phenomenon.")
    assert jaccard_estimate(m1, m2) < 0.3

def test_similar_texts_exceed_threshold():
    base = "The commission shall establish fees not to exceed one hundred dollars per application."
    similar = "The commission shall establish fees not to exceed one hundred dollars per application submitted."
    m1 = compute_minhash(base)
    m2 = compute_minhash(similar)
    assert jaccard_estimate(m1, m2) >= LSH_THRESHOLD

def test_signature_serializable_as_list():
    m = compute_minhash("Any bill text here.")
    sig = m.hashvalues.tolist()
    assert isinstance(sig, list)
    assert all(isinstance(v, int) for v in sig)
