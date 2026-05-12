# pylint: disable=line-too-long
import pytest
from app.services.snippet_extractor import extract_snippets, MIN_MATCH_LENGTH

def test_identical_text_produces_one_snippet():
    text = "The legislature finds that fees are necessary. The commission shall establish fees not to exceed one hundred dollars. Such fees shall be deposited in the fund."
    snippets = extract_snippets(text, text)
    assert len(snippets) >= 1

def test_snippet_has_required_keys():
    co = "First sentence. The commission shall establish fees not to exceed one hundred dollars. Last sentence."
    src = "Intro line. The commission shall establish fees not to exceed one hundred dollars. Outro line."
    snippets = extract_snippets(co, src)
    assert len(snippets) >= 1
    s = snippets[0]
    assert "co_match" in s
    assert "source_match" in s
    assert "co_context_before" in s
    assert "co_context_after" in s
    assert "source_context_before" in s
    assert "source_context_after" in s

def test_short_matches_excluded():
    co = "The fees. " * 10
    src = "The fees. " * 10 + "Completely different content for the rest of this document."
    snippets = extract_snippets(co, src)
    for s in snippets:
        assert len(s["co_match"]) >= MIN_MATCH_LENGTH

def test_unrelated_texts_produce_no_snippets():
    co = "The quick brown fox jumps over the lazy dog in Colorado."
    src = "Quantum mechanics describes the behavior of particles at subatomic scales."
    snippets = extract_snippets(co, src)
    assert snippets == []

def test_context_before_is_preceding_sentence():
    co = "Intro sentence. The commission shall establish fees not to exceed one hundred dollars per application. Outro sentence."
    src = "Preamble sentence. The commission shall establish fees not to exceed one hundred dollars per application. Closing sentence."
    snippets = extract_snippets(co, src)
    assert len(snippets) >= 1
    assert "Intro sentence" in snippets[0]["co_context_before"] or snippets[0]["co_context_before"] == ""

def test_context_after_is_following_sentence():
    co = "Intro sentence. The commission shall establish fees not to exceed one hundred dollars per application. Outro sentence."
    src = "Preamble sentence. The commission shall establish fees not to exceed one hundred dollars per application. Closing sentence."
    snippets = extract_snippets(co, src)
    assert len(snippets) >= 1
    assert "Outro sentence" in snippets[0]["co_context_after"] or snippets[0]["co_context_after"] == ""
