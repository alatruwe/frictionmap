from __future__ import annotations

from frictionmap.attribution import attribute_thinking_blocks
from frictionmap.parser import parse_sessions
from tests._factories import (
    assistant,
    jsonl,
    progress,
    system_compact,
    user,
)


def _read_use(tool_id: str, file_path: str) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Read",
            "input": {"file_path": file_path}}


def _thinking(text: str) -> dict:
    return {"type": "thinking", "thinking": text}


def _first_thinking_attribution(corpus, session_id="s1"):
    for event in corpus.sessions[session_id]:
        for block in event.blocks:
            if block.type == "thinking":
                return block.attribution
    return None


def test_attribution_exact_path(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/src/storage.py")]),
        assistant("s1", "u2", [_thinking("I'm reading /proj/src/storage.py closely")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "exact_path"
    assert attr.confidence == "high"
    assert attr.file_paths == ["/proj/src/storage.py"]


def test_attribution_exact_path_suffix_match(tmp_path):
    # Canonical is absolute, thinking mentions a shorter suffix.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/Users/x/proj/src/storage.py")],
                  cwd="/Users/x/proj"),
        assistant("s1", "u2", [_thinking("fixed src/storage.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "exact_path"
    assert attr.file_paths == ["/Users/x/proj/src/storage.py"]


def test_attribution_exact_path_disambiguates_by_path_fragment(tmp_path):
    # Two canonical paths both ending in storage.py; thinking mentions the
    # path fragment "attune/storage.py". Tier 1 matches ONLY the path whose
    # fragment suffix appears — the bare "storage.py" is not a Tier 1 suffix,
    # so /proj/other/storage.py is no longer over-claimed (the C2 fix).
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/attune/storage.py")],
                  cwd="/proj"),
        assistant("s1", "u2", [_read_use("t2", "/proj/other/storage.py")],
                  cwd="/proj"),
        assistant("s1", "u3", [_thinking("revisit attune/storage.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    # Only /proj/attune/storage.py has "attune/storage.py" as a fragment
    # suffix. /proj/other/storage.py has no path-fragment suffix present, and
    # bare "storage.py" no longer attributes at Tier 1.
    assert attr.tier == "exact_path"
    assert attr.file_paths == ["/proj/attune/storage.py"]


def test_attribution_exact_path_respects_path_boundary(tmp_path):
    # Session has my_logger.py; thinking mentions plain logger.py.
    # Must NOT attribute — "logger.py" is not a /-boundary suffix of
    # "/proj/my_logger.py".
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/my_logger.py")]),
        assistant("s1", "u2", [_thinking("thinking about logger.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    # No exact-path match; Tier 2 basename also fails (session has no
    # "logger.py" basename). Falls through to Tier 3.
    assert attr.tier != "exact_path"


def test_attribution_tier2_multiple_unique_basenames_attributed(tmp_path):
    # Thinking mentions two bare basenames, each unique in the session. Neither
    # is a Tier 1 path fragment, so both resolve via Tier 2 unique_basename
    # (schema-1.2 multi-file rule applies at Tier 2 too).
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/storage.py")]),
        assistant("s1", "u2", [_read_use("t2", "/proj/logger.py")]),
        assistant("s1", "u3", [_thinking("storage.py talks to logger.py here")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "unique_basename"
    assert attr.confidence == "medium"
    assert set(attr.file_paths) == {"/proj/storage.py", "/proj/logger.py"}


def test_attribution_tier1_multiple_path_fragments_attributed(tmp_path):
    # Thinking mentions two distinct path fragments (each contains "/"), so
    # both still attribute at Tier 1 under the schema-1.2 multi-file rule.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/a/storage.py")], cwd="/proj"),
        assistant("s1", "u2", [_read_use("t2", "/proj/b/logger.py")], cwd="/proj"),
        assistant("s1", "u3",
                  [_thinking("a/storage.py talks to b/logger.py here")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "exact_path"
    assert attr.confidence == "high"
    assert set(attr.file_paths) == {"/proj/a/storage.py", "/proj/b/logger.py"}


def test_attribution_unique_basename(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/deep/path/storage.py")],
                  cwd="/proj"),
        assistant("s1", "u2", [_thinking("storage.py is acting weird")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    # Bare "storage.py" is not a Tier 1 path fragment, so Tier 1 misses and
    # Tier 2 resolves the unique basename to its one canonical path.
    assert attr.tier == "unique_basename"
    assert attr.confidence == "medium"
    assert attr.file_paths == ["/proj/deep/path/storage.py"]


def test_attribution_unique_basename_fires_when_tier1_misses():
    # A bare basename in thinking is no longer a Tier 1 suffix, so Tier 1
    # misses and Tier 2 resolves it when the basename is unique in the
    # session. Direct call to keep the Tier 2 contract pinned in isolation.
    from frictionmap.attribution import _tier2_unique_basename
    basename_to_paths = {"storage.py": {"/proj/storage.py"}}
    result = _tier2_unique_basename("talking about storage.py", basename_to_paths)
    assert result == ["/proj/storage.py"]


def test_attribution_ambiguous_basename_falls_through():
    # Two session files share basename utils.py. Tier 2 (in isolation) drops
    # the ambiguous basename since it resolves to more than one path.
    from frictionmap.attribution import _tier2_unique_basename
    basename_to_paths = {"utils.py": {"/proj/a/utils.py", "/proj/b/utils.py"}}
    result = _tier2_unique_basename("look at utils.py", basename_to_paths)
    assert result == []


def test_attribution_ambiguous_basename_falls_through_end_to_end(tmp_path):
    # Two session files share basename utils.py; thinking names the bare
    # basename. Tier 1 no longer over-claims both (the C2 fix), Tier 2 drops
    # it as ambiguous, so attribution falls through to Tier 3 — NOT exact_path.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/a/utils.py")], cwd="/proj"),
        assistant("s1", "u2", [_read_use("t2", "/proj/b/utils.py")], cwd="/proj"),
        assistant("s1", "u3", [_thinking("look at utils.py")], cwd="/proj"),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier != "exact_path"
    assert attr.tier != "unique_basename"
    assert attr.tier == "temporal_proximity"


def test_attribution_tier1_pattern_hyphen_boundary():
    # The Tier 1 pattern's boundary excludes "-" as well as word chars, so a
    # path fragment preceded by "-" does not false-match (symmetric with "_").
    from frictionmap.attribution import _tier1_pattern
    pat = _tier1_pattern("/proj/src/storage.py")
    assert pat is not None
    assert pat.search("look at src/storage.py here")      # clean boundary
    assert pat.search("/proj/src/storage.py is hot")       # full path
    assert pat.search("foo_src/storage.py") is None        # "_" boundary blocks
    assert pat.search("vendored-src/storage.py") is None   # "-" boundary blocks


def test_attribution_no_filename_falls_through(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/storage.py")]),
        assistant("s1", "u2", [_thinking("I'm confused about the architecture")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"


def test_attribution_temporal_proximity_before(tmp_path):
    # Tool_use at index 0; thinking at index 2; proximity_distance = 2, before.
    # Thinking text mentions nothing filename-like.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/a.py")]),
        assistant("s1", "u2", []),
        assistant("s1", "u3", [_thinking("this is weird somehow")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"
    assert attr.file_paths == ["/proj/a.py"]
    assert attr.proximity_distance == 2
    assert attr.proximity_direction == "before"


def test_attribution_temporal_proximity_tiebreak(tmp_path):
    # Equal distance before/after; prefer before.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/before.py")]),
        assistant("s1", "u2", [_thinking("hmm something's up")]),
        assistant("s1", "u3", [_read_use("t2", "/proj/after.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"
    assert attr.file_paths == ["/proj/before.py"]
    assert attr.proximity_direction == "before"


def test_attribution_temporal_does_not_cross_compact_boundary(tmp_path):
    # Closest tool_use is at index 0, but compact_boundary at index 1.
    # Thinking at index 2. Window from 2 with n=3 stops at index 2 (lo=2).
    # The tool_use at index 0 is unreachable. Next eligible on the other
    # side: nothing. Expect unattributed.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/a.py")]),
        system_compact("s1", "u2"),
        assistant("s1", "u3", [_thinking("no filename here")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"
    assert attr.file_paths == []


def test_attribution_none_when_no_candidates(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_thinking("just floating thought, no files mentioned")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"
    assert attr.file_paths == []
    assert attr.proximity_distance is None
    assert attr.proximity_direction is None


def test_attribution_tier3_multi_file_tool_use_attributes_to_all(tmp_path):
    # Nearest tool_use is a Grep whose resolved file_paths has 2 entries.
    # Tier 3 attributes to ALL of them (schema 1.2).
    use = [{"type": "tool_use", "id": "toolu_g", "name": "Grep",
            "input": {"path": "src", "pattern": "foo"}}]
    res = [{"type": "tool_result", "tool_use_id": "toolu_g",
            "content": "src/a.py:1:foo\nsrc/b.py:2:foo\n"}]
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", use, cwd="/proj"),
        user("s1", "u2", res, cwd="/proj"),
        assistant("s1", "u3", [_thinking("pattern search is confusing me")],
                  cwd="/proj"),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "temporal_proximity"
    # Grep's file_paths includes the scope dir + matched files; Tier 3
    # attributes to the entire list per schema 1.2 uniform multi-file.
    assert len(attr.file_paths) >= 2
    assert any(p.endswith("/proj/src/a.py") for p in attr.file_paths)
    assert any(p.endswith("/proj/src/b.py") for p in attr.file_paths)


def test_attribution_applies_to_agent_sourced_thinking(tmp_path):
    nested = [_read_use("t1", "/proj/storage.py"),
              _thinking("sub-agent reading storage.py")]
    jsonl(tmp_path / "s.jsonl", [progress("s1", "u1", nested, cwd="/proj")])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    blocks = corpus.sessions["s1"][0].blocks
    thinking_block = next(b for b in blocks if b.type == "thinking")
    assert thinking_block.agent_sourced is True
    assert thinking_block.attribution is not None
    # Bare "storage.py" resolves via Tier 2 (unique basename), not Tier 1.
    assert thinking_block.attribution.tier == "unique_basename"
    assert thinking_block.attribution.file_paths == ["/proj/storage.py"]
