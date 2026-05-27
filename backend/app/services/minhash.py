import numpy as np
from datasketch import MinHash, MinHashLSH

NUM_PERM = 128       # fixed — changing invalidates all stored signatures
LSH_THRESHOLD = 0.7  # aligns with copycat_alert (score < 30.00)
SHINGLE_SIZE = 5     # character k-shingles

def compute_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    text = text.lower()
    for i in range(len(text) - SHINGLE_SIZE + 1):
        shingle = text[i:i + SHINGLE_SIZE]
        m.update(shingle.encode("utf8"))
    return m

def jaccard_estimate(m1: MinHash, m2: MinHash) -> float:
    return m1.jaccard(m2)

def minhash_from_signature(signature: list[int]) -> MinHash:
    """Reconstruct MinHash from stored BIGINT[] signature."""
    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array(signature, dtype=np.uint64)
    return m

def build_lsh() -> MinHashLSH:
    # weights=(false_positive_weight, false_negative_weight). Biased toward
    # minimizing false negatives so LSH candidates are a superset of real
    # matches above the 70% cutoff. With default (0.5, 0.5) and threshold=0.7,
    # the S-curve inflection sits at ~0.75 and misses ~56% of matches at
    # exactly s=0.70. (0.1, 0.9) shifts band/row selection toward recall:
    # ~92% recall at s=0.70, ~98% at s=0.75, ~100% at s>=0.80. The exact
    # 70% filter in match.py:_find_matches_for_bill is the precision gate.
    return MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM, weights=(0.1, 0.9))
