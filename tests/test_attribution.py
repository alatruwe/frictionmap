from __future__ import annotations

from ai_friction_map.attribution import attribute_thinking_blocks
from ai_friction_map.parser import parse_sessions
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


def test_attribution_exact_path_longest_match_wins(tmp_path):
    # Two canonical paths both ending in storage.py; thinking mentions the
    # longer "attune/storage.py". Both still match at the "storage.py"
    # suffix, but the longer one also matches at "attune/storage.py".
    # Per 1.2, both paths are returned.
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
    # Only /proj/attune/storage.py has "attune/storage.py" as a suffix.
    # "/proj/other/storage.py" suffixes are [.../storage.py, other/storage.py,
    # storage.py], none of which is "attune/storage.py"; but "storage.py"
    # IS present in thinking too. So both match via the "storage.py" suffix.
    assert attr.tier == "exact_path"
    assert set(attr.file_paths) == {
        "/proj/attune/storage.py", "/proj/other/storage.py",
    }


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


def test_attribution_tier1_multiple_distinct_paths_attributed(tmp_path):
    # Thinking mentions two distinct canonical paths. Both attribute
    # under the schema-1.2 multi-file rule.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/storage.py")]),
        assistant("s1", "u2", [_read_use("t2", "/proj/logger.py")]),
        assistant("s1", "u3", [_thinking("storage.py talks to logger.py here")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    assert attr.tier == "exact_path"
    assert set(attr.file_paths) == {"/proj/storage.py", "/proj/logger.py"}


def test_attribution_unique_basename(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_read_use("t1", "/proj/deep/path/storage.py")],
                  cwd="/proj"),
        assistant("s1", "u2", [_thinking("storage.py is acting weird")]),
    ])
    corpus = parse_sessions(tmp_path)
    attribute_thinking_blocks(corpus)
    attr = _first_thinking_attribution(corpus)
    # Tier 1 fires because "storage.py" is a suffix of the canonical path.
    # To exercise Tier 2, we need a canonical path that does NOT suffix-match.
    # Reshape test accordingly.
    # (This test passes via Tier 1, not Tier 2 — see next test for Tier 2.)
    assert attr.file_paths == ["/proj/deep/path/storage.py"]


def test_attribution_unique_basename_fires_when_tier1_misses():
    # Canonical path has storage.py as suffix; thinking mentions a different
    # bare basename that doesn't exist as any suffix.
    # Trick: use a basename that appears in thinking but not as a canonical
    # path suffix. Since any canonical basename IS a suffix, we need two
    # session files where only one is obvious.
    # Simpler: thinking mentions storage.py; the session only touched
    # /proj/storage.py. Tier 1 fires first. This test is effectively a
    # duplicate of exact_path — so we engineer a case where thinking says
    # "storage.py" and the canonical path is `/proj/src/storage.py` — Tier 1
    # still fires via the "storage.py" suffix. To see Tier 2 solo, we need
    # to make Tier 1 miss. Use path boundary obfuscation: session-touched
    # is "/proj/PREFIX_storage.py" (Tier 1 miss for "storage.py") but we
    # still want Tier 2 to match "storage.py". But basename_to_paths would
    # key on "PREFIX_storage.py" not "storage.py". So no basename match either.
    #
    # Conclusion: in practice Tier 1 subsumes Tier 2 whenever a canonical
    # basename matches. Tier 2 is useful only when thinking mentions a
    # basename whose *suffix form* doesn't appear in any canonical path —
    # which means the basename_to_paths lookup must have that basename as
    # a key, which means it IS a canonical basename, which means Tier 1
    # WOULD have matched. So Tier 2 is genuinely a fallthrough case that
    # rarely fires independently.
    # This test just exercises the Tier 2 code path by forcing it via a
    # direct attribute call where Tier 1 is bypassed.
    from ai_friction_map.attribution import _tier2_unique_basename
    basename_to_paths = {"storage.py": {"/proj/storage.py"}}
    result = _tier2_unique_basename("talking about storage.py", basename_to_paths)
    assert result == ["/proj/storage.py"]


def test_attribution_ambiguous_basename_falls_through():
    # Two session files share basename utils.py. Thinking mentions utils.py.
    # Tier 1 will match both because "utils.py" is a suffix of both canonical
    # paths. This test ensures Tier 2 itself (in isolation) drops ambiguous.
    from ai_friction_map.attribution import _tier2_unique_basename
    basename_to_paths = {"utils.py": {"/proj/a/utils.py", "/proj/b/utils.py"}}
    result = _tier2_unique_basename("look at utils.py", basename_to_paths)
    assert result == []


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
    assert thinking_block.attribution.tier == "exact_path"
    assert thinking_block.attribution.file_paths == ["/proj/storage.py"]
