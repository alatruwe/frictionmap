"""Structural audit (spec §5), outputs 1–7 on the audit sample.

    uv run python methodology/scripts/run_adapter_audit.py \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --out methodology/adapter-audit-report.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swebench_adapter.audit import render, run_audit  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    root = a.root.expanduser()
    a.out.write_text(render(run_audit(root), root, dt.date.today().isoformat()))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
