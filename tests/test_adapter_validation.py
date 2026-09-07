"""Parse-validation harness (spec §6): failure classes, denominator, strict >10%."""
from __future__ import annotations

import json

from swebench_adapter.discovery import NON_TRAJECTORY
from swebench_adapter.validation import AgentValidation, validate, validate_agent
from tests._adapter_fakes import EPAM, SWEAGENT_OLD, make_replication_tree

GOOD = {"trajectory": [{"thought": "t", "action": "ls"}], "history": []}
NO_STRUCTURE = {"trajectory": [{"action": "ls"}], "history": []}
ZERO_ACTIONS = {"trajectory": [{"thought": "only text", "action": ""}], "history": []}


def test_classes_denominator_and_quarantine(tmp_path, fence):
    folder = "20240402_sweagent_gpt4"
    root = make_replication_tree(tmp_path, submissions={folder: {
        "a__a-1.traj": GOOD, "a__a-2.traj": "{not json", "a__a-3.traj": EPAM, "a__a-4.traj": NO_STRUCTURE,
        "a__a-5.traj": ZERO_ACTIONS, "preds.json": {"x": 1},
    }})
    v = validate_agent(root, folder)
    assert v.n_files == 5                                   # preds.json outside the denominator
    assert v.n_file_failures == 2 and v.n_unit_failures == 1 and v.rate == 0.6 and v.over_threshold
    assert v.n_units == 2 and v.n_trajectories_with_units == 2 and v.n_zero_action_trajectories == 1
    classes = {name: cls for name, cls, _ in v.quarantine}
    assert classes == {"preds.json": NON_TRAJECTORY, "a__a-2.traj": "file", "a__a-3.traj": "file", "a__a-4.traj": "unit"}
    qdir = tmp_path / "q"
    validate(root, qdir)
    lines = (qdir / f"{folder}.txt").read_text().splitlines()
    assert len(lines) == 4 and all("\t" in ln for ln in lines)


def test_threshold_is_strict():
    v = AgentValidation(folder="f", family="thought", n_files=10, n_file_failures=1)
    assert v.rate == 0.1 and not v.over_threshold
    v.n_unit_failures = 1
    assert v.over_threshold
    assert not AgentValidation(folder="f", family="thought", n_files=0).over_threshold


def test_all_population_folders_are_validated_and_missing_ones_have_zero_files(tmp_path, fence):
    root = make_replication_tree(tmp_path, submissions={"20240402_sweagent_gpt4": {"a__a-1.traj": GOOD}})
    results = validate(root)
    assert len(results) == 13
    by = {v.folder: v for v in results}
    assert by["20240402_sweagent_gpt4"].n_files == 1 and by["20250804_epam-ai-run-claude-4-sonnet"].n_files == 0
