"""Run the SWE-bench adapter seam-test suite (spec §7) and write the report.

    uv run python methodology/scripts/run_adapter_seam.py \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --their-config ~/Projects/replication-package/scripts/config.py \
        --out methodology/adapter-seam-report.md

The trajectories root is explicit (spec §1, Q11); nothing here resolves a
default path. `--their-config` is hashed as bytes for drift detection and is
never imported.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swebench_adapter.seam import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path, help="trajectories root (…/dataset/trajectories/verified)")
    ap.add_argument("--their-config", type=Path, default=None, help="their scripts/config.py, hashed only")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    report, sections = run(a.root.expanduser(), a.their_config.expanduser() if a.their_config else None)
    a.out.write_text(report)
    for s in sections:
        flag = "  <-- STOP-EARLY" if s.stop_early else ""
        print(f"{s.verdict or '—':5} {s.title}{flag}")
    print(f"wrote {a.out}")
    return 1 if any(s.stop_early for s in sections) else 0


if __name__ == "__main__":
    raise SystemExit(main())
