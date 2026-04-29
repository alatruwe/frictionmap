"""Phase 3 — robust baselines (median + MAD) and on-disk cache.

Six signals get a `BaselineStat` (median, MAD, n, low_confidence). Per-block
signals are sampled across every thinking block; per-session signals are
sampled once per session. Sessions with fewer than `MIN_SESSION_BLOCKS`
thinking blocks are omitted from session_baselines — consumers fall back
to the corpus baseline on key absence.

Z-scores use the `1.4826 * MAD` standard-deviation analog. The multiplier
is applied at consumption time so the stored MAD remains raw.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from frictionmap.events import (
    BaselineSet,
    BaselineStat,
    Corpus,
    ParsedEvent,
    PresenceIntensityBaselineStat,
    RobustZBaselineStat,
)
from frictionmap.leakage import count_session_leakage_events
from frictionmap.scoring import (
    compute_block_signals,
    compute_edit_churn,
    compute_reread_bursts,
)

MIN_SESSION_BLOCKS = 20
LOW_CONFIDENCE_N = 20

CACHE_PATH = Path("~/.cache/frictionmap/baseline.json").expanduser()


def _median(sorted_values: list[float]) -> float:
    n = len(sorted_values)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_values[mid])
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def median_mad(values: list[float]) -> tuple[float, float]:
    """Return (median, MAD) for a list of samples. Empty list → (0, 0)."""
    if not values:
        return 0.0, 0.0
    s = sorted(values)
    med = _median(s)
    deviations = sorted(abs(v - med) for v in values)
    mad = _median(deviations)
    return med, mad


def _stat(values: list[float]) -> BaselineStat:
    med, mad = median_mad(values)
    n = len(values)
    return BaselineStat(median=med, mad=mad, n=n, low_confidence=(n < LOW_CONFIDENCE_N))


def _presence_intensity_stat(values: list[float]) -> PresenceIntensityBaselineStat:
    """Schema 1.3 — markers_per_100w branch.

    `presence_rate_corpus` and `median_intensity_among_positives` are
    corpus-level context numbers (for a future evidence panel). They are
    NOT divisors for the per-file score; the file-level scorer computes
    presence × intensity directly from attributed blocks.
    """
    n_blocks = len(values)
    positives = [v for v in values if v > 0]
    n_positive = len(positives)
    presence = n_positive / n_blocks if n_blocks > 0 else 0.0
    median_intensity = _median(sorted(positives)) if positives else 0.0
    return PresenceIntensityBaselineStat(
        presence_rate_corpus=presence,
        median_intensity_among_positives=median_intensity,
        n_blocks=n_blocks,
        n_positive_blocks=n_positive,
        low_confidence=(n_positive < LOW_CONFIDENCE_N),
    )


def _per_block_samples(
    events: list[ParsedEvent],
) -> tuple[list[float], list[float], list[float], list[bool]]:
    """Per thinking block: (length_words, question_rate, markers_per_100w,
    tool_use_coupling). Returns four parallel lists. tool_use_coupling is
    a list of bools (used to compute the per-session rate).
    """
    lw: list[float] = []
    qr: list[float] = []
    mp: list[float] = []
    tc: list[bool] = []
    for event_idx, event in enumerate(events):
        for block in event.blocks:
            if block.type != "thinking" or not block.thinking:
                continue
            sig = compute_block_signals(block.thinking, event_idx, events)
            lw.append(float(sig.length_words))
            qr.append(sig.question_rate_per_100w)
            mp.append(sig.markers_per_100w)
            tc.append(sig.tool_use_coupling)
    return lw, qr, mp, tc


def _per_session_reasoning_to_output(events: list[ParsedEvent]) -> float:
    r_total = 0
    o_total = 0
    for event in events:
        if event.type != "assistant":
            continue
        for block in event.blocks:
            if block.type == "thinking" and block.thinking:
                r_total += len(block.thinking)
            elif block.type == "text" and block.text:
                o_total += len(block.text)
    return r_total / max(o_total, 1)


def compute_corpus_baseline(corpus: Corpus) -> BaselineSet:
    lw_all: list[float] = []
    qr_all: list[float] = []
    mp_all: list[float] = []
    ro_all: list[float] = []
    tc_rate_all: list[float] = []
    leak_all: list[float] = []

    for events in corpus.sessions.values():
        lw, qr, mp, tc = _per_block_samples(events)
        lw_all.extend(lw)
        qr_all.extend(qr)
        mp_all.extend(mp)
        if tc:
            tc_rate_all.append(sum(1 for x in tc if x) / len(tc))
        ro_all.append(_per_session_reasoning_to_output(events))
        leak_all.append(float(count_session_leakage_events(events, corpus)))

    reread_samples = [float(v) for v in compute_reread_bursts(corpus).values()]
    edit_churn_samples = [float(v) for v in compute_edit_churn(corpus).values()]

    return BaselineSet(
        block_length_words=_stat(lw_all),
        question_rate_per_100w=_stat(qr_all),
        markers_per_100w=_presence_intensity_stat(mp_all),
        reasoning_to_output_ratio=_stat(ro_all),
        tool_use_coupling_rate=_stat(tc_rate_all),
        leakage_events_per_session=_stat(leak_all),
        reread_bursts_per_file=_stat(reread_samples),
        edit_churn_per_file=_stat(edit_churn_samples),
    )


def compute_session_baselines(corpus: Corpus) -> dict[str, BaselineSet]:
    """One BaselineSet per session with ≥ MIN_SESSION_BLOCKS thinking
    blocks. Sessions below the threshold are omitted entirely — consumers
    fall back to the corpus baseline on key absence.

    Per-session signals (reasoning_to_output, tool_use_coupling_rate,
    leakage) collapse to a single sample at the session level; their
    stats reflect that single value with `low_confidence=True`.
    """
    out: dict[str, BaselineSet] = {}
    # Per-session per-file behavioral baselines: scope a temporary
    # single-session Corpus to reuse the corpus-level helpers.
    for session_id, events in corpus.sessions.items():
        lw, qr, mp, tc = _per_block_samples(events)
        if len(lw) < MIN_SESSION_BLOCKS:
            continue
        ro = _per_session_reasoning_to_output(events)
        tc_rate = sum(1 for x in tc if x) / len(tc) if tc else 0.0
        leak = float(count_session_leakage_events(events, corpus))
        single_session = Corpus()
        single_session.sessions[session_id] = events
        single_session.tool_calls = corpus.tool_calls
        reread_samples = [
            float(v) for v in compute_reread_bursts(single_session).values()
        ]
        edit_churn_samples = [
            float(v) for v in compute_edit_churn(single_session).values()
        ]
        # Note: at session scope, n_positive_blocks < LOW_CONFIDENCE_N
        # frequently fires even when n_blocks ≥ MIN_SESSION_BLOCKS — the
        # markers signal is sparse-positive, so most session-level marker
        # baselines flag low_confidence=True. That is the correct
        # semantics; fall back to the corpus baseline for confidence.
        out[session_id] = BaselineSet(
            block_length_words=_stat(lw),
            question_rate_per_100w=_stat(qr),
            markers_per_100w=_presence_intensity_stat(mp),
            reasoning_to_output_ratio=_stat([ro]),
            tool_use_coupling_rate=_stat([tc_rate]),
            leakage_events_per_session=_stat([leak]),
            reread_bursts_per_file=_stat(reread_samples),
            edit_churn_per_file=_stat(edit_churn_samples),
        )
    return out


def z_score(raw: float, stat: BaselineStat) -> float:
    """Robust z-score using `1.4826 * MAD` as the SD analog."""
    if stat.mad <= 0:
        return 0.0
    return (raw - stat.median) / (1.4826 * stat.mad)


def save_baseline_cache(baseline_set: BaselineSet, path: Path | None = None) -> None:
    target = path or CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(baseline_set), indent=2))


def load_baseline_cache(path: Path | None = None) -> BaselineSet | None:
    target = path or CACHE_PATH
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text())
    except (OSError, ValueError):
        return None
    markers = raw.get("markers_per_100w") or {}
    if markers.get("kind") != "presence_intensity":
        # Legacy 1.2 cache (no kind discriminator, or robust_z markers).
        # Invalidate so the next run regenerates under schema 1.3.
        return None
    return _baseline_set_from_dict(raw)


def _baseline_set_from_dict(d: dict) -> BaselineSet:
    def robust_z(field: str) -> RobustZBaselineStat:
        sub = d.get(field) or {}
        return RobustZBaselineStat(
            median=sub.get("median", 0.0),
            mad=sub.get("mad", 0.0),
            n=sub.get("n", 0),
            low_confidence=sub.get("low_confidence", True),
        )

    markers_sub = d.get("markers_per_100w") or {}
    markers_stat: RobustZBaselineStat | PresenceIntensityBaselineStat
    if markers_sub.get("kind") == "presence_intensity":
        markers_stat = PresenceIntensityBaselineStat(
            presence_rate_corpus=markers_sub.get("presence_rate_corpus", 0.0),
            median_intensity_among_positives=markers_sub.get(
                "median_intensity_among_positives", 0.0
            ),
            n_blocks=markers_sub.get("n_blocks", 0),
            n_positive_blocks=markers_sub.get("n_positive_blocks", 0),
            low_confidence=markers_sub.get("low_confidence", True),
        )
    else:
        markers_stat = robust_z("markers_per_100w")

    return BaselineSet(
        block_length_words=robust_z("block_length_words"),
        question_rate_per_100w=robust_z("question_rate_per_100w"),
        markers_per_100w=markers_stat,
        reasoning_to_output_ratio=robust_z("reasoning_to_output_ratio"),
        tool_use_coupling_rate=robust_z("tool_use_coupling_rate"),
        leakage_events_per_session=robust_z("leakage_events_per_session"),
        reread_bursts_per_file=robust_z("reread_bursts_per_file"),
        edit_churn_per_file=robust_z("edit_churn_per_file"),
    )
