from __future__ import annotations

from frictionmap.events import Attribution, Block, Corpus, ParsedEvent
from frictionmap.scoring import (
    compute_block_signals,
    compute_edit_churn,
    compute_reasoning_to_output_ratio,
    compute_reread_bursts,
)


def _mk_event(blocks: list[Block], event_index: int = 0, type_: str = "assistant") -> ParsedEvent:
    return ParsedEvent(
        session_id="s1",
        event_index=event_index,
        type=type_,
        timestamp="t",
        cwd="/proj",
        uuid=f"u{event_index}",
        parent_uuid=None,
        blocks=blocks,
    )


def _mk_thinking(text: str) -> Block:
    return Block(type="thinking", thinking=text)


def _mk_tool_use(name: str = "Read") -> Block:
    return Block(type="tool_use", tool_name=name, tool_use_id="x")


def test_question_rate_two_words_two_questions():
    text = "what? why?"
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    assert sig.question_rate_per_100w == 100.0
    assert sig.length_words == 2


def test_question_rate_inside_code_fence_does_not_count():
    text = "plain text\n```\ncode line with ?\n```\nmore text"
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    assert sig.question_rate_per_100w == 0.0


def test_length_chars_uses_stripped_text():
    text = "hello\n```\n" + ("X" * 1000) + "\n```\nworld"
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    # Stripped chars must be far smaller than the raw 1000-char fence.
    assert sig.length_chars < 100
    assert sig.length_words == 2  # "hello" and "world"


def test_markers_per_100w_uses_stripped_denominator():
    text = "wait there"  # 2 words, 1 marker
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    assert sig.marker_count == 1
    assert sig.markers_per_100w == 50.0  # 1 / 2 * 100


def test_marker_inside_fence_not_counted():
    text = "hello\n```\nwait inside fence\n```\nworld"
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    assert sig.marker_count == 0


def test_tool_use_coupling_same_event():
    # Thinking block and tool_use share an assistant event → coupled.
    blocks = [_mk_thinking("wait"), _mk_tool_use("Read")]
    events = [_mk_event(blocks, event_index=0)]
    sig = compute_block_signals("wait", 0, events)
    assert sig.tool_use_coupling is True


def test_tool_use_coupling_within_window():
    # Tool_use 2 events away → coupled with default window of 3.
    events = [
        _mk_event([_mk_thinking("wait")], event_index=0),
        _mk_event([Block(type="text", text="commentary")], event_index=1, type_="assistant"),
        _mk_event([_mk_tool_use("Edit")], event_index=2),
    ]
    sig = compute_block_signals("wait", 0, events)
    assert sig.tool_use_coupling is True


def test_tool_use_coupling_outside_window():
    # Tool_use 5 events away, window is 3 → not coupled.
    events = [
        _mk_event([_mk_thinking("wait")], event_index=0),
        _mk_event([Block(type="text", text="x")], event_index=1, type_="assistant"),
        _mk_event([Block(type="text", text="y")], event_index=2, type_="assistant"),
        _mk_event([Block(type="text", text="z")], event_index=3, type_="assistant"),
        _mk_event([Block(type="text", text="w")], event_index=4, type_="assistant"),
        _mk_event([_mk_tool_use("Edit")], event_index=5),
    ]
    sig = compute_block_signals("wait", 0, events)
    assert sig.tool_use_coupling is False


def test_tool_use_coupling_no_tools_at_all():
    events = [
        _mk_event([_mk_thinking("wait")], event_index=0),
        _mk_event([Block(type="text", text="just text")], event_index=1, type_="assistant"),
    ]
    sig = compute_block_signals("wait", 0, events)
    assert sig.tool_use_coupling is False


def test_tool_use_coupling_respects_compact_boundary():
    # Boundary between thinking and tool_use clips the window.
    boundary = ParsedEvent(
        session_id="s1",
        event_index=1,
        type="system",
        timestamp="t",
        cwd="/proj",
        uuid="u1",
        parent_uuid=None,
        blocks=[],
        subtype="compact_boundary",
    )
    events = [
        _mk_event([_mk_thinking("wait")], event_index=0),
        boundary,
        _mk_event([_mk_tool_use("Read")], event_index=2),
    ]
    sig = compute_block_signals("wait", 0, events)
    assert sig.tool_use_coupling is False


def test_zero_words_does_not_divide_by_zero():
    # Pathological: all-fenced text → stripped is empty.
    text = "```\nfenced only\n```"
    events = [_mk_event([_mk_thinking(text)])]
    sig = compute_block_signals(text, 0, events)
    assert sig.length_words == 0
    assert sig.question_rate_per_100w == 0.0
    assert sig.markers_per_100w == 0.0


def _mk_read(path: str) -> Block:
    return Block(
        type="tool_use",
        tool_name="Read",
        tool_use_id="r",
        file_paths=[path],
    )


def _mk_edit(path: str) -> Block:
    return Block(
        type="tool_use",
        tool_name="Edit",
        tool_use_id="e",
        file_paths=[path],
    )


def _mk_filler() -> Block:
    return Block(type="text", text="filler")


def _mk_corpus(events: list[ParsedEvent]) -> Corpus:
    corpus = Corpus()
    corpus.sessions["s1"] = events
    return corpus


def test_reread_bursts_two_in_window_one_outside():
    # Reads of /proj/a.py at indices 5, 7, 20 with window=5.
    # 5 and 7 are in each other's window → both bursts. 20 is alone.
    events = [_mk_event([_mk_filler()], event_index=i) for i in range(25)]
    events[5] = _mk_event([_mk_read("/proj/a.py")], event_index=5)
    events[7] = _mk_event([_mk_read("/proj/a.py")], event_index=7)
    events[20] = _mk_event([_mk_read("/proj/a.py")], event_index=20)
    counts = compute_reread_bursts(_mk_corpus(events))
    assert counts == {"/proj/a.py": 2}


def test_reread_bursts_zero_when_no_reads():
    events = [_mk_event([_mk_filler()], event_index=i) for i in range(5)]
    assert compute_reread_bursts(_mk_corpus(events)) == {}


def test_reread_bursts_respects_compact_boundary():
    # Read at 0, boundary at 1, Read at 2 with window=5 → boundary clips
    # the window so neither read sees the other.
    events = [
        _mk_event([_mk_read("/proj/a.py")], event_index=0),
        ParsedEvent(
            session_id="s1", event_index=1, type="system", timestamp="t",
            cwd="/proj", uuid="u1", parent_uuid=None, blocks=[],
            subtype="compact_boundary",
        ),
        _mk_event([_mk_read("/proj/a.py")], event_index=2),
    ]
    counts = compute_reread_bursts(_mk_corpus(events))
    assert counts == {}


def test_edit_churn_basic():
    events = [_mk_event([_mk_filler()], event_index=i) for i in range(10)]
    events[2] = _mk_event([_mk_edit("/proj/a.py")], event_index=2)
    events[3] = _mk_event([_mk_edit("/proj/a.py")], event_index=3)
    counts = compute_edit_churn(_mk_corpus(events))
    assert counts == {"/proj/a.py": 2}


def test_reasoning_to_output_per_file_same_turn_rule():
    # Turn 1: thinking 100 chars (attributed to /proj/F.py), text 50 chars.
    # Turn 2: thinking 200 chars (attributed to /proj/G.py), text 400 chars.
    # F's denominator must NOT include turn 2's 400 chars of text.
    attr_f = Attribution(
        tier="exact_path", confidence="high", file_paths=["/proj/F.py"],
    )
    attr_g = Attribution(
        tier="exact_path", confidence="high", file_paths=["/proj/G.py"],
    )
    thinking_f = Block(type="thinking", thinking="x" * 100, attribution=attr_f)
    text_t1 = Block(type="text", text="y" * 50)
    thinking_g = Block(type="thinking", thinking="x" * 200, attribution=attr_g)
    text_t2 = Block(type="text", text="y" * 400)
    events = [
        _mk_event([thinking_f, text_t1], event_index=0),
        _mk_event([thinking_g, text_t2], event_index=1),
    ]
    ratios = compute_reasoning_to_output_ratio(_mk_corpus(events))
    assert ratios["/proj/F.py"] == 100 / 50
    assert ratios["/proj/G.py"] == 200 / 400


def test_reasoning_to_output_text_counted_once_per_turn_per_file():
    # Two F-attributed thinking blocks in one turn + one text block.
    # F gets thinking sum (300) and text counted once (60).
    attr_f = Attribution(
        tier="exact_path", confidence="high", file_paths=["/proj/F.py"],
    )
    blocks = [
        Block(type="thinking", thinking="x" * 100, attribution=attr_f),
        Block(type="thinking", thinking="x" * 200, attribution=attr_f),
        Block(type="text", text="y" * 60),
    ]
    events = [_mk_event(blocks, event_index=0)]
    ratios = compute_reasoning_to_output_ratio(_mk_corpus(events))
    assert ratios["/proj/F.py"] == 300 / 60


def test_reasoning_to_output_cap_when_output_tiny():
    # No output at all → cap kicks in.
    attr = Attribution(
        tier="exact_path", confidence="high", file_paths=["/proj/F.py"],
    )
    events = [
        _mk_event(
            [Block(type="thinking", thinking="x" * 9999, attribution=attr)],
            event_index=0,
        ),
    ]
    ratios = compute_reasoning_to_output_ratio(_mk_corpus(events))
    assert ratios["/proj/F.py"] == 100.0  # REASONING_TO_OUTPUT_CAP


def test_reasoning_to_output_ratio_parked_at_zero_weight():
    """Parked pending per-file definition rework.

    Cap saturation on the canonical attune corpus showed the signal
    flooding score_pre_normalization with a uniform contribution. The
    signal still computes and emits in ScoreComponents (so revisiting
    is just a weight bump), but contributes nothing to the score.
    """
    from frictionmap.events import BaselineSet, BaselineStat, LeakageCounts
    from frictionmap.scoring import (
        WEIGHTS,
        REASONING_TO_OUTPUT_CAP,
        _BlockAgg,
        score_file,
    )

    assert WEIGHTS["reasoning_to_output_ratio"] == 0.0

    # Construct a baseline that would yield a large z-score on the
    # saturated raw value, plus a non-trivial MAD so z is computable.
    baseline = BaselineSet(
        reasoning_to_output_ratio=BaselineStat(
            median=1.0, mad=1.0, n=100, low_confidence=False,
        ),
    )
    result = score_file(
        path="/proj/x.py",
        block_agg=_BlockAgg(),
        reread_count=0,
        edit_churn_count=0,
        reasoning_to_output=REASONING_TO_OUTPUT_CAP,  # would saturate
        leakage=LeakageCounts(),
        baseline=baseline,
    )
    # Raw and z are populated; weight and contribution are zero.
    assert result.components.reasoning_to_output_ratio.raw == REASONING_TO_OUTPUT_CAP
    assert result.components.reasoning_to_output_ratio.z_score != 0.0
    assert result.components.reasoning_to_output_ratio.weight == 0.0
    assert result.components.reasoning_to_output_ratio.contribution == 0.0
    # No other signals → score_pre is exactly zero.
    assert result.score_pre_normalization == 0.0


def test_leakage_signals_parked_at_weight_zero():
    """Phase 5 #2b: leakage signals are parked; weight=0 each."""
    from frictionmap.scoring import WEIGHTS

    assert WEIGHTS["edit_failures"] == 0.0
    assert WEIGHTS["grep_reformulations"] == 0.0
    assert WEIGHTS["bash_retries"] == 0.0
    assert WEIGHTS["read_after_edit"] == 0.0


def test_leakage_only_corpus_produces_zero_score():
    """A file with only leakage signals — populated raw counts and a
    baseline that would yield a large z-score — produces score=0.0
    after parking. Pins the parking; catches accidental un-parking."""
    from frictionmap.events import BaselineSet, BaselineStat, LeakageCounts
    from frictionmap.scoring import _BlockAgg, score_file

    baseline = BaselineSet(
        leakage_events_per_session=BaselineStat(
            median=0.0, mad=1.0, n=100, low_confidence=False,
        ),
    )
    result = score_file(
        path="/proj/x.py",
        block_agg=_BlockAgg(),
        reread_count=0,
        edit_churn_count=0,
        reasoning_to_output=0.0,
        leakage=LeakageCounts(
            edit_failures=5,
            grep_reformulations=5,
            bash_retries=5,
            read_after_edit=5,
        ),
        baseline=baseline,
    )
    assert result.components.edit_failures.weight == 0.0
    assert result.components.edit_failures.contribution == 0.0
    assert result.components.grep_reformulations.weight == 0.0
    assert result.components.grep_reformulations.contribution == 0.0
    assert result.components.bash_retries.weight == 0.0
    assert result.components.bash_retries.contribution == 0.0
    assert result.components.read_after_edit.weight == 0.0
    assert result.components.read_after_edit.contribution == 0.0
    assert result.score_pre_normalization == 0.0


def test_question_rate_parked_at_weight_zero():
    """Phase 5 #3: question_rate_per_100w is parked; weight=0."""
    from frictionmap.scoring import WEIGHTS

    assert WEIGHTS["question_rate_per_100w"] == 0.0


def test_question_rate_only_corpus_produces_zero_score():
    """A file with only a positive question_rate — populated weighted
    raw value and a baseline that would yield a large z-score —
    produces score=0.0 after parking. Pins the parking; catches
    accidental un-parking via weight-tuning regression."""
    from frictionmap.events import BaselineSet, BaselineStat, LeakageCounts
    from frictionmap.scoring import _BlockAgg, score_file

    baseline = BaselineSet(
        question_rate_per_100w=BaselineStat(
            median=0.0, mad=1.0, n=100, low_confidence=False,
        ),
    )
    block_agg = _BlockAgg(
        dilution_weight_sum=1.0,
        weighted_question_rate=10.0,
    )
    result = score_file(
        path="/proj/x.py",
        block_agg=block_agg,
        reread_count=0,
        edit_churn_count=0,
        reasoning_to_output=0.0,
        leakage=LeakageCounts(),
        baseline=baseline,
    )
    assert result.components.question_rate_per_100w.raw == 10.0
    assert result.components.question_rate_per_100w.z_score != 0.0
    assert result.components.question_rate_per_100w.weight == 0.0
    assert result.components.question_rate_per_100w.contribution == 0.0
    assert result.score_pre_normalization == 0.0


# ---------------------------------------------------------------------
# Schema 1.3: file-level marker scoring uses presence × intensity.
# ---------------------------------------------------------------------


def _mk_corpus_for_scoring(events: list[ParsedEvent]) -> Corpus:
    c = Corpus()
    c.sessions["s1"] = events
    return c


def _attr(*paths: str) -> Attribution:
    return Attribution(
        tier="exact_path", confidence="high", file_paths=list(paths),
    )


def test_marker_contribution_zero_when_no_attributed_blocks():
    from frictionmap.events import BaselineSet, LeakageCounts
    from frictionmap.scoring import WEIGHTS, _BlockAgg, score_file

    result = score_file(
        path="/proj/x.py",
        block_agg=_BlockAgg(),
        reread_count=0,
        edit_churn_count=0,
        reasoning_to_output=0.0,
        leakage=LeakageCounts(),
        baseline=BaselineSet(),
    )
    assert result.components.markers.raw == 0.0
    assert result.components.markers.contribution == 0.0
    # Weight is still emitted so downstream introspection sees the signal.
    assert result.components.markers.weight == WEIGHTS["markers"]


def test_marker_contribution_zero_when_no_positive_blocks():
    from frictionmap.events import BaselineSet
    from frictionmap.scoring import _aggregate_block_signals, score_corpus

    # Three thinking blocks attributed to /proj/x.py, none containing
    # any marker → presence_rate = 0 → contribution = 0.
    blocks = [
        _mk_event(
            [Block(type="thinking", thinking="ordinary text", attribution=_attr("/proj/x.py"))],
            event_index=i,
        )
        for i in range(3)
    ]
    corpus = _mk_corpus_for_scoring(blocks)
    aggs = _aggregate_block_signals(corpus)
    agg = aggs["/proj/x.py"]
    assert agg.dilution_weight_sum == 3.0
    assert agg.positive_block_weight_sum == 0.0
    results = score_corpus(corpus, BaselineSet())
    assert results["/proj/x.py"].components.markers.raw == 0.0
    assert results["/proj/x.py"].components.markers.contribution == 0.0


def test_marker_contribution_when_every_attributed_block_has_markers():
    """Presence rate = 1.0; raw equals mean intensity over positive blocks."""
    from frictionmap.events import BaselineSet
    from frictionmap.scoring import WEIGHTS, score_corpus

    # Each block is "wait" (1 marker, 1 word) → markers_per_100w = 100.
    events = [
        _mk_event(
            [Block(type="thinking", thinking="wait", attribution=_attr("/proj/x.py"))],
            event_index=i,
        )
        for i in range(3)
    ]
    corpus = _mk_corpus_for_scoring(events)
    results = score_corpus(corpus, BaselineSet())
    sig = results["/proj/x.py"].components.markers
    # presence_rate = 1.0, mean_intensity = 100.0 → raw = 100.0.
    assert abs(sig.raw - 100.0) < 1e-9
    assert abs(sig.contribution - 100.0 * WEIGHTS["markers"]) < 1e-9
    # z_score is unused on the presence/intensity path.
    assert sig.z_score == 0.0


def test_marker_contribution_partial_presence():
    """4 blocks attributed; 1 has markers (rate 100), 3 do not.
    presence_rate = 0.25, mean_intensity = 100 → raw = 25.0."""
    from frictionmap.events import BaselineSet
    from frictionmap.scoring import score_corpus

    events = [
        _mk_event(
            [Block(type="thinking", thinking="wait", attribution=_attr("/proj/x.py"))],
            event_index=0,
        ),
        _mk_event(
            [Block(type="thinking", thinking="ordinary one", attribution=_attr("/proj/x.py"))],
            event_index=1,
        ),
        _mk_event(
            [Block(type="thinking", thinking="ordinary two", attribution=_attr("/proj/x.py"))],
            event_index=2,
        ),
        _mk_event(
            [Block(type="thinking", thinking="ordinary three", attribution=_attr("/proj/x.py"))],
            event_index=3,
        ),
    ]
    corpus = _mk_corpus_for_scoring(events)
    results = score_corpus(corpus, BaselineSet())
    sig = results["/proj/x.py"].components.markers
    assert abs(sig.raw - 25.0) < 1e-9


def test_marker_contribution_multi_file_dilution():
    """A single thinking block attributed to two files distributes its
    presence × intensity contribution as 0.5 each, not full weight per
    file. Both files should compute the same raw under symmetric input.
    """
    from frictionmap.events import BaselineSet
    from frictionmap.scoring import _aggregate_block_signals, score_corpus

    block = Block(
        type="thinking", thinking="wait", attribution=_attr("/proj/a.py", "/proj/b.py"),
    )
    events = [_mk_event([block], event_index=0)]
    corpus = _mk_corpus_for_scoring(events)
    aggs = _aggregate_block_signals(corpus)
    for path in ("/proj/a.py", "/proj/b.py"):
        agg = aggs[path]
        assert abs(agg.dilution_weight_sum - 0.5) < 1e-9
        assert abs(agg.positive_block_weight_sum - 0.5) < 1e-9
        # weighted_intensity_positive_sum = rate * share = 100.0 * 0.5
        assert abs(agg.weighted_intensity_positive_sum - 50.0) < 1e-9

    results = score_corpus(corpus, BaselineSet())
    sig_a = results["/proj/a.py"].components.markers
    sig_b = results["/proj/b.py"].components.markers
    # presence = 0.5/0.5 = 1.0; intensity = 50/0.5 = 100; raw = 100.
    assert abs(sig_a.raw - 100.0) < 1e-9
    assert abs(sig_b.raw - 100.0) < 1e-9
