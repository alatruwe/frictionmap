"""Stability metrics on synthetic score arrays with hand-computed values."""
from __future__ import annotations

import json

import pytest

from judge_harness.metrics import (
    compute_metrics, pairwise_kappa, quadratic_weighted_kappa, rerun_agreement, report_run,
)
from judge_harness.store import Attempt, append_ledger


def test_kappa_perfect_agreement_is_one():
    assert quadratic_weighted_kappa([0, 1, 2, 3, 3], [0, 1, 2, 3, 3]) == pytest.approx(1.0)


def test_kappa_chance_level_is_zero():
    # each rater 50/50 between 0 and 1, independent: observed == expected
    assert quadratic_weighted_kappa([0, 0, 1, 1], [0, 1, 0, 1]) == pytest.approx(0.0)


def test_kappa_hand_computed_example():
    # a=[0,1,2,3,3], b=[0,1,2,3,2]: one off-by-one disagreement at the top.
    # sum(w*O) = 1/9; sum(w*E) = 61/45  ->  kappa = 1 - 5/61 = 56/61
    assert quadratic_weighted_kappa([0, 1, 2, 3, 3], [0, 1, 2, 3, 2]) == pytest.approx(56 / 61)


def test_kappa_weights_are_quadratic():
    # a two-step disagreement costs 4x a one-step one under quadratic weights
    one_step = quadratic_weighted_kappa([0, 1, 2, 3, 1], [0, 1, 2, 3, 2])
    two_step = quadratic_weighted_kappa([0, 1, 2, 3, 1], [0, 1, 2, 3, 3])
    assert one_step > two_step
    # and maximal disagreement across the fixed 0-3 scale is strongly negative
    assert quadratic_weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]) == pytest.approx(-1.0)


def test_kappa_undefined_and_empty():
    assert quadratic_weighted_kappa([2, 2, 2], [2, 2, 2]) is None   # no expected disagreement
    assert quadratic_weighted_kappa([], []) is None
    with pytest.raises(ValueError):
        quadratic_weighted_kappa([1], [1, 2])


def test_rerun_agreement_excludes_missing():
    p1 = {1: 0, 2: 1, 3: 2, 4: None}
    p2 = {1: 0, 2: 1, 3: 3, 4: 1}
    p3 = {1: 0, 2: 1, 3: 2, 4: 1}
    r = rerun_agreement([p1, p2, p3])
    assert (r["n_units"], r["n_compared"], r["n_excluded_missing"], r["n_agree"]) == (4, 3, 1, 2)
    assert r["agreement_pct"] == pytest.approx(66.67)
    assert r["disagreeing_positions"] == [3]
    assert rerun_agreement([{}, {}, {}])["agreement_pct"] is None


def test_pairwise_excludes_missing_on_either_side():
    a = {1: 0, 2: None, 3: 2, 4: 3}
    b = {1: 0, 2: 1, 3: 2}
    r = pairwise_kappa(a, b)
    assert (r["n_units"], r["n_compared"], r["n_excluded_missing"]) == (4, 2, 2)
    assert r["quadratic_weighted_kappa"] == pytest.approx(1.0)
    assert r["disagreeing_positions"] == []


def _attempt(pass_id, pos, n, valid, score):
    return Attempt(pass_id=pass_id, sheet_position=pos, session_id="s", block_index=pos, attempt=n,
                   valid=valid, score=score, justification=None, reason=None if valid else "x",
                   raw_response_path="r", request_id=None, stop_reason="end_turn", input_tokens=1,
                   output_tokens=1, infra_retries=0, latency_s=0.0, timestamp="t")


def test_report_run_reads_ledgers(tmp_path):
    scores = {"v1-pass1": [0, 1, 2, 3], "v1-pass2": [0, 1, 2, 3], "v1-pass3": [0, 1, 2, 2],
              "paraphrase-a": [0, 1, 2, 3]}
    for pass_id, vals in scores.items():
        for pos, s in enumerate(vals, start=1):
            append_ledger(tmp_path, _attempt(pass_id, pos, 1, True, s))
    append_ledger(tmp_path, _attempt("paraphrase-a", 5, 1, False, None))   # incomplete, ignored
    append_ledger(tmp_path, _attempt("v1-pass1", 5, 1, False, None))
    append_ledger(tmp_path, _attempt("v1-pass1", 5, 2, False, None))       # missing
    text = report_run(tmp_path)
    m = json.loads(text)
    assert m == json.loads((tmp_path / "metrics.json").read_text())
    assert m["passes"]["v1-pass1"] == {"n_scored": 4, "n_missing": 1, "n_incomplete": 0}
    assert m["passes"]["paraphrase-a"] == {"n_scored": 4, "n_missing": 0, "n_incomplete": 1}
    assert m["rerun_agreement"]["n_compared"] == 4 and m["rerun_agreement"]["agreement_pct"] == 75.0
    assert m["rerun_agreement"]["disagreeing_positions"] == [4]
    assert m["pairwise_kappa"]["v1-pass1<->paraphrase-a"]["quadratic_weighted_kappa"] == 1.0
    assert m["pairwise_kappa"]["v1-pass1<->paraphrase-b"] == {"skipped": "pass missing"}
    assert compute_metrics(tmp_path)["pairwise_kappa"]["paraphrase-a<->paraphrase-b"] == {"skipped": "pass missing"}
