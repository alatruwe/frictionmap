"""unit → file mention attribution (spec §8, Q10): tiers 1–2 of v1's
`attribute_thinking_blocks` reimplemented on unit text plus the touched-path
set from the path layer. Tier 3 (temporal proximity) is not rebuilt — the
unit's anchor already is that adjacency; units ship `anchor_files` instead.

Fixture-verified against the pin (`src/frictionmap/attribution.py` at
e2d6db2) in tests/test_adapter_mention.py. Logged-deviation wording:
"mention tiers reimplemented on adapter output, fixture-verified against the
pin; proximity tier superseded by step-anchored units." Descriptive use only.
"""
from __future__ import annotations

import re

# Vendored from frictionmap.extraction._PATH_SUFFIXES at the pin; the test
# asserts equality so drift is visible without importing v1 code here.
PATH_SUFFIXES = (
    "py", "js", "ts", "jsx", "tsx",
    "md", "yaml", "yml", "toml", "json",
    "sh", "sql", "html", "css", "rs", "go",
)
_SUFFIX_ALT = "|".join(PATH_SUFFIXES)
_BASENAME_RE = re.compile(rf"\b[\w\-.]+\.(?:{_SUFFIX_ALT})\b")

EXACT_PATH = "exact_path"
UNIQUE_BASENAME = "unique_basename"


def _path_suffixes(canonical_path: str) -> list[str]:
    out = [canonical_path]
    parts = canonical_path.split("/")
    for i in range(1, len(parts) - 1):
        suffix = "/".join(parts[i:])
        if suffix and suffix not in out:
            out.append(suffix)
    return [s for s in out if "/" in s]


def _tier1_pattern(canonical_path: str) -> re.Pattern[str] | None:
    suffixes = _path_suffixes(canonical_path)
    if not suffixes:
        return None
    alt = "|".join(re.escape(s) for s in suffixes)
    return re.compile(rf"(?<![\w-])(?:{alt})(?![\w-])")


class MentionIndex:
    """Per-trajectory lookups, compiled once from the touched-path set."""

    def __init__(self, canonical_paths) -> None:
        paths = set(canonical_paths)
        self.tier1: list[tuple[str, re.Pattern[str]]] = []
        for p in sorted(paths):
            pat = _tier1_pattern(p)
            if pat is not None:
                self.tier1.append((p, pat))
        self.basename_to_paths: dict[str, set[str]] = {}
        for p in paths:
            base = p.rsplit("/", 1)[-1] if "/" in p else p
            self.basename_to_paths.setdefault(base, set()).add(p)

    def attribute(self, text: str) -> tuple[str | None, list[str]]:
        t1 = [p for p, pat in self.tier1 if pat.search(text)]
        if t1:
            return EXACT_PATH, t1
        out: list[str] = []
        seen: set[str] = set()
        for m in _BASENAME_RE.finditer(text):
            cands = self.basename_to_paths.get(m.group(0))
            if cands and len(cands) == 1:
                p = next(iter(cands))
                if p not in seen:
                    seen.add(p)
                    out.append(p)
        if out:
            return UNIQUE_BASENAME, out
        return None, []


def attribute_mentions(text: str, canonical_paths) -> tuple[str | None, list[str]]:
    return MentionIndex(canonical_paths).attribute(text)
