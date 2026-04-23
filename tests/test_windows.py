from __future__ import annotations

from ai_friction_map.parser import parse_sessions
from ai_friction_map.windows import (
    get_boundary_clip_count,
    is_compact_boundary,
    reset_boundary_clip_count,
    window_events,
)
from tests._factories import (
    assistant,
    bare,
    jsonl,
    system_compact,
)


def _events_with_compact_at(tmp_path, boundary_indices: list[int], total: int):
    records = []
    for i in range(total):
        if i in boundary_indices:
            records.append(system_compact("s1", f"u{i}"))
        else:
            records.append(assistant("s1", f"u{i}", []))
    jsonl(tmp_path / "s.jsonl", records)
    corpus = parse_sessions(tmp_path)
    return corpus.sessions["s1"]


def test_subtype_populated_for_system_event(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u0", []),
        system_compact("s1", "u1"),
        assistant("s1", "u2", []),
    ])
    corpus = parse_sessions(tmp_path)
    events = corpus.sessions["s1"]
    assert events[1].type == "system"
    assert events[1].subtype == "compact_boundary"
    assert is_compact_boundary(events[1])


def test_subtype_none_for_other_events(tmp_path):
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u0", [])])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.subtype is None
    assert not is_compact_boundary(event)


def test_window_events_bounded_by_corpus_edges(tmp_path):
    events = _events_with_compact_at(tmp_path, [], total=5)
    lo, hi = window_events(events, center_idx=1, n=5)
    assert (lo, hi) == (0, 4)


def test_window_events_stops_at_compact_boundary_before(tmp_path):
    # Boundary at index 8; center at 10; n=5 should only reach lo=9.
    events = _events_with_compact_at(tmp_path, [8], total=16)
    lo, hi = window_events(events, center_idx=10, n=5)
    assert lo == 9
    assert hi == 15


def test_window_events_stops_at_compact_boundary_after(tmp_path):
    # Boundary at index 12; center at 10; n=5 should only reach hi=11.
    events = _events_with_compact_at(tmp_path, [12], total=20)
    lo, hi = window_events(events, center_idx=10, n=5)
    assert lo == 5
    assert hi == 11


def test_window_events_no_boundaries(tmp_path):
    events = _events_with_compact_at(tmp_path, [], total=20)
    lo, hi = window_events(events, center_idx=10, n=3)
    assert (lo, hi) == (7, 13)


def test_window_events_increments_clip_counter(tmp_path):
    reset_boundary_clip_count()
    events = _events_with_compact_at(tmp_path, [8, 12], total=20)
    window_events(events, center_idx=10, n=5)
    # Clipped on both sides.
    assert get_boundary_clip_count() == 2


def test_window_events_no_clip_at_corpus_edge(tmp_path):
    reset_boundary_clip_count()
    events = _events_with_compact_at(tmp_path, [], total=5)
    window_events(events, center_idx=1, n=5)
    # Hit corpus edge, not a boundary; counter stays 0.
    assert get_boundary_clip_count() == 0
