from __future__ import annotations

from ai_friction_map.clusters import (
    _LEXICON,
    detect_excerpts,
    find_markers,
    strip_code_fences,
)
from ai_friction_map.events import Block, Corpus, ParsedEvent


def _mk_corpus_with_thinking(text: str) -> Corpus:
    corpus = Corpus()
    block = Block(type="thinking", thinking=text)
    event = ParsedEvent(
        session_id="s1",
        event_index=0,
        type="assistant",
        timestamp="t",
        cwd="/proj",
        uuid="u1",
        parent_uuid=None,
        blocks=[block],
    )
    corpus.sessions["s1"] = [event]
    return corpus


def _block_excerpts(corpus: Corpus):
    return corpus.sessions["s1"][0].blocks[0].excerpts


def test_single_cluster_single_marker():
    corpus = _mk_corpus_with_thinking("wait, that's not right at all")
    detect_excerpts(corpus)
    excerpts = _block_excerpts(corpus)
    assert len(excerpts) == 1
    assert excerpts[0].cluster_index == 0
    assert excerpts[0].cluster_count == 1
    assert len(excerpts[0].highlights) == 1
    assert excerpts[0].highlights[0].marker.lower() == "wait"


def test_single_cluster_multiple_markers():
    corpus = _mk_corpus_with_thinking("wait, actually, hmm, this is off")
    detect_excerpts(corpus)
    excerpts = _block_excerpts(corpus)
    assert len(excerpts) == 1
    assert excerpts[0].cluster_count == 1
    assert len(excerpts[0].highlights) == 3


def test_two_clusters_separated_by_long_gap():
    filler = " ".join(["lorem"] * 150)
    text = f"wait, that seems wrong. {filler} actually, now I see it"
    corpus = _mk_corpus_with_thinking(text)
    detect_excerpts(corpus)
    excerpts = _block_excerpts(corpus)
    assert len(excerpts) == 2
    assert excerpts[0].cluster_count == 2
    assert excerpts[1].cluster_count == 2
    assert excerpts[0].cluster_index == 0
    assert excerpts[1].cluster_index == 1


def test_zero_markers_produces_no_excerpts():
    corpus = _mk_corpus_with_thinking("this is just a plain thought with no markers")
    detect_excerpts(corpus)
    assert _block_excerpts(corpus) == []


def test_highlight_char_offsets_within_excerpt_text():
    corpus = _mk_corpus_with_thinking("some preamble wait, reconsidering this")
    detect_excerpts(corpus)
    excerpt = _block_excerpts(corpus)[0]
    for h in excerpt.highlights:
        assert 0 <= h.start < len(excerpt.text)
        assert 0 < h.end <= len(excerpt.text)
        assert excerpt.text[h.start:h.end].lower() == h.marker.lower()


def test_cluster_count_matches_across_siblings():
    filler = " ".join(["word"] * 150)
    text = f"wait here {filler} actually there {filler} hmm then"
    corpus = _mk_corpus_with_thinking(text)
    detect_excerpts(corpus)
    excerpts = _block_excerpts(corpus)
    assert len(excerpts) == 3
    for e in excerpts:
        assert e.cluster_count == 3


def test_find_markers_returns_sorted_positions():
    text = "actually wait hmm"
    markers = find_markers(text)
    positions = [m[0] for m in markers]
    assert positions == sorted(positions)


def test_find_markers_case_insensitive():
    markers = find_markers("Wait and ACTUALLY and hmm")
    assert len(markers) == 3


def test_lexicon_locked():
    assert _LEXICON == (
        "actually", "wait", "hmm", "no,",
        "let me reconsider", "on second thought", "scratch that",
        "hold on", "reconsidering", "i was wrong", "let me think",
        "now I'm realizing", "however",
    )


def test_word_boundary_no_substring_let_me():
    assert find_markers("delete me from the list") == []


def test_word_boundary_no_substring_no_comma():
    assert find_markers("anno, the year was 1066") == []


def test_dropped_markers_no_longer_matched():
    # "but" and "let me check" were calibrated out — must not re-enter
    # the lexicon as a regression.
    assert find_markers("but it might still work") == []
    assert find_markers("let me check the docs first") == []


def test_let_me_think_matches():
    markers = find_markers("let me think about this carefully")
    assert len(markers) == 1
    assert markers[0][2].lower() == "let me think"


def test_however_matches():
    markers = find_markers("However, the schema is wrong")
    assert len(markers) == 1
    assert markers[0][2].lower() == "however"


def test_no_comma_disambiguator_matches():
    markers = find_markers("no, that won't work")
    assert len(markers) == 1
    assert markers[0][2].lower() == "no,"


def test_no_problem_does_not_match():
    assert find_markers("no problem here, all good") == []


def test_multi_word_literal_whitespace():
    # Tab between "let me" and "reconsider" → no match.
    assert find_markers("let me\treconsider that") == []


def test_multi_word_literal_whitespace_double_space():
    # Two spaces between words → no match (literal single space only).
    assert find_markers("let me  reconsider that") == []


def test_longest_first_alternation():
    # "let me reconsider" should win over "let me think" prefix; both are
    # in the lexicon but the longer match should be preferred at this offset.
    markers = find_markers("let me reconsider this approach")
    matched = [m[2].lower() for m in markers]
    assert matched == ["let me reconsider"]


def test_now_im_realizing_case_insensitive():
    markers = find_markers("Now I'm Realizing this is wrong")
    assert len(markers) == 1


def test_marker_inside_fence_filtered():
    text = "outside wait\n```\ninside wait inside\n```\nafter"
    markers = find_markers(text)
    matched_offsets = [m[0] for m in markers]
    # The "wait" inside the fence must be filtered. The two outside
    # ("outside wait" and the implicit "wait" prefix of "wait inside"
    # is INSIDE the fence, so excluded) — only the very first remains.
    assert len(markers) == 1
    assert text[markers[0][0]:markers[0][1]].lower() == "wait"
    # Sanity: the surviving offset is before any fence.
    assert matched_offsets[0] < text.index("```")


def test_marker_outside_fence_on_same_line_hits():
    # "actually" sits on the same line as the closing fence, after the
    # third backtick — must hit and offsets must point at original text.
    text = "```\ncode\n``` actually here"
    markers = find_markers(text)
    assert len(markers) == 1
    start, end, marker = markers[0]
    assert text[start:end] == "actually"
    assert marker.lower() == "actually"


def test_strip_code_fences_removes_fenced_block():
    text = "before\n```\nfenced wait\n```\nafter"
    stripped = strip_code_fences(text)
    assert "fenced" not in stripped
    assert "before" in stripped and "after" in stripped


def test_find_markers_offsets_roundtrip_through_word_index():
    # Char offsets emitted by find_markers must locate words in the
    # original text — the downstream cluster detector relies on this.
    from ai_friction_map.clusters import _WORD_RE, _char_to_word_idx
    text = "some preamble wait, reconsidering this"
    markers = find_markers(text)
    word_spans = [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]
    for ch_start, ch_end, marker_text in markers:
        word_idx = _char_to_word_idx(word_spans, ch_start)
        ws_start, _ = word_spans[word_idx]
        # The word containing this marker offset starts at or before the
        # marker (markers can begin mid-word for the comma-suffixed "no,",
        # but our test set has only word-aligned markers).
        assert ws_start <= ch_start
        assert text[ch_start:ch_end].lower() == marker_text.lower()
