"""Extraction identity with sample_validation.build_pool, anchor filter, manifest
loader, and the three gates — all on synthetic corpora."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

from judge_harness import REPO_ROOT
from judge_harness.units import (
    GateError, Unit, anchor_units, extract_blocks, manifest_units, render_sheet,
    sha256_file, sheet_sha256, verify_corpus, verify_labels, verify_sheet_identity,
)
from tests._factories import assistant, jsonl, progress, user


def _load_sampling_script():
    path = REPO_ROOT / "methodology" / "scripts" / "sample_validation.py"
    spec = importlib.util.spec_from_file_location("sample_validation", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


def _think(text):
    return {"type": "thinking", "thinking": text}


def _tool(uid, path):
    return {"type": "tool_use", "id": uid, "name": "Read", "input": {"file_path": path}}


@pytest.fixture
def corpus_root(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "attune").mkdir(parents=True)
    (root / "brownfield").mkdir()
    # session A: two thinking blocks, an empty one (skipped), a text block,
    # and a sub-agent thinking block reached through agent_progress.
    jsonl(root / "attune" / "aaa.jsonl", [
        assistant("sess-a", "u1", [_think("first block\nwith newline"), {"type": "text", "text": "hi"}]),
        assistant("sess-a", "u2", [_tool("t1", "/proj/x.py"), _think("")]),
        user("sess-a", "u3", [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]),
        progress("sess-a", "u4", [_think("agent block")]),
        assistant("sess-a", "u5", [_think("third block")]),
    ])
    # session B: sessionId missing -> id falls back to file stem, per parser.
    jsonl(root / "attune" / "bbb.jsonl", [
        assistant("", "v1", [_think("b0")]),
    ])
    jsonl(root / "brownfield" / "ccc.jsonl", [
        assistant("sess-c", "w1", [_think("c0"), _think("c1")]),
    ])
    return root


def test_extraction_matches_sampling_script(corpus_root):
    sv = _load_sampling_script()
    pool, dropped = sv.build_pool(corpus_root, excluded=set())
    ours = extract_blocks(corpus_root)
    assert dropped == 0
    assert {u.key: (u.corpus, u.text) for u in pool} == ours
    assert ours[("sess-a", 0)] == ("attune", "first block\nwith newline")
    assert ours[("sess-a", 1)] == ("attune", "agent block")   # empty block not counted
    assert ours[("sess-a", 2)] == ("attune", "third block")
    assert ours[("bbb", 0)] == ("attune", "b0")
    assert ours[("sess-c", 1)] == ("brownfield", "c1")
    assert len(ours) == 6


def test_anchor_units_filters_and_orders(corpus_root, tmp_path):
    anchors = tmp_path / "anchors.txt"
    anchors.write_text("# comment\nsess-c\nbbb\n")
    units = anchor_units(corpus_root, anchors)
    assert [(u.position, u.key) for u in units] == [
        (1, ("bbb", 0)), (2, ("sess-c", 0)), (3, ("sess-c", 1)),
    ]
    assert units[2].text == "c1" and units[2].corpus == "brownfield"


def _write_manifest(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["session_id", "block_index", "stratum", "corpus",
                    "file_attachment", "sheet_position", "relabel_subset"])
        w.writerows(rows)


def test_manifest_units_in_sheet_order(corpus_root, tmp_path):
    manifest = tmp_path / "m.csv"
    _write_manifest(manifest, [
        ["sess-c", 1, "random", "brownfield", 0, 2, 0],
        ["sess-a", 2, "oversample", "attune", 1, 1, 1],
    ])
    units = manifest_units(corpus_root, manifest)
    assert [(u.position, u.key, u.text) for u in units] == [
        (1, ("sess-a", 2), "third block"), (2, ("sess-c", 1), "c1"),
    ]
    _write_manifest(manifest, [["sess-a", 9, "random", "attune", 0, 1, 0]])
    with pytest.raises(GateError):
        manifest_units(corpus_root, manifest)          # unit not in corpus
    _write_manifest(manifest, [["sess-a", 0, "random", "brownfield", 0, 1, 0]])
    with pytest.raises(GateError):
        manifest_units(corpus_root, manifest)          # corpus column disagrees


def test_render_sheet_matches_sampling_script(corpus_root):
    sv = _load_sampling_script()
    pool, _ = sv.build_pool(corpus_root, excluded=set())
    main = sorted(pool, key=lambda u: u.key)
    # write_sheet is fixed to REPO_ROOT; call the renderer it delegates to
    expected = sv.render_units(
        "Validation labeling sheet (LOCAL — never commit)",
        [
            "100 thinking blocks in labeling order. Unit key and text only —",
            "no stratum, no corpus, no signal values, no file paths (§4 step 3).",
            "",
            "Score each unit 0-3 per methodology/labeling-rubric.md.",
        ],
        main,
    )
    ours = [Unit(i, u.session_id, u.block_index, u.corpus, u.text)
            for i, u in enumerate(main, start=1)]
    assert render_sheet(ours) == expected
    assert sheet_sha256(ours) == hashlib.sha256(expected.encode("utf-8")).hexdigest()


def test_sheet_identity_gate(tmp_path):
    units = [Unit(1, "s", 0, "attune", "hello"), Unit(2, "s", 1, "attune", "world")]
    seal = tmp_path / "seal.txt"
    seal.write_text(f"# seal\nsha256  labeling-sheet.md    {sheet_sha256(units)}\n")
    verify_sheet_identity(units, seal)
    with pytest.raises(GateError):
        verify_sheet_identity([Unit(1, "s", 0, "attune", "hello"), Unit(2, "s", 1, "attune", "world!")], seal)
    seal.write_text("# no line\n")
    with pytest.raises(GateError):
        verify_sheet_identity(units, seal)


def test_corpus_gate(corpus_root, tmp_path):
    manifest = tmp_path / "corpus-manifest.txt"
    lines = ["# generated"]
    for p in sorted(corpus_root.glob("*/*.jsonl")):
        lines.append(f"{sha256_file(p)}  {p.relative_to(corpus_root)}")
    manifest.write_text("\n".join(lines) + "\n")
    assert verify_corpus(corpus_root, manifest) == 3
    (corpus_root / "attune" / "bbb.jsonl").write_text("{}\n")
    with pytest.raises(GateError):
        verify_corpus(corpus_root, manifest)


def test_labels_gate_hashes_raw_bytes(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_bytes(b"sheet_position,score\r\n1,0")   # CRLF, no trailing newline
    verify_labels(labels, hashlib.sha256(b"sheet_position,score\r\n1,0").hexdigest())
    with pytest.raises(GateError):
        verify_labels(labels, hashlib.sha256(b"sheet_position,score\n1,0\n").hexdigest())
