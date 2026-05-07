import difflib
import re

MIN_MATCH_LENGTH = 50

def extract_snippets(co_text: str, source_text: str) -> list[dict]:
    matcher = difflib.SequenceMatcher(None, co_text, source_text, autojunk=False)
    co_sents = _split_sentences(co_text)
    src_sents = _split_sentences(source_text)
    snippets = []

    for a, b, n in matcher.get_matching_blocks():
        if n < MIN_MATCH_LENGTH:
            continue
        co_match = co_text[a:a + n]
        src_match = source_text[b:b + n]
        co_before, co_after = _surrounding_sentence(co_sents, a, a + n)
        src_before, src_after = _surrounding_sentence(src_sents, b, b + n)
        snippets.append({
            "co_context_before": co_before,
            "co_match": co_match,
            "co_context_after": co_after,
            "source_context_before": src_before,
            "source_match": src_match,
            "source_context_after": src_after,
        })

    return snippets

def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    result = []
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        result.append((m.start(), m.end(), m.group().strip()))
    return result

def _surrounding_sentence(
    sentences: list[tuple[int, int, str]],
    match_start: int,
    match_end: int,
) -> tuple[str, str]:
    before = ""
    after = ""
    for s, e, sent in sentences:
        if e <= match_start:
            before = sent
        if s >= match_end and not after:
            after = sent
            break
    return before, after
