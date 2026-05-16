"""Split thinking blocks into marker clusters and emit per-cluster excerpts.

Phase 3: word-boundary regex over a locked 13-marker lexicon, with markers
inside fenced code blocks filtered out. Cluster detection itself is
unchanged from Phase 2.
"""
from __future__ import annotations

import re

from frictionmap.events import Corpus, Highlight, ThinkingExcerpt

# N=200 chosen via two-corpus hand-tag (2026-05-15, attune + brownfield,
# 20 boundary blocks); robust to "actually"-as-discourse-tic overcount.
# See project_design/ASSUMPTIONS.md T2.12.
CLUSTER_GAP_WORDS = 200
EXCERPT_WORDS = 50

# Empirically calibrated against the attune corpus (April 2026, 30-block
# hand-tagged sample). "but" and "let me check" were dropped — both were
# dominated by forward-planning false positives, not re-evaluation. "let
# me think" and "however" were missing markers caught during the same
# pass.
_LEXICON = (
    "actually", "wait", "hmm", "no,",
    "let me reconsider", "on second thought", "scratch that",
    "hold on", "reconsidering", "i was wrong", "let me think",
    "now I'm realizing", "however",
)

# Longest-first so "let me reconsider" wins over "let me check" at the
# same offset; \b applies at outer boundaries only (the comma in "no,"
# and the apostrophe in "now I'm realizing" are matched literally).
_MARKER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in sorted(_LEXICON, key=len, reverse=True)) + r")",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(r"^```[\s\S]*?^```", re.MULTILINE)
_WORD_RE = re.compile(r"\S+")


def _fenced_regions(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]


def _in_any_region(pos: int, regions: list[tuple[int, int]]) -> bool:
    for start, end in regions:
        if start <= pos < end:
            return True
    return False


def strip_code_fences(text: str) -> str:
    """Remove ``` fenced blocks. Used for per-100-words denominators."""
    return _FENCE_RE.sub("", text)


def find_markers(text: str) -> list[tuple[int, int, str]]:
    """Return (char_start, char_end, matched_text) per marker occurrence
    in original-text coordinates. Hits inside fenced code blocks are
    filtered out — downstream `_excerpts_for_block` consumes the same
    coordinate space, so no offset translation is needed.
    """
    regions = _fenced_regions(text)
    out: list[tuple[int, int, str]] = []
    for m in _MARKER_RE.finditer(text):
        if _in_any_region(m.start(), regions):
            continue
        out.append((m.start(), m.end(), m.group(0)))
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
