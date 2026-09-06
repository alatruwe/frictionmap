"""The dry-run CLI path never touches sample-manifest.csv, and the run manifest
captures what a rerun needs."""
from __future__ import annotations

import builtins
import json
import pathlib

import pytest

import judge_harness.units as units_mod
from judge_harness.__main__ import main
from judge_harness.prompts import load_prompt
from tests._judge_fakes import VALID, VALID3, FakeJudge, make_corpus


@pytest.fixture
def manifest_tripwire(monkeypatch):
    real_open = builtins.open
    real_path_open = pathlib.Path.open

    def guard(path):
        if "sample-manifest.csv" in str(path):
            raise AssertionError(f"dry-run path opened the manifest: {path}")

    def fake_open(file, *a, **kw):
        guard(file)
        return real_open(file, *a, **kw)

    def fake_path_open(self, *a, **kw):
        guard(self)
        return real_path_open(self, *a, **kw)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(pathlib.Path, "open", fake_path_open)
    monkeypatch.setattr(units_mod, "manifest_units",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("manifest_units called")))


def _argv(root, anchors, manifest, runs_dir, *passes, limit=0):
    argv = ["run", "--corpus-root", str(root), "--run-id", "t", "--runs-dir", str(runs_dir),
            "--anchors", str(anchors), "--corpus-manifest", str(manifest)]
    for p in passes:
        argv += ["--pass", p]
    if limit:
        argv += ["--limit", str(limit)]
    return argv


def test_dry_run_never_reads_manifest_and_writes_manifest(tmp_path, manifest_tripwire, capsys):
    root, anchors, manifest = make_corpus(tmp_path)
    runs_dir = tmp_path / "judge-runs"
    judge = FakeJudge([VALID, VALID3, VALID, VALID])
    rc = main(_argv(root, anchors, manifest, runs_dir, "v1-pass1", "paraphrase-a"), client_factory=lambda: judge)
    assert rc == 0
    # only the two anchor-session blocks were judged, once per pass
    assert len(judge.calls) == 4
    v1 = load_prompt("v1")
    assert all(system == v1.system for system, _ in judge.calls[:2])
    assert [u.split("\n")[1] for u, in [(c[1],) for c in judge.calls[:2]]] == ["anchor one", "anchor two"]
    assert "other" not in "".join(u for _, u in judge.calls)

    run_dir = runs_dir / "t"
    m = json.loads((run_dir / "run-manifest.json").read_text())
    assert m["mode"] == "dry-run" and m["unit_source"] == "anchors"
    assert m["corpus_files_verified"] == 2
    assert m["judge"]["model"] == "claude-haiku-4-5-20251001" and m["judge"]["temperature"] == 0
    assert "extra_body" in m["judge"]["temperature_mechanism"] and m["judge"]["sdk"].startswith("anthropic ")
    assert m["prompts"]["v1"]["sha256"] == v1.sha256
    assert m["prompts"]["v1"]["path"] == "methodology/judge-prompts/v1.md"
    assert m["scaffold_tokens"] == {"v1": 2900, "paraphrase-a": 2900} and judge.count_calls == 2
    assert set(m["passes"]) == {"v1-pass1", "paraphrase-a"}
    p = m["passes"]["v1-pass1"]
    assert p["calls"] == 2 and p["missing"] == 0 and p["first_response_usage"]["input_tokens"] == 3001
    assert p["started_at"] and p["ended_at"] and p["latency"]["median_s"] >= 0
    assert (run_dir / "v1-pass1" / "scores.csv").exists() and (run_dir / "paraphrase-a" / "scores.csv").exists()
    out = capsys.readouterr().out
    assert "calls=2" in out and "anchor one" not in out


def test_second_invocation_merges_manifest_and_limit_applies(tmp_path, manifest_tripwire):
    root, anchors, manifest = make_corpus(tmp_path)
    runs_dir = tmp_path / "judge-runs"
    first = FakeJudge([VALID, VALID])
    assert main(_argv(root, anchors, manifest, runs_dir, "v1-pass1"), client_factory=lambda: first) == 0
    created = json.loads((runs_dir / "t" / "run-manifest.json").read_text())["created_at"]

    second = FakeJudge([VALID])
    assert main(_argv(root, anchors, manifest, runs_dir, "v1-pass2", limit=1), client_factory=lambda: second) == 0
    assert len(second.calls) == 1 and second.count_calls == 0    # scaffold count reused
    m = json.loads((runs_dir / "t" / "run-manifest.json").read_text())
    assert m["created_at"] == created
    assert m["passes"]["v1-pass1"]["calls"] == 2 and m["passes"]["v1-pass2"]["units_total"] == 1


def test_validation_flag_without_phrase_fails_before_any_call(tmp_path, capsys):
    root, anchors, manifest = make_corpus(tmp_path)
    judge = FakeJudge([])
    argv = _argv(root, anchors, manifest, tmp_path / "r", "v1-pass1") + ["--validation-run", "--i-confirm", "wrong"]
    assert main(argv, client_factory=lambda: judge) == 1
    assert judge.calls == [] and "gate failed" in capsys.readouterr().err


def test_corpus_drift_fails_before_any_call(tmp_path, capsys):
    root, anchors, manifest = make_corpus(tmp_path)
    (root / "attune" / "anc.jsonl").write_text("{}\n")
    judge = FakeJudge([])
    assert main(_argv(root, anchors, manifest, tmp_path / "r", "v1-pass1"), client_factory=lambda: judge) == 1
    assert judge.calls == []
