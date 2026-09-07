"""Blindness tripwires for the SWE-bench adapter (spec §0, §9.1, §9.8).

Built before any loader existed. Every adapter entry point runs under `fence`
in the other adapter test modules; these tests prove the fence itself fires,
that the adapter's own paths stay inside the trajectories root, and that
their `scripts/config.py` is never imported.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

from tests._adapter_fakes import EPAM, FENCED_NAMES, SWEAGENT_OLD, is_fenced, make_replication_tree

ADAPTER_DIR = pathlib.Path(__file__).resolve().parents[1] / "methodology" / "swebench_adapter"


@pytest.mark.parametrize("name", FENCED_NAMES)
def test_fence_fires_on_each_fenced_file(tmp_path, fence, name):
    root = make_replication_tree(tmp_path)
    decoy = root.parents[2] / "data" / name
    with pytest.raises(AssertionError, match="fenced path"):
        decoy.read_text()
    with pytest.raises(AssertionError, match="fenced path"):
        open(decoy).read()


def test_fence_fires_on_results_dir(tmp_path, fence):
    root = make_replication_tree(tmp_path)
    with pytest.raises(AssertionError, match="fenced path"):
        (root.parents[2] / "results" / "summary.csv").read_text()


def test_is_fenced_matches_path_segments_not_substrings():
    assert is_fenced("/x/results/a.csv")
    assert is_fenced("/x/data/resolution_status.json")
    assert not is_fenced("/x/my_results_notes.md")
    assert not is_fenced("/x/dataset/trajectories/verified/a/b.traj")


def test_discovery_and_load_never_leave_the_trajectories_root(tmp_path, fence):
    from swebench_adapter.discovery import discover
    from swebench_adapter.loaders import load_trajectory_file

    root = make_replication_tree(tmp_path, submissions={
        "20240402_sweagent_gpt4": {"a__b-1.traj": SWEAGENT_OLD, "preds.json": {}},
        "20250804_epam-ai-run-claude-4-sonnet": {"a__b-1.traj": EPAM},
    })
    for folder in ("20240402_sweagent_gpt4", "20250804_epam-ai-run-claude-4-sonnet"):
        found = discover(root / folder)
        for f in found.files:
            load_trajectory_file(f, folder)
    assert fence, "expected the loaders to open trajectory files"
    assert all(str(root) in p for p in fence), fence


def test_their_config_is_never_imported():
    # Static: no adapter module imports their `config`; the sha256 is vendored instead.
    pattern = re.compile(r"^\s*(from\s+config\s+import|import\s+config\b)", re.M)
    for src in ADAPTER_DIR.glob("*.py"):
        assert not pattern.search(src.read_text()), f"{src.name} imports their config.py"
    # Dynamic: importing the adapter does not pull a `config` module into sys.modules.
    import swebench_adapter.registry  # noqa: F401
    assert "config" not in sys.modules or not str(getattr(sys.modules["config"], "__file__", "")).endswith(
        "scripts/config.py"
    )
