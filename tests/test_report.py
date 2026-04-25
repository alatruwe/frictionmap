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
    # File A: tool-used (Read) — appears via tool_usage_by_file
    # File B: leakage-detected (edit failure) — appears via leakage_by_file
    # File C: excerpt-attributed via thinking mentioning canonical path
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
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
            {"type": "tool_use", "id": "t3", "name": "Read",
             "input": {"file_path": "/proj/c.py"}},
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
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
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
        blocks.append({"type": "tool_use", "id": f"t{i}", "name": "Read",
                       "input": {"file_path": "/proj/a.py"}})
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", blocks)])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert len(file.excerpts) == 5


def test_excerpt_ordering_by_marker_count(tmp_path: Path) -> None:
    blocks = [
        {"type": "thinking",
         "thinking": "Just one marker: wait. About /proj/a.py."},
        {"type": "tool_use", "id": "t1", "name": "Read",
         "input": {"file_path": "/proj/a.py"}},
        {"type": "thinking",
         "thinking": "wait, actually, hmm, let me — about /proj/a.py for sure."},
        {"type": "tool_use", "id": "t2", "name": "Read",
         "input": {"file_path": "/proj/a.py"}},
    ]
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", blocks)])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert len(file.excerpts) == 2
    first, second = file.excerpts
    assert first.block_signals.marker_count >= second.block_signals.marker_count
    assert first.block_signals.marker_count >= 4  # the four-marker block


def test_missing_file_complexity_is_empty(tmp_path: Path) -> None:
    # /nowhere/x.py is canonical-looking but doesn't exist on disk.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/nowhere/x.py"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/nowhere/x.py")
    assert file.complexity.loc == 0
    assert file.complexity.cyclomatic is None


def test_codebase_meta_name_extracted_from_sessions_dir() -> None:
    assert _extract_codebase_name("-Users-x-Projects-attune") == "attune"
    assert _extract_codebase_name("-Users-x-Projects-my-cool-project") == "my-cool-project"
    # Fallback: no -Projects- substring → last dash segment
    assert _extract_codebase_name("-Users-x-foo") == "foo"
    assert _extract_codebase_name("") == ""


def test_report_has_empty_baselines_in_2c(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
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
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    assert report.meta.schema_version == "1.2"
    assert report.meta.name == "attune"


def test_score_components_default_zero_in_2c(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    file = next(f for f in report.files if f.path == "/proj/a.py")
    assert file.score == 0.0
    assert file.tangle_count == 0
    assert file.thinking_resolution_rate == 0.0
    assert file.score_components.markers.raw == 0.0
    assert file.score_components.markers.contribution == 0.0
