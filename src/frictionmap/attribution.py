"""Attribute thinking blocks to files via three-tier rule.

Schema 1.2: Attribution.file_paths is a list. Tier 1 and Tier 2 attributions
are typically singletons but may contain multiple paths when thinking
mentions multiple distinct files. Tier 3 attributes to the entire file_paths
list of the nearest tool_use.
"""
from __future__ import annotations

import re

from frictionmap.events import Attribution, Corpus, ParsedEvent
from frictionmap.extraction import _PATH_SUFFIXES
from frictionmap.windows import window_events

_DEFAULT_PROXIMITY_N = 3

_SUFFIX_ALT = "|".join(_PATH_SUFFIXES)
# Bare basename token: word chars, a dot, then a known source-file suffix,
# at a word boundary. Used only in Tier 2 (Tier 1 works on canonical paths).
_BASENAME_RE = re.compile(rf"\b[\w\-.]+\.(?:{_SUFFIX_ALT})\b")


def attribute_thinking_blocks(
    corpus: Corpus,
    proximity_n: int = _DEFAULT_PROXIMITY_N,
) -> None:
    for events in corpus.sessions.values():
        canonical_paths, basename_to_paths = _session_path_index(events)
        for ev_idx, event in enumerate(events):
            for block in event.blocks:
                if block.type != "thinking" or not block.thinking:
                    continue
                block.attribution = _attribute_one(
                    block.thinking,
                    events,
                    ev_idx,
                    canonical_paths,
                    basename_to_paths,
                    proximity_n,
                )


def _session_path_index(
    events: list[ParsedEvent],
) -> tuple[set[str], dict[str, set[str]]]:
    canonical_paths: set[str] = set()
    for event in events:
        for block in event.blocks:
            for p in block.file_paths:
                canonical_paths.add(p)
    basename_to_paths: dict[str, set[str]] = {}
    for p in canonical_paths:
        base = p.rsplit("/", 1)[-1] if "/" in p else p
        basename_to_paths.setdefault(base, set()).add(p)
    return canonical_paths, basename_to_paths


def _path_suffixes(canonical_path: str) -> list[str]:
    """All `/`-boundary-aligned suffixes of a canonical path, longest first.

    E.g. `/a/b/c.py` → `['/a/b/c.py', 'a/b/c.py', 'b/c.py', 'c.py']`.
    """
    out: list[str] = []
    parts = canonical_path.split("/")
    # Full absolute path (includes leading slash if present).
    out.append(canonical_path)
    # Suffixes starting at each subsequent part.
    for i in range(1, len(parts)):
        suffix = "/".join(parts[i:])
        if suffix and suffix not in out:
            out.append(suffix)
    return out


def _tier1_exact_path(
    thinking: str,
    canonical_paths: set[str],
) -> list[str]:
    """Return every canonical path with at least one `/`-boundary suffix
    present in the thinking text. Suffix must appear at a word boundary
    (not preceded/followed by a word char) so `logger.py` does NOT match
    canonical `/proj/my_logger.py`. Schema 1.2: multiple matched paths
    are all returned.
    """
    matched: list[str] = []
    for path in canonical_paths:
        for suffix in _path_suffixes(path):
            if _suffix_present(thinking, suffix):
                matched.append(path)
                break
    return matched


def _suffix_present(text: str, suffix: str) -> bool:
    pattern = rf"(?<!\w){re.escape(suffix)}(?!\w)"
    return re.search(pattern, text) is not None


def _tier2_unique_basename(
    thinking: str,
    basename_to_paths: dict[str, set[str]],
) -> list[str]:
    attributed: list[str] = []
    seen: set[str] = set()
    for m in _BASENAME_RE.finditer(thinking):
        base = m.group(0)
        candidates = basename_to_paths.get(base)
        if candidates and len(candidates) == 1:
            path = next(iter(candidates))
            if path not in seen:
                seen.add(path)
                attributed.append(path)
    return attributed


def _tier3_temporal_proximity(
    events: list[ParsedEvent],
    center_idx: int,
    n: int,
) -> tuple[list[str], int | None, str | None]:
    lo, hi = window_events(events, center_idx, n)
    for d in range(1, n + 1):
        before_idx = center_idx - d
        after_idx = center_idx + d
        if before_idx >= lo:
            paths = _tool_use_file_paths(events[before_idx])
            if paths:
                return (paths, d, "before")
        if after_idx <= hi:
            paths = _tool_use_file_paths(events[after_idx])
            if paths:
                return (paths, d, "after")
    return ([], None, None)


def _tool_use_file_paths(event: ParsedEvent) -> list[str]:
    for block in event.blocks:
        if block.type == "tool_use" and block.file_paths:
            return list(block.file_paths)
    return []


def _attribute_one(
    thinking: str,
    events: list[ParsedEvent],
    ev_idx: int,
    canonical_paths: set[str],
    basename_to_paths: dict[str, set[str]],
    proximity_n: int,
) -> Attribution:
    t1 = _tier1_exact_path(thinking, canonical_paths)
    if t1:
        return Attribution(tier="exact_path", confidence="high", file_paths=t1)
    t2 = _tier2_unique_basename(thinking, basename_to_paths)
    if t2:
        return Attribution(tier="unique_basename", confidence="medium", file_paths=t2)
    paths, distance, direction = _tier3_temporal_proximity(events, ev_idx, proximity_n)
    return Attribution(
        tier="temporal_proximity",
        confidence="low",
        file_paths=paths,
        proximity_distance=distance,
        proximity_direction=direction,
    )
