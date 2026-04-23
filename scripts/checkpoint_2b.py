"""Run 2B parser on the attune corpus and print 8 sanity outputs.

Usage: uv run python scripts/checkpoint_2b.py [sessions_dir]

Defaults to the attune project's session logs.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

from ai_friction_map.clusters import find_markers
from ai_friction_map.parser import parse_sessions
from ai_friction_map.windows import (
    get_boundary_clip_count,
    reset_boundary_clip_count,
)

DEFAULT_SESSIONS = Path.home() / ".claude/projects/-Users-adelinelatruwe-Projects-attune"
CANONICAL_DEMO_SESSION = "a70658da-6873-408d-999b-d4136d75de24"


def main() -> None:
    sessions_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SESSIONS
    reset_boundary_clip_count()

    t0 = time.perf_counter()
    corpus = parse_sessions(sessions_dir)
    elapsed = time.perf_counter() - t0

    tiers = Counter()
    cardinality = Counter()
    agent_thinking_count = 0
    canonical_agent_sourced = 0
    cluster_counts = Counter()
    for events in corpus.sessions.values():
        for event in events:
            for block in event.blocks:
                if block.agent_sourced and block.type == "thinking":
                    agent_thinking_count += 1
                if block.type == "thinking" and block.attribution is not None:
                    tiers[block.attribution.tier] += 1
                    n = len(block.attribution.file_paths)
                    if n == 0:
                        cardinality["0"] += 1
                    elif n == 1:
                        cardinality["1"] += 1
                    elif n == 2:
                        cardinality["2"] += 1
                    else:
                        cardinality["3+"] += 1
                if block.type == "thinking" and block.excerpts:
                    cluster_counts[block.excerpts[0].cluster_count] += 1

    demo_events = corpus.sessions.get(CANONICAL_DEMO_SESSION, [])
    for event in demo_events:
        for block in event.blocks:
            if block.agent_sourced:
                canonical_agent_sourced += 1

    leakage_totals = Counter()
    for counts in corpus.leakage_by_file.values():
        leakage_totals["edit_failures"] += counts.edit_failures
        leakage_totals["grep_reformulations"] += counts.grep_reformulations
        leakage_totals["bash_retries"] += counts.bash_retries
        leakage_totals["read_after_edit"] += counts.read_after_edit

    total_attributed = sum(tiers.values())
    pct = lambda n: (100.0 * n / total_attributed) if total_attributed else 0.0
    single = cluster_counts[1] if 1 in cluster_counts else 0
    multi = sum(v for k, v in cluster_counts.items() if k > 1)
    multi_pct = (100.0 * multi / max(1, single + multi))

    print(f"[1] Attribution tiers over {total_attributed} thinking blocks:")
    for tier in ("exact_path", "unique_basename", "temporal_proximity"):
        print(f"      {tier:20s} {tiers[tier]:6d}  ({pct(tiers[tier]):5.1f}%)")
    hi_med_pct = pct(tiers['exact_path']) + pct(tiers['unique_basename'])
    print(f"      exact+basename combined: {hi_med_pct:.1f}%  (target ≈46%)")

    print(f"[2] Attribution cardinality (|file_paths| per thinking block):")
    for k in ("0", "1", "2", "3+"):
        print(f"      {k:3s} files: {cardinality[k]:6d}")

    print(f"[3] agent_sourced blocks on canonical demo session "
          f"({CANONICAL_DEMO_SESSION[:8]}...): {canonical_agent_sourced}")
    print(f"[4] agent_sourced thinking blocks corpus-wide: {agent_thinking_count}")
    print(f"[5] Clusters (marker-bearing blocks):  single={single}  multi={multi}  "
          f"({multi_pct:.1f}% multi)")
    print(f"[6] window_events boundary clip count: {get_boundary_clip_count()}")
    print(f"[7] Leakage totals:")
    for k, v in leakage_totals.items():
        print(f"      {k:22s} {v}")
    print(f"[8] Parse wall-clock: {elapsed:.3f}s "
          f"({corpus.session_count} sessions, {corpus.event_count} events)")


if __name__ == "__main__":
    main()
