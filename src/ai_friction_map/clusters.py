"""Split thinking blocks into marker clusters and emit per-cluster excerpts.

Phase 2B uses a stub marker detector (case-insensitive substring match
against a small lexicon). Phase 3 will replace `find_markers` with a
real word-boundary regex; cluster detection itself won't change.
"""
from __future__ import annotations

import re

from ai_friction_map.events import Corpus, Highlight, ThinkingExcerpt

CLUSTER_GAP_WORDS = 100
EXCERPT_WORDS = 50

_STUB_MARKERS = (
    "wait",
    "actually",
    "hmm",
    "let me",
    "on second thought",
    "reconsidering",
    "i was wrong",
)

_WORD_RE = re.compile(r"\S+")


def find_markers(text: str) -> list[tuple[int, int, str]]:
    """Return (char_start, char_end, matched_text) per marker occurrence.

    Stub: case-insensitive substring match. Known false-positive sources
    (e.g. "let me" inside "delete me") are accepted for 2B — Phase 3's
    word-boundary regex replaces this implementation without changing
    cluster-detection code.
    """
    out: list[tuple[int, int, str]] = []
    lowered = text.lower()
    for marker in _STUB_MARKERS:
        start = 0
        while True:
            idx = lowered.find(marker, start)
            if idx == -1:
                break
            out.append((idx, idx + len(marker), text[idx:idx + len(marker)]))
            start = idx + len(marker)
    out.sort(key=lambda x: x[0])
    return out


def detect_excerpts(corpus: Corpus) -> None:
    for events in corpus.sessions.values():
        for event in events:
            for block in event.blocks:
                if block.type != "thinking" or not block.thinking:
                    continue
                block.excerpts = _excerpts_for_block(block.thinking)


def _excerpts_for_block(text: str) -> list[ThinkingExcerpt]:
    markers = find_markers(text)
    if not markers:
        return []

    word_spans = [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]
    marker_word_idxs = [_char_to_word_idx(word_spans, ch_start) for ch_start, _, _ in markers]

    clusters: list[list[int]] = []
    current: list[int] = [0]
    for i in range(1, len(markers)):
        gap = marker_word_idxs[i] - marker_word_idxs[current[-1]]
        if gap <= CLUSTER_GAP_WORDS:
            current.append(i)
        else:
            clusters.append(current)
            current = [i]
    clusters.append(current)

    excerpts: list[ThinkingExcerpt] = []
    total = len(clusters)
    for idx, member_indices in enumerate(clusters):
        first_word_idx = marker_word_idxs[member_indices[0]]
        last_word_idx = marker_word_idxs[member_indices[-1]]
        excerpt_lo_word = max(0, first_word_idx - EXCERPT_WORDS)
        excerpt_hi_word = min(len(word_spans) - 1, last_word_idx + EXCERPT_WORDS)
        char_start = word_spans[excerpt_lo_word][0]
        char_end = word_spans[excerpt_hi_word][1]
        local_text = text[char_start:char_end]
        highlights = [
            Highlight(
                start=markers[mi][0] - char_start,
                end=markers[mi][1] - char_start,
                marker=markers[mi][2],
            )
            for mi in member_indices
        ]
        excerpts.append(ThinkingExcerpt(
            cluster_index=idx,
            cluster_count=total,
            text=local_text,
            highlights=highlights,
        ))
    return excerpts


def _char_to_word_idx(word_spans: list[tuple[int, int]], ch_pos: int) -> int:
    """Return the word index whose span contains ch_pos, or the nearest
    preceding word index if ch_pos falls in whitespace.
    """
    lo, hi = 0, len(word_spans) - 1
    last_before = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end = word_spans[mid]
        if start <= ch_pos < end:
            return mid
        if ch_pos < start:
            hi = mid - 1
        else:
            last_before = mid
            lo = mid + 1
    return last_before
