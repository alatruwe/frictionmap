"""Shared fakes for judge-harness tests. No network, no real client."""
from __future__ import annotations

from pathlib import Path

from judge_harness.client import CallResult
from judge_harness.units import Unit, sha256_file
from tests._factories import assistant, jsonl

VALID = '{"justification": "quotes \\"hmm\\"", "score": 1}'
VALID3 = '{"justification": "quotes \\"wait\\"", "score": 3}'
INVALID = "I would rather not assign a number here."


class Kill(Exception):
    """Non-infra exception used to simulate a killed process mid-pass."""


class FakeJudge:
    """Scripted responses: a str (end_turn text), a (text, stop_reason) tuple,
    or an exception instance to raise."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[tuple[str, str]] = []
        self.count_calls = 0

    def judge(self, system: str, user: str) -> CallResult:
        self.calls.append((system, user))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        text, stop = (item, "end_turn") if isinstance(item, str) else item
        n = len(self.calls)
        return CallResult(text=text, stop_reason=stop, request_id=f"req-{n}",
                          input_tokens=3000 + n, output_tokens=90, model="fake-model",
                          response={"content": [{"type": "text", "text": text}], "stop_reason": stop})

    def count_tokens(self, system: str, user: str) -> int:
        self.count_calls += 1
        return 2900


def units(n: int) -> list[Unit]:
    return [Unit(i, "sess", i - 1, "attune", f"block {i} text") for i in range(1, n + 1)]


def make_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Synthetic corpus root + anchors file + corpus manifest. Session 'anc'
    (2 blocks) is the anchor; 'oth' (1 block) is not."""
    root = tmp_path / "corpus"
    (root / "attune").mkdir(parents=True)
    (root / "brownfield").mkdir()
    jsonl(root / "attune" / "anc.jsonl", [
        assistant("anc", "u1", [{"type": "thinking", "thinking": "anchor one"}]),
        assistant("anc", "u2", [{"type": "thinking", "thinking": "anchor two"}]),
    ])
    jsonl(root / "brownfield" / "oth.jsonl", [
        assistant("oth", "v1", [{"type": "thinking", "thinking": "other"}]),
    ])
    anchors = tmp_path / "anchors.txt"
    anchors.write_text("# excluded sessions\nanc\n")
    manifest = tmp_path / "corpus-manifest.txt"
    manifest.write_text("".join(f"{sha256_file(p)}  {p.relative_to(root)}\n"
                                for p in sorted(root.glob("*/*.jsonl"))))
    return root, anchors, manifest
