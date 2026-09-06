"""Ledger -> scores.csv rendering and run-manifest merge."""
from __future__ import annotations

import csv

from judge_harness.store import Attempt, append_ledger, load_ledger, read_manifest, render_scores, update_manifest


def _attempt(pos, n, valid, score=None, justification=None):
    return Attempt(pass_id="v1-pass1", sheet_position=pos, session_id="s", block_index=pos - 1,
                   attempt=n, valid=valid, score=score, justification=justification,
                   reason=None if valid else "score_invalid", raw_response_path=f"v1-pass1/raw/{pos:03d}-{n}.json",
                   request_id=f"r{pos}{n}", stop_reason="end_turn", input_tokens=1, output_tokens=1,
                   infra_retries=0, latency_s=0.1, timestamp="t")


def test_render_scores_flags_and_justification_encoding(tmp_path):
    append_ledger(tmp_path, _attempt(2, 1, True, 0, "plain"))
    append_ledger(tmp_path, _attempt(1, 1, False))
    append_ledger(tmp_path, _attempt(1, 2, True, 2, ["not", "a string"]))
    append_ledger(tmp_path, _attempt(3, 1, False))
    append_ledger(tmp_path, _attempt(3, 2, False))
    append_ledger(tmp_path, _attempt(4, 1, False))          # incomplete: mid-retry
    path, rows, incomplete = render_scores(tmp_path, "v1-pass1")
    assert (rows, incomplete) == (3, 1)
    with path.open(encoding="utf-8", newline="") as fh:
        got = list(csv.DictReader(fh))
    assert [r["sheet_position"] for r in got] == ["1", "2", "3"]
    assert got[0]["score"] == "2" and got[0]["justification"] == '["not", "a string"]' and got[0]["retry_flag"] == "1"
    assert got[0]["raw_response_path"] == "v1-pass1/raw/001-2.json"
    assert got[1]["score"] == "0" and got[1]["justification"] == "plain" and got[1]["retry_flag"] == "0"
    assert got[2]["score"] == "" and got[2]["missing_flag"] == "1"
    assert list(got[0]) == ["pass_id", "sheet_position", "session_id", "block_index", "score",
                            "justification", "raw_response_path", "retry_flag", "missing_flag"]
    ledger = load_ledger(tmp_path, "v1-pass1")
    assert [a.attempt for a in ledger[1]] == [1, 2] and ledger[1][1].justification == ["not", "a string"]


def test_update_manifest_merges_passes(tmp_path):
    update_manifest(tmp_path, {"run_id": "x", "passes": {"v1-pass1": {"calls": 2}}})
    update_manifest(tmp_path, {"passes": {"v1-pass1": {"missing": 0}, "v1-pass2": {"calls": 1}}, "mode": "dry-run"})
    m = read_manifest(tmp_path)
    assert m["run_id"] == "x" and m["mode"] == "dry-run"
    assert m["passes"] == {"v1-pass1": {"calls": 2, "missing": 0}, "v1-pass2": {"calls": 1}}
