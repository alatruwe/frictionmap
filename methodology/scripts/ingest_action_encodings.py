"""Task 1 of the action-encoding handoff: join their precomputed encodings to
our 13-agent population and report join coverage per agent.

    uv run python methodology/scripts/ingest_action_encodings.py \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --csv ~/Projects/replication-package/data/enriched_encodings_all.csv \
        --out methodology/results/action-encodings-joined.csv

Prints the per-agent coverage table (markdown) and every unjoined key. Exits 1
when any agent is below 100% — the handoff's stop condition — after writing
the table, so the unjoined rows are on record rather than silently dropped.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from action_encoding.join import (  # noqa: E402
    coverage, csv_rows_for_population_not_on_disk, join_population, load_encodings, render_coverage, write_table,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)

    encodings = load_encodings(a.csv.expanduser())
    rows = join_population(a.root.expanduser(), encodings)
    write_table(rows, a.out)
    cov = coverage(rows)

    print(render_coverage(cov))
    print(f"\ntotal: population={sum(c.n_population for c in cov)} joined={sum(c.n_joined for c in cov)} "
          f"unjoined={sum(c.n_unjoined for c in cov)}")
    reverse = csv_rows_for_population_not_on_disk(rows, encodings)
    print(f"CSV rows for population agents with no file on disk: {len(reverse)}")
    for k in reverse:
        print(f"  {k}")
    incomplete = [c for c in cov if not c.complete]
    for c in incomplete:
        print(f"\nUNJOINED {c.submission_folder} ({c.n_unjoined}):")
        for iid in c.unjoined_ids:
            print(f"  {iid}")
    print(f"\nwrote {a.out}")
    if incomplete:
        print(f"STOP: {len(incomplete)} agent(s) below 100% join coverage (handoff hard requirement)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
