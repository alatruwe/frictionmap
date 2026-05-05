"""Phase 3 — per-block and per-file signal computation, scoring v1.

This module is the integration point for Tasks 2, 3, 5, 6, 7 of the Phase 3
handoff. Counts and ratios only — no NLP, no LLM in the loop.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from frictionmap.clusters import find_markers, strip_code_fences
from frictionmap.events import (
    BaselineSet,
    BaselineStat,
    BlockSignals,
    Corpus,
    LeakageCounts,
    ParsedEvent,
    ScoreComponents,
    SignalValue,
)
from frictionmap.windows import window_events

_WORD_RE = re.compile(r"\S+")

TOOL_USE_COUPLING_WINDOW = 3
RE_READ_WINDOW = 5
EDIT_CHURN_WINDOW = 5

# Phase 5 tunables — exposed as named constants, not magic numbers.
CLUSTER_WEIGHT_ALPHA = 0.2
REASONING_TO_OUTPUT_CAP = 100.0


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _has_tool_use_in_window(
    events: list[ParsedEvent], center_idx: int, n: int
) -> bool:
    lo, hi = window_events(events, center_idx, n)
    for i in range(lo, hi + 1):
        for block in events[i].blocks:
            if block.type == "tool_use":
                return True
    return False


def compute_block_signals(
    thinking_text: str,
    event_idx: int,
    events: list[ParsedEvent],
) -> BlockSignals:
    """All length-based fields use code-stripped text; mixing stripped and
    unstripped sources across signals would make z-scores incomparable.
    """
    stripped = strip_code_fences(thinking_text)
    stripped_words = _word_count(stripped)
    stripped_chars = len(stripped)
    marker_count = len(find_markers(thinking_text))
    q_count = stripped.count("?")
    denom = max(stripped_words, 1)
    return BlockSignals(
        length_words=stripped_words,
        length_chars=stripped_chars,
        question_rate_per_100w=q_count / denom * 100.0,
        marker_count=marker_count,
        markers_per_100w=marker_count / denom * 100.0,
        tool_use_coupling=_has_tool_use_in_window(
            events, event_idx, TOOL_USE_COUPLING_WINDOW
        ),
    )


def _per_file_burst_count(
    corpus: Corpus, tool_name: str, window: int
) -> dict[str, int]:
    """Count tool invocations of `tool_name` (Read or Edit) on a given file
    that have at least one same-file invocation inside the ±window range.
    Boundary-respecting via `windows.window_events`.
    """
    counts: dict[str, int] = defaultdict(int)
    for events in corpus.sessions.values():
        indices_by_path: dict[str, list[int]] = defaultdict(list)
        for i, event in enumerate(events):
            for block in event.blocks:
                if (
                    block.type == "tool_use"
                    and block.tool_name == tool_name
                    and block.file_paths
                ):
                    for path in block.file_paths:
                        indices_by_path[path].append(i)
        for path, indices in indices_by_path.items():
            for pos, i in enumerate(indices):
                lo, hi = window_events(events, i, window)
                for other_pos, j in enumerate(indices):
                    if other_pos == pos:
                        continue
                    if lo <= j <= hi:
                        counts[path] += 1
                        break
    return dict(counts)


def compute_reread_bursts(corpus: Corpus) -> dict[str, int]:
    return _per_file_burst_count(corpus, "Read", RE_READ_WINDOW)


def compute_edit_churn(corpus: Corpus) -> dict[str, int]:
    return _per_file_burst_count(corpus, "Edit", EDIT_CHURN_WINDOW)


# reasoning_to_output_ratio is parked at weight 0.0 pending a per-file
# definition rework — the current denominator (output chars in same turn)
# is too small/zero on assistant-thinks-then-tool-uses turns, which is
# most turns, so the ratio saturates at REASONING_TO_OUTPUT_CAP for
# nearly every attributed file and floods the score. The signal still
# computes and emits in ScoreComponents so the operationalization can
# be revisited without re-architecting.
#
# Leakage signals (edit_failures, grep_reformulations, bash_retries,
# read_after_edit) are parked at weight 0.0 pending either a debugger
# use case (Phase 7) or a per-file definition rework. The corpus
# baseline (leakage_events_per_session) is sparse-positive — collapsed
# to median=0 / MAD=0 on both reference corpora — and the per-file
# rollup does not fingerprint friction-causing files in either raw or
# per-LOC normalization. The signals still compute and emit in
# ScoreComponents, and corpus.leakage_by_file is populated; the parking
# preserves the data without locking the wrong-shape signal into the
# friction map score.
#
# question_rate_per_100w is parked at weight 0.0 pending either a
# broader question-token lexicon or a path-extractor fix. The signal is
# sparse-positive at ~7% on both reference corpora (4–5x sparser than
# markers had pre-reshape), and the per-file orthogonality diagnostic
# showed that a presence/intensity migration would lift mostly
# attribution-noise: URL fragments, directory paths, single-attribution
# multi-file splits, and git-ref artifacts. On attune, every file in
# the hyp top-15 was small-N (n_blocks_attributed < 3); on brownfield,
# 11/15. The one production file with thick evidence was already in
# the current top-20. Signal still computes and emits in
# ScoreComponents so a future broader lexicon or cleaner path
# extractor can revisit without re-architecting.
#
# tool_use_coupling is parked at weight 0.0 because the binary signal
# saturates at 97-99% pooled coupling on both reference corpora.
# Block-level diagnostic established that this saturation collapses
# opposite-sign stratum effects: marker-positive thinking blocks lean
# away from investigative tools (Read/Grep/Glob; gap -0.16/-0.15) and
# toward bash (gap +0.13/+0.20). The class-stratified versions
# (bash_coupling_rate, investigative_coupling_rate) are real v2
# redefinition candidates with measured per-file spread, but validating
# them through full Section B+C work was deferred to keep v1 scope
# bounded. The thinking_resolution_rate file-level aggregate (computed
# from _BlockAgg.coupled_block_count / tangle_count) is still exposed
# in the report payload, independently of this parked scoring path.
#
# block_length_words is parked at weight 0.0. The corpus baseline is
# healthy (attune median=71/MAD=49, brownfield median=61/MAD=44.5),
# but the per-file rollup of length-only top-15 is dominated by
# attribution noise (URL fragments, bare directory paths, absolute
# paths off the codebase root) and small-N evidence on both reference
# corpora; the thick-evidence orthogonal candidates that exist (e.g.
# CLAUDE.md at n=9, permissions/views at n=5) are mostly NOT in
# production top-20, meaning length is surfacing files that markers +
# behavioral signals correctly deprioritized. Section A's block-level
# Pearson r flips negative on both_positive blocks (-0.175 attune,
# -0.286 brownfield) — a denominator artifact (markers/100w is
# intensity, length is size) but it confirms the signals aren't
# redundant. Signal still computes (BlockSignals.length_words) and
# aggregates (_BlockAgg.weighted_length); only the WEIGHTS multiplier
# is zeroed. Reversibility: post-path-extractor fix re-evaluation, a
# more diverse corpus, or Phase 7 session-detail use.
WEIGHTS: dict[str, float] = {
    "markers": 0.25,
    "block_length_words": 0.0,
    "question_rate_per_100w": 0.0,
    "tool_use_coupling": 0.0,
    "reread_bursts": 0.25 / 3,
    "edit_churn": 0.25 / 3,
    "reasoning_to_output_ratio": 0.0,
    "edit_failures": 0.0,
    "grep_reformulations": 0.0,
    "bash_retries": 0.0,
    "read_after_edit": 0.0,
}


def cluster_weight(cluster_count: int) -> float:
    """`1 + α(N − 1)`. N≤1 → 1.0, the additive identity."""
    if cluster_count <= 1:
        return 1.0
    return 1.0 + CLUSTER_WEIGHT_ALPHA * (cluster_count - 1)


@dataclass
class _BlockAgg:
    """Per-file accumulator for per-block signals.

    weighted_* sums apply 1/N multi-file dilution; unweighted_* sums do
    not. The `dilution_weight_sum` divides weighted sums to produce a
    weighted mean (used as SignalValue.raw for per-block signals).
    `tangle_count` is the count of distinct attributed thinking blocks
    where this file appears — multi-file blocks count as 1 per file
    they attribute to, intentionally diverging from the 1/N scoring.

    `positive_block_weight_sum` and `weighted_intensity_positive_sum`
    feed the schema-1.3 presence/intensity formula for markers. They
    track the dilution-weighted sub-population of attributed blocks
    where `markers_per_100w > 0`, with raw intensity (no cluster_weight
    multiplier — that lived in the z-score era).
    """
    dilution_weight_sum: float = 0.0
    tangle_count: int = 0
    coupled_block_count: int = 0
    weighted_markers: float = 0.0
    unweighted_markers: float = 0.0
    weighted_length: float = 0.0
    weighted_question_rate: float = 0.0
    weighted_tool_use_coupling: float = 0.0
    positive_block_weight_sum: float = 0.0
    weighted_intensity_positive_sum: float = 0.0


def _aggregate_block_signals(corpus: Corpus) -> dict[str, _BlockAgg]:
    """One pass over thinking blocks; per-file weighted/unweighted sums."""
    out: dict[str, _BlockAgg] = defaultdict(_BlockAgg)
    for events in corpus.sessions.values():
        for event_idx, event in enumerate(events):
            for block in event.blocks:
                if block.type != "thinking" or not block.thinking:
                    continue
                if not block.attribution or not block.attribution.file_paths:
                    continue
                paths = block.attribution.file_paths
                n = len(paths)
                share = 1.0 / n
                signals = compute_block_signals(block.thinking, event_idx, events)
                cw = cluster_weight(len(block.excerpts) if block.excerpts else 1)
                marker_signal = signals.markers_per_100w * cw
                tc_val = 1.0 if signals.tool_use_coupling else 0.0
                # Schema 1.3: presence/intensity uses raw markers_per_100w
                # (no cw); cw stays scoped to the legacy weighted_markers
                # path that feeds multi_file_weight.
                marker_rate = signals.markers_per_100w
                positive = marker_rate > 0
                for path in paths:
                    agg = out[path]
                    agg.dilution_weight_sum += share
                    agg.tangle_count += 1
                    if signals.tool_use_coupling:
                        agg.coupled_block_count += 1
                    agg.weighted_markers += marker_signal * share
                    agg.unweighted_markers += marker_signal
                    agg.weighted_length += signals.length_words * share
                    agg.weighted_question_rate += signals.question_rate_per_100w * share
                    agg.weighted_tool_use_coupling += tc_val * share
                    if positive:
                        agg.positive_block_weight_sum += share
                        agg.weighted_intensity_positive_sum += marker_rate * share
    return out


def _z(raw: float, baseline: BaselineStat) -> float:
    if baseline.mad <= 0:
        return 0.0
    return (raw - baseline.median) / (1.4826 * baseline.mad)


def _signal(name: str, raw: float, baseline: BaselineStat) -> SignalValue:
    z = _z(raw, baseline)
    weight = WEIGHTS.get(name, 0.0)
    return SignalValue(raw=raw, z_score=z, weight=weight, contribution=z * weight)


@dataclass
class FileScoreResult:
    """Output of `score_file`. The report assembler copies these fields
    onto the corresponding `FileFriction`.
    """
    components: ScoreComponents = field(default_factory=ScoreComponents)
    score_pre_normalization: float = 0.0
    tangle_count: int = 0
    thinking_resolution_rate: float = 0.0


def score_file(
    path: str,
    block_agg: _BlockAgg,
    reread_count: int,
    edit_churn_count: int,
    reasoning_to_output: float,
    leakage: LeakageCounts,
    baseline: BaselineSet,
) -> FileScoreResult:
    """Build a `ScoreComponents` plus the pre-normalization aggregate.

    Per-block signal raw values are weighted means across attributed
    blocks (1/N dilution applied); per-file signals (behavioral and
    leakage) carry direct raw values. `multi_file_weight` is the
    actual scaling factor — `weighted_marker_total /
    unweighted_marker_total` — and is informational; it does not
    multiply the score again at consumption time (the dilution is
    already baked into the weighted means).
    """
    if block_agg.dilution_weight_sum > 0:
        length_raw = block_agg.weighted_length / block_agg.dilution_weight_sum
        question_raw = block_agg.weighted_question_rate / block_agg.dilution_weight_sum
        tc_raw = block_agg.weighted_tool_use_coupling / block_agg.dilution_weight_sum
        presence_rate = (
            block_agg.positive_block_weight_sum / block_agg.dilution_weight_sum
        )
    else:
        length_raw = question_raw = tc_raw = 0.0
        presence_rate = 0.0

    if block_agg.positive_block_weight_sum > 0:
        mean_intensity = (
            block_agg.weighted_intensity_positive_sum
            / block_agg.positive_block_weight_sum
        )
    else:
        mean_intensity = 0.0

    markers_raw = presence_rate * mean_intensity
    markers_weight = WEIGHTS["markers"]
    # Schema 1.3: markers uses presence × intensity, not robust z-score.
    # z_score=0.0 is a placeholder kept for SignalValue shape stability;
    # no consumer reads it for the markers signal.
    markers_signal = SignalValue(
        raw=markers_raw,
        z_score=0.0,
        weight=markers_weight,
        contribution=markers_raw * markers_weight,
    )

    if block_agg.unweighted_markers > 0:
        mfw = block_agg.weighted_markers / block_agg.unweighted_markers
    else:
        mfw = 1.0

    components = ScoreComponents(
        markers=markers_signal,
        block_length_words=_signal(
            "block_length_words", length_raw, baseline.block_length_words
        ),
        question_rate_per_100w=_signal(
            "question_rate_per_100w", question_raw, baseline.question_rate_per_100w
        ),
        tool_use_coupling=_signal(
            "tool_use_coupling", tc_raw, baseline.tool_use_coupling_rate
        ),
        reread_bursts=_signal(
            "reread_bursts", float(reread_count), baseline.reread_bursts_per_file
        ),
        edit_churn=_signal(
            "edit_churn", float(edit_churn_count), baseline.edit_churn_per_file
        ),
        reasoning_to_output_ratio=_signal(
            "reasoning_to_output_ratio",
            reasoning_to_output,
            baseline.reasoning_to_output_ratio,
        ),
        edit_failures=_signal(
            "edit_failures",
            float(leakage.edit_failures),
            baseline.leakage_events_per_session,
        ),
        grep_reformulations=_signal(
            "grep_reformulations",
            float(leakage.grep_reformulations),
            baseline.leakage_events_per_session,
        ),
        bash_retries=_signal(
            "bash_retries",
            float(leakage.bash_retries),
            baseline.leakage_events_per_session,
        ),
        read_after_edit=_signal(
            "read_after_edit",
            float(leakage.read_after_edit),
            baseline.leakage_events_per_session,
        ),
        multi_file_weight=mfw,
    )
    score_pre = sum(
        sv.contribution
        for sv in (
            components.markers,
            components.block_length_words,
            components.question_rate_per_100w,
            components.tool_use_coupling,
            components.reread_bursts,
            components.edit_churn,
            components.reasoning_to_output_ratio,
            components.edit_failures,
            components.grep_reformulations,
            components.bash_retries,
            components.read_after_edit,
        )
    )
    thinking_res = (
        block_agg.coupled_block_count / block_agg.tangle_count
        if block_agg.tangle_count > 0
        else 0.0
    )
    return FileScoreResult(
        components=components,
        score_pre_normalization=score_pre,
        tangle_count=block_agg.tangle_count,
        thinking_resolution_rate=thinking_res,
    )


def score_corpus(
    corpus: Corpus, baseline: BaselineSet
) -> dict[str, FileScoreResult]:
    """One-shot scorer; called by report.assemble_report."""
    block_aggs = _aggregate_block_signals(corpus)
    reread = compute_reread_bursts(corpus)
    edit_churn = compute_edit_churn(corpus)
    ratio = compute_reasoning_to_output_ratio(corpus)
    paths: set[str] = set()
    paths.update(block_aggs.keys())
    paths.update(reread.keys())
    paths.update(edit_churn.keys())
    paths.update(ratio.keys())
    paths.update(corpus.leakage_by_file.keys())
    out: dict[str, FileScoreResult] = {}
    for path in paths:
        out[path] = score_file(
            path,
            block_aggs.get(path, _BlockAgg()),
            reread.get(path, 0),
            edit_churn.get(path, 0),
            ratio.get(path, 0.0),
            corpus.leakage_by_file.get(path, LeakageCounts()),
            baseline,
        )
    return out


def compute_reasoning_to_output_ratio(corpus: Corpus) -> dict[str, float]:
    """Per file F: R_F = sum(thinking chars) over blocks attributed to F.
    O_F = sum(text chars) over assistant text blocks emitted in the SAME
    assistant turns as those attributed thinking blocks. Each turn's text
    is counted once per file (a turn with multiple F-attributed blocks
    contributes its text to O_F once).
    """
    r_by_file: dict[str, float] = defaultdict(float)
    o_by_file: dict[str, float] = defaultdict(float)
    seen_turns_by_file: dict[str, set[tuple[str, int]]] = defaultdict(set)

    for session_id, events in corpus.sessions.items():
        for event_idx, event in enumerate(events):
            if event.type != "assistant":
                continue
            text_chars_in_turn = 0
            r_per_path_in_turn: dict[str, int] = defaultdict(int)
            for block in event.blocks:
                if block.type == "text" and block.text:
                    text_chars_in_turn += len(block.text)
                elif (
                    block.type == "thinking"
                    and block.thinking
                    and block.attribution
                    and block.attribution.file_paths
                ):
                    for path in block.attribution.file_paths:
                        r_per_path_in_turn[path] += len(block.thinking)
            for path, r in r_per_path_in_turn.items():
                r_by_file[path] += r
                key = (session_id, event_idx)
                if key not in seen_turns_by_file[path]:
                    seen_turns_by_file[path].add(key)
                    o_by_file[path] += text_chars_in_turn

    out: dict[str, float] = {}
    for path, r in r_by_file.items():
        ratio = r / max(o_by_file[path], 1.0)
        out[path] = min(ratio, REASONING_TO_OUTPUT_CAP)
    return out
