"""File discovery per submission folder (spec §1 discovery rule, Q7).

Candidates = `*.traj` + `*.json`; dedupe on stem, treating the `.traj.json`
double extension as one stem (`.traj` wins a collision, mirroring their glob
order); the stem must match the instance-id pattern `<owner>__<repo>-<n>`.
Non-matching stems (e.g. `preds.json`) are quarantined `non_trajectory` and sit
outside every rate in the spec. Directory globbing is never the population
filter — the registry is (registry.resolve).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

INSTANCE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-\d+$")

NON_TRAJECTORY = "non_trajectory"


def instance_stem(path: Path) -> str:
    """Filename with `.traj`, `.json`, or `.traj.json` removed."""
    stem = path.name
    for ext in (".traj.json", ".traj", ".json"):
        if stem.endswith(ext):
            return stem[: -len(ext)]
    return stem


@dataclass
class Discovery:
    submission_dir: Path
    files: list[Path] = field(default_factory=list)          # instance-id-stem files, deduped, bytewise-sorted
    quarantined: list[tuple[Path, str]] = field(default_factory=list)   # (path, class) — class is `non_trajectory`
    duplicates: list[Path] = field(default_factory=list)     # lost a stem collision to an earlier candidate
    n_candidates: int = 0

    @property
    def instance_ids(self) -> list[str]:
        return [instance_stem(p) for p in self.files]


def discover(submission_dir: Path) -> Discovery:
    submission_dir = Path(submission_dir)
    # `.traj` before `.json` so a `.traj` wins any stem collision (their order).
    candidates = sorted(submission_dir.glob("*.traj"), key=lambda p: p.name.encode()) + sorted(
        submission_dir.glob("*.json"), key=lambda p: p.name.encode()
    )
    result = Discovery(submission_dir=submission_dir, n_candidates=len(candidates))
    seen: set[str] = set()
    kept: list[Path] = []
    for path in candidates:
        if not path.is_file():
            continue
        stem = instance_stem(path)
        if stem in seen:
            result.duplicates.append(path)
            continue
        seen.add(stem)
        if INSTANCE_ID_RE.match(stem):
            kept.append(path)
        else:
            result.quarantined.append((path, NON_TRAJECTORY))
    result.files = sorted(kept, key=lambda p: p.name.encode())
    return result
