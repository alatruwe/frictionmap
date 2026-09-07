"""Raw file loading and the file-level shape check (spec §1 shape table, §6).

`load_trajectory_file` reads one trajectory file under the trajectories root
and verifies its top-level shape against the registry's expectation for that
submission's family. Everything downstream (seam censuses, extractors) takes
the loaded object from here, so shape failures are classified in one place.

EPAM build rule (spec §2.7): the loader never sorts keys. `json.loads`
preserves document order and that insertion order is the only order EPAM has.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from swebench_adapter import registry

FILE_FAILURE = "file"
UNIT_FAILURE = "unit"


class FileLevelFailure(Exception):
    """JSON unreadable, or top-level shape does not match the family (spec §6)."""


@dataclass
class Loaded:
    path: Path
    submission: registry.Submission
    data: Any


def shape_matches(family: str, data: Any) -> bool:
    """Spec §1 file-level shape table."""
    if family == registry.THOUGHT:
        return isinstance(data, dict) and isinstance(data.get("trajectory"), list)
    if family == registry.EPAM:
        return (isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict)
                and all(isinstance(v, dict) and "author_name" in v for v in data[0].values()))
    if family == registry.SONAR:
        return isinstance(data, list) and all(isinstance(m, dict) and "role" in m and "blocks" in m for m in data)
    if family == registry.SAGE:
        return isinstance(data, dict) and isinstance(data.get("messages"), list)
    if family in (registry.TRAE, registry.THINK_TOOL):
        return isinstance(data, list) and all(isinstance(m, dict) and "role" in m for m in data)
    raise ValueError(f"unknown family {family!r}")


def read_json(path: Path) -> Any:
    """Order-preserving JSON read (no key sorting anywhere)."""
    with Path(path).open("rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def load_trajectory_file(path: Path, folder: str) -> Loaded:
    """Load one file for a population folder; raises FileLevelFailure per §6.

    `folder` is the submission folder name; the registry refuses excluded and
    unknown folders before any byte is read.
    """
    sub = registry.resolve(folder)
    try:
        data = read_json(path)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        raise FileLevelFailure(f"{path.name}: unreadable JSON ({type(e).__name__}: {e})") from e
    if not shape_matches(sub.family, data):
        raise FileLevelFailure(f"{path.name}: top-level shape does not match family {sub.family!r}")
    return Loaded(path=Path(path), submission=sub, data=data)
