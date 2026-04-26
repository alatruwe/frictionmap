from __future__ import annotations

from pathlib import Path

from ai_friction_map.parser import parse_sessions
from ai_friction_map.report import _extract_codebase_name, assemble_report
from tests._factories import assistant, jsonl, user


def _scan(tmp_path: Path) -> tuple:
    corpus = parse_sessions(tmp_path)
    report = assemble_report(corpus, sessions_dir_name="-Users-x-Projects-attune")
    return corpus, report


def test_interesting_files_union(tmp_path: Path) -> None:
    # File A: Edit-touched — appears via tool_usage_by_file
    # File B: leakage-detected (edit failure) — appears via leakage_by_file
    # File C: excerpt-attributed via thinking mentioning canonical path,
    #         kept via Edit so the LOC=0 filter doesn't drop it.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
        assistant("s1", "u2", [
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/proj/b.py",
                       "old_string": "x", "new_string": "y"}},
        ]),
        user("s1", "u3", [
            {"type": "tool_result", "tool_use_id": "t2",
             "content": "Error: string not found"},
        ]),
        assistant("s1", "u4", [
            {"type": "thinking",
             "thinking": "Looking at /proj/c.py, wait, let me reconsider."},
            {"type": "tool_use", "id": "t3", "name": "Edit",
             "input": {"file_path": "/proj/c.py",
                       "old_string": "c", "new_string": "d"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/a.py" in paths
    assert "/proj/b.py" in paths
    assert "/proj/c.py" in paths


def test_excerpt_carries_session_metadata(tmp_path: Path) -> None:
    records = [
        assistant("session-12345abcdef0", "u1", [
            {"type": "thinking",
             "thinking": "wait, looking at /proj/a.py — actually let me reconsider."},
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "session-12345abcdef0.jsonl", records)
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert file.excerpts, "expected at least one excerpt"
    e = file.excerpts[0]
    assert e.session_id == "session-12345abcdef0"
    assert e.session_id_short == "session-"
    assert e.block_total == 1
    assert e.block_index == 0
    assert e.block_length_words > 0
    assert e.block_signals.length_words > 0
    assert e.block_signals.marker_count >= 2  # "wait" + "actually"


def test_excerpts_capped_at_five_per_file(tmp_path: Path) -> None:
    # Build seven thinking blocks, each one mentioning the same canonical
    # path and including at least one marker, so all seven excerpts attribute
    # to /proj/a.py.
    blocks: list[dict] = []
    for i in range(7):
        blocks.append({"type": "thinking",
                       "thinking": f"wait, looking at /proj/a.py iteration {i}"})
        blocks.append({"type": "tool_use", "id": f"t{i}", "name": "Edit",
                       "input": {"file_path": "/proj/a.py",
                                 "old_string": f"a{i}", "new_string": f"b{i}"}})
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", blocks)])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert len(file.excerpts) == 5


def test_excerpt_ordering_by_marker_count(tmp_path: Path) -> None:
    blocks = [
        {"type": "thinking",
         "thinking": "Just one marker: wait. About /proj/a.py."},
        {"type": "tool_use", "id": "t1", "name": "Edit",
         "input": {"file_path": "/proj/a.py",
                   "old_string": "a", "new_string": "b"}},
        {"type": "thinking",
         "thinking": "wait, actually, hmm, let me reconsider — about /proj/a.py for sure."},
        {"type": "tool_use", "id": "t2", "name": "Edit",
         "input": {"file_path": "/proj/a.py",
                   "old_string": "c", "new_string": "d"}},
    ]
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", blocks)])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert len(file.excerpts) == 2
    first, second = file.excerpts
    assert first.block_signals.marker_count >= second.block_signals.marker_count
    assert first.block_signals.marker_count >= 4  # wait, actually, hmm, let me reconsider


def test_missing_file_kept_when_edited(tmp_path: Path) -> None:
    # /nowhere/x.py doesn't exist on disk but Claude Edit'd it — kept.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/nowhere/x.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/nowhere/x.py")
    assert file.complexity.loc == 0
    assert file.complexity.cyclomatic is None


def test_loc_zero_read_only_filtered_out(tmp_path: Path) -> None:
    # /nowhere/x.py: not on disk, only Read'd → filtered out.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/nowhere/x.py"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/nowhere/x.py" not in paths


def test_loc_zero_write_target_kept(tmp_path: Path) -> None:
    # File doesn't exist on disk but Claude Wrote it (then it was deleted
    # or moved). Friction is real — must be kept.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Write",
             "input": {"file_path": "/nowhere/y.py", "content": "..."}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/nowhere/y.py" in paths


def test_real_file_with_loc_kept_even_if_only_read(tmp_path: Path) -> None:
    # Real .py file on disk; only Read, never edited. LOC > 0 keeps it.
    real = tmp_path / "real.py"
    real.write_text("def f():\n    return 1\n", encoding="utf-8")
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": str(real)}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert str(real) in paths


def test_codebase_meta_name_extracted_from_sessions_dir() -> None:
    assert _extract_codebase_name("-Users-x-Projects-attune") == "attune"
    assert _extract_codebase_name("-Users-x-Projects-my-cool-project") == "my-cool-project"
    # Fallback: no -Projects- substring → last dash segment
    assert _extract_codebase_name("-Users-x-foo") == "foo"
    assert _extract_codebase_name("") == ""


def test_report_has_empty_baselines_in_2c(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    assert report.session_baselines == {}
    bs = report.baselines.corpus.markers_per_100w
    assert bs.median == 0.0 and bs.mad == 0.0 and bs.n == 0
    assert bs.low_confidence is True


def test_schema_version_is_1_2(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    assert report.meta.schema_version == "1.2"
    assert report.meta.name == "attune"


def test_score_components_zero_on_corpus_without_signals(tmp_path: Path) -> None:
    """Empty-corpus edge case: no thinking blocks, no friction signals.

    Contributions stay zero (mad=0 → z=0); multi_file_weight defaults
    to 1.0, not 0.0 — there's no dilution to record.
    """
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert file.score == 0.0
    assert file.tangle_count == 0
    assert file.thinking_resolution_rate == 0.0
    assert file.score_components.markers.raw == 0.0
    assert file.score_components.markers.contribution == 0.0
    assert file.score_components.multi_file_weight == 1.0


def test_score_components_populated_for_attributed_block(tmp_path: Path) -> None:
    """Single thinking block attributed to /proj/a.py, plus tool use.

    tangle_count=1, thinking_resolution_rate=1.0 (block coupled to tool
    use), multi_file_weight=1.0 (single-file attribution). Marker raw
    should be > 0 since "wait" + "actually" + "let me reconsider" are
    in the lexicon.
    """
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "thinking",
             "thinking": "wait, actually — let me reconsider /proj/a.py."},
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert file.tangle_count == 1
    assert file.thinking_resolution_rate == 1.0
    assert file.score_components.multi_file_weight == 1.0
    assert file.score_components.markers.raw > 0.0
    assert file.score_components.tool_use_coupling.raw == 1.0


def test_multi_file_weight_dilutes_with_shared_attribution(tmp_path: Path) -> None:
    """Two attributed blocks: one single-file (full credit), one shared
    with /proj/b.py (1/2 credit). multi_file_weight for /proj/a.py
    must be < 1.0 — the actual scaling factor of marker contribution.
    """
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "thinking",
             "thinking": "wait, actually about /proj/a.py."},
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
            {"type": "thinking",
             "thinking": "hmm, /proj/a.py and /proj/b.py both — wait."},
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "c", "new_string": "d"}},
            {"type": "tool_use", "id": "t3", "name": "Edit",
             "input": {"file_path": "/proj/b.py",
                       "old_string": "e", "new_string": "f"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    file_a = next(f for f in report.files if f.path == "/proj/a.py")
    assert file_a.tangle_count == 2  # full credit per attributed block
    assert file_a.score_components.multi_file_weight < 1.0
