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
        tier1_patterns, basename_to_paths = _session_path_index(events)
        for ev_idx, event in enumerate(events):
            for block in event.blocks:
                if block.type != "thinking" or not block.thinking:
                    continue
                block.attribution = _attribute_one(
                    block.thinking,
                    events,
                    ev_idx,
                    tier1_patterns,
                    basename_to_paths,
                    proximity_n,
                )


def _session_path_index(
    events: list[ParsedEvent],
) -> tuple[list[tuple[str, re.Pattern[str]]], dict[str, set[str]]]:
    """Build the per-session lookups used by attribution.

    Returns `(tier1_patterns, basename_to_paths)`:
    - `tier1_patterns` — one compiled regex per canonical path, over that
      path's path-fragment suffixes (those containing `/`). Compiled once per
      session and reused across every block, rather than re-escaping suffixes
      per (block × path × suffix).
    - `basename_to_paths` — bare basename → set of canonical paths, for Tier 2.
    """
    canonical_paths: set[str] = set()
    for event in events:
        for block in event.blocks:
            for p in block.file_paths:
                canonical_paths.add(p)
    tier1_patterns: list[tuple[str, re.Pattern[str]]] = []
    for p in sorted(canonical_paths):
        pattern = _tier1_pattern(p)
        if pattern is not None:
            tier1_patterns.append((p, pattern))
    basename_to_paths: dict[str, set[str]] = {}
    for p in canonical_paths:
        base = p.rsplit("/", 1)[-1] if "/" in p else p
        basename_to_paths.setdefault(base, set()).add(p)
    return tier1_patterns, basename_to_paths


def _path_suffixes(canonical_path: str) -> list[str]:
    """Path-fragment suffixes of a canonical path (those containing a `/`),
    longest first.

    E.g. `/a/b/c.py` → `['/a/b/c.py', 'a/b/c.py', 'b/c.py']`. The bare
    basename (`c.py`) is deliberately excluded: matching it would attribute
    every same-basename file in the session at Tier 1, pre-empting Tier 2's
    uniqueness guard. Bare-basename mentions are resolved by Tier 2 instead.
    """
    out: list[str] = []
    parts = canonical_path.split("/")
    # Full path (includes leading slash if present), then each `/`-aligned
    # suffix down to (but excluding) the bare basename.
    out.append(canonical_path)
    for i in range(1, len(parts) - 1):
        suffix = "/".join(parts[i:])
        if suffix and suffix not in out:
            out.append(suffix)
    return [s for s in out if "/" in s]


def _tier1_pattern(canonical_path: str) -> re.Pattern[str] | None:
    """Compile one boundary-anchored alternation over a path's fragment
    suffixes. Returns None if the path has no `/`-containing suffix (e.g. a
    bare basename), which can then only attribute via Tier 2/3.

    Boundaries exclude `-` as well as word chars (`(?<![\\w-]) … (?![\\w-])`)
    so `logger.py` does not match `/proj/my_logger.py` and `my-storage.py`
    does not match canonical `storage.py`.
    """
    suffixes = _path_suffixes(canonical_path)
    if not suffixes:
        return None
    alt = "|".join(re.escape(s) for s in suffixes)
    return re.compile(rf"(?<![\w-])(?:{alt})(?![\w-])")


def _tier1_exact_path(
    thinking: str,
    tier1_patterns: list[tuple[str, re.Pattern[str]]],
) -> list[str]:
    """Return every canonical path with at least one path-fragment suffix
    (containing `/`) present in the thinking text, at a non-word, non-`-`
    boundary. Schema 1.2: multiple matched paths are all returned.
    """
    matched: list[str] = []
    for path, pattern in tier1_patterns:
        if pattern.search(thinking):
            matched.append(path)
    return matched


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
    tier1_patterns: list[tuple[str, re.Pattern[str]]],
    basename_to_paths: dict[str, set[str]],
    proximity_n: int,
) -> Attribution:
    t1 = _tier1_exact_path(thinking, tier1_patterns)
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
