"""Seeded sample for the spot-check (Task 2): composition, joined-only universe, determinism."""
from __future__ import annotations

from collections import Counter

from action_encoding.join import JoinedRow
from action_encoding.spotcheck import DOUBAO_FOLDER, SAGE_FOLDER, draw_sample, never_fired, symbol_distribution
from swebench_adapter.registry import population_folders


def _rows() -> list[JoinedRow]:
    rows = []
    for folder in population_folders():
        for i in range(8):
            joined = not (folder == DOUBAO_FOLDER and i < 3)          # 3 unjoined Trae-doubao rows
            rows.append(JoinedRow(folder, "a", "l", f"x__y-{i}", joined, "G P" if joined else None,
                                  0 if joined else None))
    return rows


def test_sample_composition_is_5_5_10_from_joined_rows_only():
    rows = _rows()
    sample = draw_sample(rows, seed=1)
    assert len(sample) == 20 and len({(r.submission_folder, r.instance_id) for r in sample}) == 20
    by = Counter(r.submission_folder for r in sample)
    assert by[SAGE_FOLDER] == 5 and by[DOUBAO_FOLDER] == 5
    rest = {f: n for f, n in by.items() if f not in (SAGE_FOLDER, DOUBAO_FOLDER)}
    assert len(rest) == 10 and set(rest.values()) == {1}                # 10 distinct agents, one each
    assert all(r.joined for r in sample)
    doubao = [r for r in sample if r.submission_folder == DOUBAO_FOLDER]
    assert all(r.instance_id not in {"x__y-0", "x__y-1", "x__y-2"} for r in doubao)


def test_sample_is_deterministic_under_seed():
    rows = _rows()
    a = [(r.submission_folder, r.instance_id) for r in draw_sample(rows, seed=7)]
    b = [(r.submission_folder, r.instance_id) for r in draw_sample(rows, seed=7)]
    c = [(r.submission_folder, r.instance_id) for r in draw_sample(rows, seed=8)]
    assert a == b and a != c


def test_symbol_distribution_and_never_fired():
    c = symbol_distribution(["G G Ls", "P Vp G"])
    assert c == Counter({"G": 3, "Ls": 1, "P": 1, "Vp": 1})
    assert never_fired(c) == ("Lb", "Lt", "L", "Ps", "Pi", "Pr", "Vf", "Ve", "Vr", "E")
