"""Shared helpers for the SWE-bench adapter tests (spec §9.1, §9.8).

`fence` is the blindness tripwire: every adapter test module imports it, and
any adapter code path that opens a fenced file fails the test. It mirrors the
manifest tripwire in tests/test_judge_blindness.py, widened to the Phase 2
fence set: the three outcome-bearing data files plus any `results/` path.
"""
from __future__ import annotations

import builtins
import json
import os
import pathlib

import pytest

FENCED_NAMES = ("resolution_status.json", "verified_trajectory_features.csv", "enriched_encodings_all.csv")


def is_fenced(path) -> bool:
    s = str(path)
    if any(name in s for name in FENCED_NAMES):
        return True
    parts = pathlib.PurePath(s).parts
    return "results" in parts


@pytest.fixture
def fence(monkeypatch):
    real_open = builtins.open
    real_path_open = pathlib.Path.open
    opened: list[str] = []

    def guard(path):
        opened.append(str(path))
        if is_fenced(path):
            raise AssertionError(f"adapter opened a fenced path: {path}")

    def fake_open(file, *a, **kw):
        guard(file)
        return real_open(file, *a, **kw)

    def fake_path_open(self, *a, **kw):
        guard(self)
        return real_path_open(self, *a, **kw)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(pathlib.Path, "open", fake_path_open)
    return opened


def _raw_write(path: pathlib.Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, text.encode())
    finally:
        os.close(fd)


def make_replication_tree(tmp_path: pathlib.Path, *, submissions: dict[str, dict[str, object]] | None = None):
    """Build a fake replication-package layout: fenced decoys in `data/` and
    `results/`, and a trajectories root with the given submission folders.

    `submissions` maps folder name -> {filename: json-serialisable content}.
    Returns the trajectories root (the explicit argument every entry point takes).
    """
    pkg = tmp_path / "replication-package"
    (pkg / "data").mkdir(parents=True)
    (pkg / "results").mkdir()
    # Decoys are written through os.open so the `fence` fixture (which guards
    # builtins.open / Path.open) can already be active when the tree is built.
    for name in FENCED_NAMES:
        _raw_write(pkg / "data" / name, "DECOY — must never be read\n")
    _raw_write(pkg / "results" / "summary.csv", "DECOY\n")
    root = pkg / "dataset" / "trajectories" / "verified"
    root.mkdir(parents=True)
    for folder, files in (submissions or {}).items():
        d = root / folder
        d.mkdir()
        for fname, content in files.items():
            _raw_write(d / fname, content if isinstance(content, str) else json.dumps(content))
    return root


# Minimal well-formed file bodies per family (spec §1 shape table).
SWEAGENT_OLD = {"environment": "e", "info": {}, "trajectory": [], "history": []}
EPAM = [{"u1": {"author_name": "Thoughts", "message": "hi", "input_text": ""}}]
SONAR = [{"role": "assistant", "blocks": [], "additional_kwargs": {}}]
SAGE = {"info": {}, "instance_id": "x", "messages": [], "trajectory_format": "f"}
TRAE = [{"role": "assistant", "content": "<think>a</think>"}]
OPENHANDS = [{"role": "assistant", "content": [], "tool_calls": []}]
