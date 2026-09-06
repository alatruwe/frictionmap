"""Judge-output parse rule (D1, frozen 2026-09-06).

Lenient extraction: the first JSON object found in the response text, scanning
forward from each `{` until raw_decode succeeds. Valid iff that object carries
an integer `score` in {0, 1, 2, 3}: a Python int (bool excluded), or a string
that strips to a single digit 0-3. Floats, other strings, and anything else are
invalid. `justification` is stored as-is and not validated. A response with
stop_reason "refusal" is invalid regardless of text.

Retry-then-missing lives in runner.py; this module only classifies one response.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

VALID_SCORES = frozenset({0, 1, 2, 3})
_DECODER = json.JSONDecoder()


@dataclass(frozen=True)
class ParseResult:
    valid: bool
    score: int | None
    justification: Any
    reason: str | None  # None when valid


def first_json_object(text: str) -> dict | None:
    start = 0
    while True:
        idx = text.find("{", start)
        if idx < 0:
            return None
        try:
            obj, _ = _DECODER.raw_decode(text, idx)
        except ValueError:
            start = idx + 1
            continue
        if isinstance(obj, dict):
            return obj
        start = idx + 1


def coerce_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value in VALID_SCORES else None
    if isinstance(value, str):
        stripped = value.strip()
        if len(stripped) == 1 and stripped.isdigit() and int(stripped) in VALID_SCORES:
            return int(stripped)
    return None


def parse_response(text: str, stop_reason: str | None) -> ParseResult:
    if stop_reason == "refusal":
        return ParseResult(False, None, None, "refusal")
    obj = first_json_object(text)
    if obj is None:
        return ParseResult(False, None, None, "no_json_object")
    justification = obj.get("justification")
    if "score" not in obj:
        return ParseResult(False, None, justification, "score_missing")
    score = coerce_score(obj["score"])
    if score is None:
        return ParseResult(False, None, justification, "score_invalid")
    return ParseResult(True, score, justification, None)
