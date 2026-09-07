"""Join of their `enriched_encodings_all.csv` to the population (action-encoding handoff, Task 1).

The join deliberately reads the fenced CSV, so these tests do not use `fence`.
"""
from __future__ import annotations

import csv
import pathlib

import pytest

from action_encoding.join import (
    DuplicateEncodingKey,
    coverage,
    csv_rows_for_population_not_on_disk,
    join_population,
    load_encodings,
    write_table,
)
from tests._adapter_fakes import SWEAGENT_OLD, TRAE, make_replication_tree

GPT4 = "20240402_sweagent_gpt4"                  # agent SWE-agent, llm gpt-4
DOUBAO = "20250928_trae_doubao_seed_code"        # agent Trae, llm doubao-seed-code
HEADER = ["instance_id", "agent_name", "framework", "llm_name", "is_failed", "n_raw_steps", "n_encoded_steps",
          "enriched_encoding", "base_encoding", "has_lb_lt_distinction"]


def _csv(path: pathlib.Path, rows: list[tuple[str, str, str, str, str]]) -> pathlib.Path:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for iid, agent, llm, failed, enc in rows:
            w.writerow([iid, agent, "fmt", llm, failed, "3", "2", enc, "PG", "False"])
    return path


def test_join_keys_on_registry_agent_llm_and_stem(tmp_path):
    root = make_replication_tree(tmp_path, submissions={
        GPT4: {"a__b-1.traj": SWEAGENT_OLD, "a__b-2.traj.json": SWEAGENT_OLD, "preds.json": {}},
        DOUBAO: {"a__b-1.json": TRAE, "a__b-3.json": TRAE},
    })
    enc = load_encodings(_csv(tmp_path / "e.csv", [
        ("a__b-1", "SWE-agent", "gpt-4", "1", "P G"),
        ("a__b-2", "SWE-agent", "gpt-4", "0", "Lb P"),
        ("a__b-1", "Trae", "doubao-seed-code", "0", "G"),
        ("a__b-1", "SWE-agent", "gpt-4o", "0", "X"),          # same agent, other llm: must not join to GPT4
        ("a__b-9", "Trae", "doubao-seed-code", "1", "G G"),   # in CSV, no file on disk
        ("a__b-1", "Skywork", "qwen-32b", "1", "G"),          # excluded agent: ignored entirely
    ]))
    rows = join_population(root, enc)
    by = {(r.submission_folder, r.instance_id): r for r in rows}
    assert set(by) == {(GPT4, "a__b-1"), (GPT4, "a__b-2"), (DOUBAO, "a__b-1"), (DOUBAO, "a__b-3")}
    assert by[(GPT4, "a__b-1")].joined and by[(GPT4, "a__b-1")].enriched_encoding == "P G"
    assert by[(GPT4, "a__b-1")].is_failed == 1
    assert by[(GPT4, "a__b-2")].joined and by[(GPT4, "a__b-2")].enriched_encoding == "Lb P"   # .traj.json stem
    assert by[(DOUBAO, "a__b-1")].joined and by[(DOUBAO, "a__b-1")].is_failed == 0
    assert not by[(DOUBAO, "a__b-3")].joined
    assert by[(DOUBAO, "a__b-3")].enriched_encoding is None and by[(DOUBAO, "a__b-3")].is_failed is None
    assert csv_rows_for_population_not_on_disk(rows, enc) == [("Trae", "doubao-seed-code", "a__b-9")]


def test_coverage_lists_unjoined_ids_and_flags_incomplete_agents(tmp_path):
    root = make_replication_tree(tmp_path, submissions={
        GPT4: {"a__b-1.traj": SWEAGENT_OLD},
        DOUBAO: {"a__b-1.json": TRAE, "a__b-3.json": TRAE},
    })
    enc = load_encodings(_csv(tmp_path / "e.csv", [
        ("a__b-1", "SWE-agent", "gpt-4", "1", "P"),
        ("a__b-1", "Trae", "doubao-seed-code", "0", "G"),
    ]))
    cov = {c.submission_folder: c for c in coverage(join_population(root, enc))}
    assert len(cov) == 13                                   # every population folder reported, present or not
    assert cov[GPT4].complete and cov[GPT4].n_population == 1 and cov[GPT4].coverage == 1.0
    assert not cov[DOUBAO].complete
    assert (cov[DOUBAO].n_population, cov[DOUBAO].n_joined, cov[DOUBAO].n_unjoined) == (2, 1, 1)
    assert cov[DOUBAO].unjoined_ids == ("a__b-3",)
    assert cov["20240402_sweagent_claude3opus"].n_population == 0    # folder absent: 0/0, not an error


def test_duplicate_csv_key_is_refused(tmp_path):
    dup = [("a__b-1", "SWE-agent", "gpt-4", "1", "P"), ("a__b-1", "SWE-agent", "gpt-4", "0", "G")]
    p = _csv(tmp_path / "e.csv", dup)
    with pytest.raises(DuplicateEncodingKey):
        load_encodings(p)


def test_table_round_trips_unjoined_rows_as_blank_not_dropped(tmp_path):
    root = make_replication_tree(tmp_path, submissions={DOUBAO: {"a__b-1.json": TRAE, "a__b-3.json": TRAE}})
    enc = load_encodings(_csv(tmp_path / "e.csv", [("a__b-1", "Trae", "doubao-seed-code", "0", "G Ls")]))
    out = tmp_path / "t.csv"
    write_table(join_population(root, enc), out)
    with out.open(newline="") as fh:
        got = list(csv.DictReader(fh))
    assert [(r["instance_id"], r["joined"], r["enriched_encoding"], r["is_failed"]) for r in got] == [
        ("a__b-1", "1", "G Ls", "0"), ("a__b-3", "0", "", ""),
    ]
