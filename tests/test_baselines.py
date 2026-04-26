from __future__ import annotations

from pathlib import Path

from ai_friction_map.baselines import (
    LOW_CONFIDENCE_N,
    MIN_SESSION_BLOCKS,
    compute_corpus_baseline,
    compute_session_baselines,
    load_baseline_cache,
    median_mad,
    save_baseline_cache,
    z_score,
)
from ai_friction_map.events import (
    BaselineSet,
    BaselineStat,
    Block,
    Corpus,
    ParsedEvent,
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


def _mk_thinking_session(session_id: str, n_blocks: int) -> tuple[str, list[ParsedEvent]]:
    events = []
    for i in range(n_blocks):
        text = f"thinking block number {i}"
        events.append(_mk_event(
            [Block(type="thinking", thinking=text)],
            event_index=i,
        ))
    return session_id, events


def test_median_mad_simple():
    med, mad = median_mad([1.0, 2.0, 3.0, 4.0, 5.0])
    assert med == 3.0
    assert mad == 1.0


def test_median_mad_even_count():
    med, mad = median_mad([1.0, 2.0, 3.0, 4.0])
    assert med == 2.5
    # Deviations: 1.5, 0.5, 0.5, 1.5 → sorted [0.5, 0.5, 1.5, 1.5] → median 1.0
    assert mad == 1.0


def test_median_mad_empty():
    assert median_mad([]) == (0.0, 0.0)


def test_z_score_zero_when_mad_zero():
    stat = BaselineStat(median=5.0, mad=0.0, n=10, low_confidence=False)
    assert z_score(10.0, stat) == 0.0


def test_z_score_uses_1_4826_multiplier():
    stat = BaselineStat(median=0.0, mad=1.0, n=100, low_confidence=False)
    z = z_score(1.4826, stat)
    assert abs(z - 1.0) < 1e-9


def test_corpus_baseline_low_confidence_when_few_samples():
    corpus = Corpus()
    sid, events = _mk_thinking_session("s1", n_blocks=3)
    corpus.sessions[sid] = events
    baseline = compute_corpus_baseline(corpus)
    assert baseline.block_length_words.n == 3
    assert baseline.block_length_words.low_confidence is True


def test_corpus_baseline_not_low_confidence_at_threshold():
    corpus = Corpus()
    sid, events = _mk_thinking_session("s1", n_blocks=LOW_CONFIDENCE_N)
    corpus.sessions[sid] = events
    baseline = compute_corpus_baseline(corpus)
    assert baseline.block_length_words.n == LOW_CONFIDENCE_N
    assert baseline.block_length_words.low_confidence is False


def test_session_baselines_threshold_omits_below_min():
    corpus = Corpus()
    sid_a, events_a = _mk_thinking_session("s_small", n_blocks=MIN_SESSION_BLOCKS - 1)
    sid_b, events_b = _mk_thinking_session("s_big", n_blocks=MIN_SESSION_BLOCKS)
    corpus.sessions[sid_a] = events_a
    corpus.sessions[sid_b] = events_b
    sb = compute_session_baselines(corpus)
    assert "s_small" not in sb
    assert "s_big" in sb


def test_session_baselines_includes_at_threshold():
    corpus = Corpus()
    sid, events = _mk_thinking_session("s1", n_blocks=MIN_SESSION_BLOCKS)
    corpus.sessions[sid] = events
    sb = compute_session_baselines(corpus)
    assert sid in sb
    assert sb[sid].block_length_words.n == MIN_SESSION_BLOCKS


def test_baseline_cache_round_trip(tmp_path: Path):
    target = tmp_path / "baseline.json"
    bs = BaselineSet(
        block_length_words=BaselineStat(median=10.0, mad=2.0, n=50, low_confidence=False),
        question_rate_per_100w=BaselineStat(median=1.5, mad=0.5, n=50, low_confidence=False),
    )
    save_baseline_cache(bs, target)
    loaded = load_baseline_cache(target)
    assert loaded is not None
    assert loaded.block_length_words.median == 10.0
    assert loaded.block_length_words.mad == 2.0
    assert loaded.block_length_words.n == 50
    assert loaded.block_length_words.low_confidence is False
    assert loaded.question_rate_per_100w.median == 1.5


def test_baseline_cache_miss_returns_none(tmp_path: Path):
    assert load_baseline_cache(tmp_path / "does-not-exist.json") is None


def test_corpus_baseline_no_thinking_blocks():
    corpus = Corpus()
    corpus.sessions["s1"] = [_mk_event([Block(type="text", text="hi")])]
    baseline = compute_corpus_baseline(corpus)
    assert baseline.block_length_words.n == 0
    assert baseline.block_length_words.median == 0.0
    assert baseline.block_length_words.low_confidence is True
