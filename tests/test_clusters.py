from __future__ import annotations

from ai_friction_map.clusters import detect_excerpts, find_markers
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
