"""SWE-bench corpus hash manifest (pre-reg §3 pattern: relative path + SHA-256 per file).

Covers exactly the parse-validated population: every instance-id file of the 13
population folders under the discovery rule (spec §1; `.traj.json` one stem,
non-trajectory stems such as `preds.json` quarantined and not listed). Paths are
relative to the trajectories root and are labels — the files are not in this repo.

    uv run python methodology/scripts/build_swebench_manifest.py \
        --root ~/Projects/replication-package/dataset/trajectories/verified \
        --out methodology/swebench-corpus-manifest.txt
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swebench_adapter import discovery, registry  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    root = a.root.expanduser()

    lines: list[str] = []
    counts: dict[str, int] = {}
    quarantined: list[str] = []
    for folder in registry.population_folders():
        registry.resolve(folder)                       # refuses excluded / unknown folders
        d = discovery.discover(root / folder)
        counts[folder] = len(d.files)
        quarantined += [f"{folder}/{p.name}" for p, _ in d.quarantined]
        for p in d.files:
            lines.append(f"{sha256(p)}  {folder}/{p.name}")

    header = [
        f"# Generated {dt.date.today().isoformat()}",
        f"# SWE-bench side: {len(counts)} population folders, {sum(counts.values())} instance-id files "
        f"(discovery rule, spec §1); root = replication-package/dataset/trajectories/verified",
        "# " + "; ".join(f"{f}: {n}" for f, n in counts.items()),
        f"# Not listed (quarantined non_trajectory): {', '.join(quarantined) or 'none'}",
        "# Paths are labels; trajectory files are not in this repository.",
    ]
    a.out.write_text("\n".join(header + lines) + "\n")
    for f, n in counts.items():
        print(f"{f:50} {n}")
    print(f"total {sum(counts.values())}; wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
