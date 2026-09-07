"""Diagnostic for the Task 1 stop: run THEIR Trae parser + encoder, unmodified,
on the Trae-doubao files that did not join, plus a few joined controls.

Their module is imported from a byte-identical copy of the package's
`scripts/` tree (sha256 of both files printed), never from the package itself:
their `config.py` calls `mkdir()` at import time. Their code is not edited.

    uv run --no-project --with pandas --with numpy python \
        methodology/scripts/diag_trae_unjoined.py \
        --pkg-copy <scratch>/pkgcopy \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --table methodology/results/action-encodings-joined.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

FOLDER = "20250928_trae_doubao_seed_code"
CONTROLS = ["astropy__astropy-12907", "astropy__astropy-13033", "django__django-11099"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg-copy", required=True, type=Path)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--table", required=True, type=Path)
    a = ap.parse_args(argv)
    pkg = a.pkg_copy.expanduser()
    for rel in ("scripts/config.py", "scripts/data_processing/extract_enriched_encoding_all.py"):
        print(f"{hashlib.sha256((pkg / rel).read_bytes()).hexdigest()}  {rel}")
    sys.path.insert(0, str(pkg / "scripts" / "data_processing"))
    sys.path.insert(0, str(pkg / "scripts"))
    import extract_enriched_encoding_all as ee  # their module, unmodified

    with a.table.open(newline="") as fh:
        unjoined = [r["instance_id"] for r in csv.DictReader(fh)
                    if r["submission_folder"] == FOLDER and r["joined"] == "0"]
    root = a.root.expanduser() / FOLDER
    parser = ee.PARSERS["trae"]
    for label, ids in (("UNJOINED", unjoined), ("CONTROL", CONTROLS)):
        for iid in ids:
            data = json.loads((root / f"{iid}.json").read_text())
            msgs = [m for m in data if isinstance(m, dict) and m.get("role") == "assistant"]
            fences = sum(str(m.get("content", "")).count("```") for m in msgs)
            fn_tags = sum(str(m.get("content", "")).count("<function=") for m in msgs)
            tool_calls = sum(1 for m in msgs if m.get("tool_calls"))
            steps = parser(data)
            res = ee.encode_trajectory(steps, has_lb_lt=False) if steps else None
            enc = "None" if res is None else res["enriched_encoding"]
            print(f"{label:8} {iid:34} asst={len(msgs):3} tool_calls={tool_calls} fences={fences:3} "
                  f"fn_tags={fn_tags:3} their_steps={len(steps):3} encoding={enc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
