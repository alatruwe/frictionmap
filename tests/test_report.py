from __future__ import annotations

from pathlib import Path

import json

from frictionmap.parser import parse_sessions
from frictionmap.report import _extract_codebase_name, assemble_report
from tests._factories import assistant, jsonl, progress, user


def _scan(tmp_path: Path) -> tuple:
    corpus = parse_sessions(tmp_path)
    report = assemble_report(corpus, sessions_dir_name="-Users-x-Projects-attune")
    return corpus, report


def _scan_with_dir(tmp_path: Path) -> tuple:
    corpus = parse_sessions(tmp_path)
    report = assemble_report(
        corpus,
        sessions_dir_name="-Users-x-Projects-attune",
        sessions_dir=tmp_path,
    )
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
    assert bs.kind == "presence_intensity"
    assert bs.n_blocks == 0
    assert bs.n_positive_blocks == 0
    assert bs.presence_rate_corpus == 0.0
    assert bs.median_intensity_among_positives == 0.0
    assert bs.low_confidence is True


def test_schema_version_is_1_3(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    assert report.meta.schema_version == "1.3"
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


def test_model_distribution_counts_events_and_sessions(tmp_path: Path) -> None:
    """Walker-emitted assistant blocks are counted under their own model;
    a session that runs under both a parent model and a sub-agent model
    counts toward both in sessions_by_model."""
    text = [{"type": "text", "text": "ok"}]
    nested = [{"type": "tool_use", "id": "t1", "name": "Read",
               "input": {"file_path": "/proj/x.py"}}]
    jsonl(tmp_path / "a.jsonl", [
        assistant("sA", "u1", text, model="model_A"),
        assistant("sA", "u2", text, model="model_A"),
    ])
    jsonl(tmp_path / "b.jsonl", [
        assistant("sB", "u1", text, model="model_A"),
        progress("sB", "u2", nested, cwd="/proj", model="model_B"),
    ])
    _, report = _scan(tmp_path)
    md = report.meta.model_distribution
    assert md.events_by_model == {"model_A": 3, "model_B": 1}
    assert md.sessions_by_model == {"model_A": 2, "model_B": 1}
    assert md.unknown_model_event_count == 0


def test_session_titles_populated_from_ai_title_events(tmp_path: Path) -> None:
    """When sessions_dir is provided, session_titles maps the 8-char
    session-id prefix to the most recent aiTitle event in each JSONL.
    Sessions without an aiTitle are omitted (UI guards with `&&`)."""
    sid_a = "aaaa1111-bbbb-cccc-dddd-eeeeeeeeeeee"
    sid_b = "bbbb2222-cccc-dddd-eeee-ffffffffffff"
    sid_c = "cccc3333-dddd-eeee-ffff-000000000000"
    edit_a = assistant(sid_a, "u1", [
        {"type": "tool_use", "id": "t1", "name": "Edit",
         "input": {"file_path": "/proj/a.py",
                   "old_string": "a", "new_string": "b"}},
    ])
    edit_b = assistant(sid_b, "u1", [
        {"type": "tool_use", "id": "t1", "name": "Edit",
         "input": {"file_path": "/proj/b.py",
                   "old_string": "a", "new_string": "b"}},
    ])
    edit_c = assistant(sid_c, "u1", [
        {"type": "tool_use", "id": "t1", "name": "Edit",
         "input": {"file_path": "/proj/c.py",
                   "old_string": "a", "new_string": "b"}},
    ])
    title_a = {"type": "ai-title", "sessionId": sid_a, "aiTitle": "First title"}
    title_b_old = {"type": "ai-title", "sessionId": sid_b, "aiTitle": "Old title"}
    title_b_new = {"type": "ai-title", "sessionId": sid_b, "aiTitle": "New title"}
    (tmp_path / f"{sid_a}.jsonl").write_text(
        json.dumps(edit_a) + "\n" + json.dumps(title_a) + "\n",
        encoding="utf-8",
    )
    (tmp_path / f"{sid_b}.jsonl").write_text(
        json.dumps(edit_b) + "\n"
        + json.dumps(title_b_old) + "\n"
        + json.dumps(title_b_new) + "\n",
        encoding="utf-8",
    )
    jsonl(tmp_path / f"{sid_c}.jsonl", [edit_c])

    _, report = _scan_with_dir(tmp_path)
    assert isinstance(report.session_titles, dict)
    assert report.session_titles[sid_a[:8]] == "First title"
    assert report.session_titles[sid_b[:8]] == "New title"  # last wins
    assert sid_c[:8] not in report.session_titles  # no title → omitted
    for key in report.session_titles:
        assert len(key) == 8


def test_session_titles_empty_when_sessions_dir_omitted(tmp_path: Path) -> None:
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/a.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ])
    _, report = _scan(tmp_path)
    assert report.session_titles == {}


def test_ignored_git_internals_filtered_out(tmp_path: Path) -> None:
    # /proj/.git/refs/heads/main: Edit-touched so the loc=0 filter
    # doesn't independently explain the drop. The .git/ pattern must
    # be what filters it.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/.git/refs/heads/main",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/.git/refs/heads/main" not in paths


def test_ignored_pycache_filtered_out(tmp_path: Path) -> None:
    # Both __pycache__/ dir pattern and *.pyc glob must drop their targets.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/src/__pycache__/foo.cpython-311.pyc",
                       "old_string": "a", "new_string": "b"}},
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/proj/loose.pyc",
                       "old_string": "c", "new_string": "d"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/src/__pycache__/foo.cpython-311.pyc" not in paths
    assert "/proj/loose.pyc" not in paths


def test_ignored_node_modules_filtered_out(tmp_path: Path) -> None:
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/node_modules/lodash/index.js",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/node_modules/lodash/index.js" not in paths


def test_ignored_claude_plans_filtered_out(tmp_path: Path) -> None:
    # Use Edit (not Write) so the loc=0 filter doesn't independently
    # explain the drop — the .claude/ pattern must do it.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/Users/x/.claude/plans/foo.md",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/Users/x/.claude/plans/foo.md" not in paths


def test_ignored_env_file_filtered_out(tmp_path: Path) -> None:
    # Bare .env via exact-basename match; .env.production via .env.* glob.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/.env",
                       "old_string": "a", "new_string": "b"}},
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/proj/.env.production",
                       "old_string": "c", "new_string": "d"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/.env" not in paths
    assert "/proj/.env.production" not in paths


def test_ignored_ds_store_filtered_out(tmp_path: Path) -> None:
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/.DS_Store",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/.DS_Store" not in paths


def test_real_source_file_not_filtered(tmp_path: Path) -> None:
    # Negative control: a normal source path under scripts/ must survive.
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/scripts/foo.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    _, report = _scan(tmp_path)
    paths = {f.path for f in report.files}
    assert "/proj/scripts/foo.py" in paths


def test_filter_does_not_affect_baselines(tmp_path: Path) -> None:
    # Tripwire: the filter must be presentation-layer-only. Adding an
    # ignored file (with thinking content that would shift baselines)
    # must not change report.baselines.corpus.markers_per_100w.
    base_dir = tmp_path / "a"
    base_dir.mkdir()
    extended_dir = tmp_path / "b"
    extended_dir.mkdir()

    base_records = [
        assistant("s1", "u1", [
            {"type": "thinking",
             "thinking": "Looking at /proj/foo.py — wait, actually let me reconsider."},
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "/proj/foo.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
    ]
    jsonl(base_dir / "s.jsonl", base_records)

    extended_records = base_records + [
        assistant("s2", "u1", [
            {"type": "thinking",
             "thinking": "About /proj/.env — wait, hmm, actually let me reconsider this carefully."},
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/proj/.env",
                       "old_string": "x", "new_string": "y"}},
        ]),
    ]
    jsonl(extended_dir / "s.jsonl", extended_records)

    _, base_report = _scan(base_dir)
    _, extended_report = _scan(extended_dir)
    base_bs = base_report.baselines.corpus.markers_per_100w
    ext_bs = extended_report.baselines.corpus.markers_per_100w
    assert ext_bs.n_blocks > base_bs.n_blocks  # sanity: ignored file's block IS in baseline
    # But the filter is presentation-only — extended report still drops .env from files.
    extended_paths = {f.path for f in extended_report.files}
    assert "/proj/.env" not in extended_paths
    assert "/proj/foo.py" in extended_paths


def test_model_distribution_unknown_bucket_counts_only_assistant_like(tmp_path: Path) -> None:
    """Assistant events without a model field count toward unknown.
    user events and user-role agent_progress events do not."""
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [{"type": "text", "text": "ok"}]),  # no model kwarg
        user("s1", "u2", "hello"),
        progress("s1", "u3",
                 [{"type": "tool_result", "tool_use_id": "tr", "content": "ok"}],
                 cwd="/proj", nested_role="user"),
    ])
    _, report = _scan(tmp_path)
    md = report.meta.model_distribution
    assert md.events_by_model == {}
    assert md.sessions_by_model == {}
    assert md.unknown_model_event_count == 1
