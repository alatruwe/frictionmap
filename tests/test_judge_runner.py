"""Pass runner on a fake judge: retry-then-missing, resume, infra handling."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import anthropic
import httpx2 as httpx
import pytest

from judge_harness.prompts import PLACEHOLDER, Prompt
from judge_harness.runner import PassAborted, run_pass
from judge_harness.store import INFRA_LOG_NAME, load_ledger, render_scores
from tests._judge_fakes import INVALID, VALID, VALID3, FakeJudge, Kill, units

PROMPT = Prompt(name="v1", path=Path("v1.md"), sha256="abc", system="SYS\n",
                user_template=f"<t>\n{PLACEHOLDER}\n</t>")
NOSLEEP = lambda s: None  # noqa: E731


def _rows(run_dir, pass_id):
    path, rows, incomplete = render_scores(run_dir, pass_id)
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh)), incomplete


def test_valid_first_attempt_is_one_call(tmp_path):
    judge = FakeJudge([VALID])
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(1), judge, sleep=NOSLEEP)
    assert (s.calls, s.retried, s.missing, s.units_completed) == (1, 0, 0, 1)
    assert judge.calls == [("SYS\n", "<t>\nblock 1 text\n</t>")]
    rows, incomplete = _rows(tmp_path, "v1-pass1")
    assert incomplete == 0
    assert rows[0]["score"] == "1" and rows[0]["retry_flag"] == "0" and rows[0]["missing_flag"] == "0"
    assert rows[0]["raw_response_path"] == "v1-pass1/raw/001-1.json"
    raw = json.loads((tmp_path / rows[0]["raw_response_path"]).read_text())
    assert raw["parse"] == {"valid": True, "reason": None} and raw["request_id"] == "req-1"
    assert s.first_response_usage["input_tokens"] == 3001


def test_invalid_then_valid_sets_retry_flag(tmp_path):
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(1), FakeJudge([INVALID, VALID3]), sleep=NOSLEEP)
    assert (s.calls, s.retried, s.missing) == (2, 1, 0)
    rows, _ = _rows(tmp_path, "v1-pass1")
    assert rows[0]["score"] == "3" and rows[0]["retry_flag"] == "1" and rows[0]["missing_flag"] == "0"
    assert rows[0]["raw_response_path"] == "v1-pass1/raw/001-2.json"
    assert (tmp_path / "v1-pass1/raw/001-1.json").exists()


def test_invalid_twice_is_missing_with_both_raws_kept(tmp_path):
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(1),
                 FakeJudge([("anything", "refusal"), INVALID]), sleep=NOSLEEP)
    assert (s.calls, s.retried, s.missing) == (2, 1, 1)
    rows, _ = _rows(tmp_path, "v1-pass1")
    assert rows[0]["score"] == "" and rows[0]["missing_flag"] == "1" and rows[0]["retry_flag"] == "1"
    assert sorted(p.name for p in (tmp_path / "v1-pass1/raw").iterdir()) == ["001-1.json", "001-2.json"]
    attempts = load_ledger(tmp_path, "v1-pass1")[1]
    assert [a.reason for a in attempts] == ["refusal", "no_json_object"]


def test_resume_after_kill_makes_no_duplicate_calls(tmp_path):
    first = FakeJudge([VALID, VALID, Kill()])
    with pytest.raises(Kill):
        run_pass(tmp_path, "v1-pass1", PROMPT, units(3), first, sleep=NOSLEEP)
    assert sorted(load_ledger(tmp_path, "v1-pass1")) == [1, 2]
    _, incomplete = _rows(tmp_path, "v1-pass1")
    assert incomplete == 0

    second = FakeJudge([VALID3])
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(3), second, sleep=NOSLEEP)
    assert len(second.calls) == 1 and second.calls[0][1] == "<t>\nblock 3 text\n</t>"
    assert (s.units_skipped_resume, s.units_completed, s.calls) == (2, 1, 1)
    rows, _ = _rows(tmp_path, "v1-pass1")
    assert [r["sheet_position"] for r in rows] == ["1", "2", "3"]


def test_resume_mid_retry_goes_straight_to_attempt_two(tmp_path):
    with pytest.raises(Kill):
        run_pass(tmp_path, "v1-pass1", PROMPT, units(1), FakeJudge([INVALID, Kill()]), sleep=NOSLEEP)
    _, incomplete = _rows(tmp_path, "v1-pass1")
    assert incomplete == 1                       # one invalid attempt, unit not complete

    second = FakeJudge([VALID])
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(1), second, sleep=NOSLEEP)
    assert len(second.calls) == 1 and s.calls == 1 and s.retried == 1
    attempts = load_ledger(tmp_path, "v1-pass1")[1]
    assert [a.attempt for a in attempts] == [1, 2]
    rows, incomplete = _rows(tmp_path, "v1-pass1")
    assert incomplete == 0 and rows[0]["retry_flag"] == "1" and rows[0]["score"] == "1"


def _conn_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://x/v1/messages"))


def test_infra_error_is_logged_not_recorded_as_attempt(tmp_path):
    slept: list[float] = []
    s = run_pass(tmp_path, "v1-pass1", PROMPT, units(1), FakeJudge([_conn_error(), VALID]),
                 sleep=slept.append, base_delay=5.0)
    assert (s.calls, s.infra_retries, s.retried) == (1, 1, 0)
    assert slept == [5.0]
    attempts = load_ledger(tmp_path, "v1-pass1")[1]
    assert len(attempts) == 1 and attempts[0].infra_retries == 1 and attempts[0].attempt == 1
    log = (tmp_path / INFRA_LOG_NAME).read_text().splitlines()
    assert len(log) == 1 and "APIConnectionError" in log[0] and "block 1 text" not in log[0]


def test_infra_exhaustion_aborts_with_ledger_intact(tmp_path):
    slept: list[float] = []
    judge = FakeJudge([VALID] + [_conn_error()] * 4)
    with pytest.raises(PassAborted):
        run_pass(tmp_path, "v1-pass1", PROMPT, units(2), judge, infra_max=3, sleep=slept.append, base_delay=1.0)
    assert slept == [1.0, 2.0, 4.0]
    assert sorted(load_ledger(tmp_path, "v1-pass1")) == [1]
    assert len((tmp_path / INFRA_LOG_NAME).read_text().splitlines()) == 4


def test_non_infra_api_error_propagates(tmp_path):
    response = httpx.Response(400, request=httpx.Request("POST", "https://x"))
    bad = anthropic.BadRequestError("bad", response=response, body=None)
    with pytest.raises(anthropic.BadRequestError):
        run_pass(tmp_path, "v1-pass1", PROMPT, units(1), FakeJudge([bad]), sleep=NOSLEEP)
    assert not (tmp_path / "v1-pass1").exists() or not load_ledger(tmp_path, "v1-pass1")
