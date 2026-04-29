from __future__ import annotations

import json
from pathlib import Path

from frictionmap.baselines import (
    LOW_CONFIDENCE_N,
    MIN_SESSION_BLOCKS,
    _presence_intensity_stat,
    compute_corpus_baseline,
    compute_session_baselines,
    load_baseline_cache,
    median_mad,
    save_baseline_cache,
    z_score,
)
from frictionmap.events import (
    BaselineSet,
    BaselineStat,
    Block,
    Corpus,
    ParsedEvent,
    PresenceIntensityBaselineStat,
    RobustZBaselineStat,
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


def test_presence_intensity_stat_basic():
    # 10 values; 4 positive (1.0, 2.0, 3.0, 5.0) → median 2.5
    values = [0.0, 0.0, 1.0, 0.0, 2.0, 0.0, 3.0, 0.0, 0.0, 5.0]
    stat = _presence_intensity_stat(values)
    assert isinstance(stat, PresenceIntensityBaselineStat)
    assert stat.kind == "presence_intensity"
    assert stat.n_blocks == 10
    assert stat.n_positive_blocks == 4
    assert abs(stat.presence_rate_corpus - 0.4) < 1e-9
    assert abs(stat.median_intensity_among_positives - 2.5) < 1e-9
    assert stat.low_confidence is True  # n_positive < 20


def test_presence_intensity_stat_empty():
    stat = _presence_intensity_stat([])
    assert stat.n_blocks == 0
    assert stat.n_positive_blocks == 0
    assert stat.presence_rate_corpus == 0.0
    assert stat.median_intensity_among_positives == 0.0
    assert stat.low_confidence is True


def test_presence_intensity_stat_all_zero():
    stat = _presence_intensity_stat([0.0] * 50)
    assert stat.n_blocks == 50
    assert stat.n_positive_blocks == 0
    assert stat.presence_rate_corpus == 0.0
    assert stat.median_intensity_among_positives == 0.0
    assert stat.low_confidence is True


def test_corpus_markers_baseline_uses_presence_intensity_branch():
    corpus = Corpus()
    sid, events = _mk_thinking_session("s1", n_blocks=3)
    corpus.sessions[sid] = events
    baseline = compute_corpus_baseline(corpus)
    assert isinstance(baseline.markers_per_100w, PresenceIntensityBaselineStat)
    assert baseline.markers_per_100w.kind == "presence_intensity"
    # Other signals stay on robust_z.
    assert isinstance(baseline.block_length_words, RobustZBaselineStat)
    assert baseline.block_length_words.kind == "robust_z"


def test_baseline_cache_round_trip_with_presence_intensity_markers(tmp_path: Path):
    target = tmp_path / "baseline.json"
    bs = BaselineSet(
        block_length_words=RobustZBaselineStat(
            median=10.0, mad=2.0, n=50, low_confidence=False
        ),
        markers_per_100w=PresenceIntensityBaselineStat(
            presence_rate_corpus=0.34,
            median_intensity_among_positives=1.1,
            n_blocks=600,
            n_positive_blocks=204,
            low_confidence=False,
        ),
    )
    save_baseline_cache(bs, target)
    loaded = load_baseline_cache(target)
    assert loaded is not None
    mk = loaded.markers_per_100w
    assert isinstance(mk, PresenceIntensityBaselineStat)
    assert mk.kind == "presence_intensity"
    assert abs(mk.presence_rate_corpus - 0.34) < 1e-9
    assert abs(mk.median_intensity_among_positives - 1.1) < 1e-9
    assert mk.n_blocks == 600
    assert mk.n_positive_blocks == 204


def test_baseline_cache_legacy_shape_invalidates(tmp_path: Path):
    """Schema 1.2 caches (markers stored as robust-z, no `kind` field)
    must invalidate on load so the next run regenerates under 1.3."""
    target = tmp_path / "baseline.json"
    legacy = {
        "block_length_words": {
            "median": 10.0, "mad": 2.0, "n": 50, "low_confidence": False
        },
        "markers_per_100w": {
            "median": 1.2, "mad": 0.9, "n": 487, "low_confidence": False
        },
    }
    target.write_text(json.dumps(legacy))
    assert load_baseline_cache(target) is None
