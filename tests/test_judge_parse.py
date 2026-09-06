"""D1 parse rule on synthetic responses, including every listed failure mode."""
from __future__ import annotations

import pytest

from judge_harness.parse import coerce_score, first_json_object, parse_response

GOOD = '{"justification": "quotes \\"wait, actually\\"", "score": 2}'


def test_clean_json():
    r = parse_response(GOOD, "end_turn")
    assert r.valid and r.score == 2 and r.reason is None
    assert r.justification == 'quotes "wait, actually"'


def test_fenced_json():
    r = parse_response("```json\n" + GOOD + "\n```", "end_turn")
    assert r.valid and r.score == 2


def test_prose_preamble_and_trailer():
    r = parse_response("Here is my { assessment:\n" + GOOD + "\nHope that helps {", "end_turn")
    assert r.valid and r.score == 2


def test_first_object_wins():
    r = parse_response('{"score": 1} {"score": 3}', "end_turn")
    assert r.valid and r.score == 1


@pytest.mark.parametrize("raw, expected", [
    ('"2"', 2), ('" 2 "', 2), ("0", 0), ("3", 3),
])
def test_score_coercion_accepts(raw, expected):
    r = parse_response('{"justification": "j", "score": %s}' % raw, "end_turn")
    assert r.valid and r.score == expected


@pytest.mark.parametrize("raw, reason", [
    ("2.0", "score_invalid"), ("true", "score_invalid"), ("4", "score_invalid"),
    ("-1", "score_invalid"), ('"two"', "score_invalid"), ('"22"', "score_invalid"),
    ("null", "score_invalid"),
])
def test_score_coercion_rejects(raw, reason):
    r = parse_response('{"justification": "j", "score": %s}' % raw, "end_turn")
    assert not r.valid and r.score is None and r.reason == reason
    assert r.justification == "j"  # stored as-is even when invalid


def test_bool_is_not_an_int():
    assert coerce_score(True) is None and coerce_score(False) is None
    assert coerce_score(1) == 1


def test_score_missing():
    r = parse_response('{"justification": "j"}', "end_turn")
    assert not r.valid and r.reason == "score_missing"


def test_no_json_object():
    r = parse_response("I cannot score this text.", "end_turn")
    assert not r.valid and r.reason == "no_json_object"
    assert first_json_object("[1, 2]") is None
    assert first_json_object("{ not json } " + GOOD)["score"] == 2


def test_refusal_stop_reason_is_invalid_regardless_of_text():
    r = parse_response(GOOD, "refusal")
    assert not r.valid and r.reason == "refusal"


def test_justification_not_validated():
    r = parse_response('{"justification": ["a", "b"], "score": 1}', "end_turn")
    assert r.valid and r.justification == ["a", "b"]
    r = parse_response('{"score": 1}', "end_turn")
    assert r.valid and r.justification is None
