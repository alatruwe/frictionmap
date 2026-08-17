"""Descriptive unit count for the v2 pre-registration corpus (§3).

Read-only: uses v1 parsing exactly as shipped. Writes nothing.

Usage: uv run python methodology/scripts/count_units.py <corpus-root>
where <corpus-root> contains attune/ and brownfield/ session dirs.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from frictionmap.attribution import attribute_thinking_blocks
from frictionmap.clusters import find_markers
from frictionmap.parser import parse_sessions

CORPORA = ("attune", "brownfield")


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} <corpus-root>")
    root = Path(sys.argv[1])

    header = (
        f"{'corpus':<12}{'sessions':>9}{'thinking':>9}{'marker+':>9}"
        f"{'attr(file)':>12}{'marker+':>9}"
    )
    print(header)
    print("-" * len(header))

    totals = [0, 0, 0, 0, 0]
    tiers: dict[str, Counter] = {}
    for label in CORPORA:
        corpus = parse_sessions(root / label)
        attribute_thinking_blocks(corpus)

        n_thinking = n_marker = n_attr = n_attr_marker = 0
        tier_counts: Counter = Counter()
        for events in corpus.sessions.values():
            for event in events:
                for block in event.blocks:
                    if block.type != "thinking" or not block.thinking:
                        continue
                    marker_positive = bool(find_markers(block.thinking))
                    n_thinking += 1
                    n_marker += marker_positive
                    attribution = block.attribution
                    if attribution is None:
                        continue
                    tier_counts[attribution.tier] += 1
                    if attribution.file_paths:
                        n_attr += 1
                        n_attr_marker += marker_positive

        row = (len(corpus.sessions), n_thinking, n_marker, n_attr, n_attr_marker)
        print(
            f"{label:<12}{row[0]:>9}{row[1]:>9}{row[2]:>9}{row[3]:>12}{row[4]:>9}"
        )
        totals = [t + v for t, v in zip(totals, row)]
        tiers[label] = tier_counts

    print(
        f"{'TOTAL':<12}{totals[0]:>9}{totals[1]:>9}{totals[2]:>9}"
        f"{totals[3]:>12}{totals[4]:>9}"
    )

    print()
    for label, tier_counts in tiers.items():
        parts = " / ".join(
            f"{tier_counts[tier]} {name}"
            for tier, name in (
                ("exact_path", "exact"),
                ("unique_basename", "basename"),
                ("temporal_proximity", "proximity"),
            )
        )
        print(f"tiers {label}: {parts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
