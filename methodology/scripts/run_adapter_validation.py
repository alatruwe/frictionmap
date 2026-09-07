"""Parse-validation harness (spec §6): per-agent rates + quarantine listing.

    uv run python methodology/scripts/run_adapter_validation.py \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --out methodology/adapter-parse-validation.md \
        --quarantine-dir methodology/adapter-quarantine
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swebench_adapter.validation import render, validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--quarantine-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    root = a.root.expanduser()
    results = validate(root, a.quarantine_dir)
    a.out.write_text(render(results, root, dt.date.today().isoformat()))
    for v in results:
        flag = "  <-- >10%" if v.over_threshold else ""
        print(f"{v.folder:50} files={v.n_files:4} file_fail={v.n_file_failures:3} unit_fail={v.n_unit_failures:3} "
              f"rate={100 * v.rate:6.2f}% units={v.n_units:6}{flag}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
