from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Attribution:
    """Schema 1.2: file_paths is a list; was singular file_path in 1.1.

    Per-tier semantics on multi-file:
    - exact_path: every canonical path whose suffix was mentioned in thinking.
    - unique_basename: every mentioned basename that uniquely resolves.
    - temporal_proximity: the entire file_paths list of the nearest tool_use.
    Blocks with no candidates get file_paths=[].
    """
    tier: Literal["exact_path", "unique_basename", "temporal_proximity"]
    confidence: Literal["high", "medium", "low"]
    file_paths: list[str] = field(default_factory=list)
    proximity_distance: int | None = None
    proximity_direction: Literal["before", "after"] | None = None


@dataclass
class Highlight:
    start: int
    end: int
    marker: str


@dataclass
class BlockSignals:
    length_words: int = 0
    length_chars: int = 0
    question_rate_per_100w: float = 0.0
    marker_count: int = 0
    markers_per_100w: float = 0.0
    tool_use_coupling: bool = False


@dataclass
class ThinkingExcerpt:
    """Atomic unit of evidence for a friction signal.

    Fields beyond cluster_index/cluster_count/text/highlights are populated
    by `report.assemble_report`. Until that runs, they hold default values —
    do not read them from a Block mid-pipeline.
    """
    cluster_index: int
    cluster_count: int
    text: str
    highlights: list[Highlight] = field(default_factory=list)
    agent_sourced: bool = False
    session_id: str = ""
    session_id_short: str = ""
    block_index: int = 0
    block_total: int = 0
    block_length_words: int = 0
    attribution: Attribution | None = None
    block_signals: BlockSignals = field(default_factory=BlockSignals)


@dataclass
class LeakageCounts:
    edit_failures: int = 0
    grep_reformulations: int = 0
    bash_retries: int = 0
    read_after_edit: int = 0
    total: int = 0


@dataclass
class ToolUsage:
    read: int = 0
    edit: int = 0
    write: int = 0
    bash: int = 0
    grep: int = 0
    glob: int = 0


@dataclass
class Block:
    type: str
    text: str | None = None
    thinking: str | None = None
    tool_name: str | None = None
    tool_use_id: str | None = None
    tool_input: dict | None = None
    tool_result_content: str | list | None = None
    file_paths: list[str] = field(default_factory=list)
    agent_sourced: bool = False
    attribution: Attribution | None = None
    excerpts: list[ThinkingExcerpt] = field(default_factory=list)


@dataclass
class ParsedEvent:
    session_id: str
    event_index: int
    type: str
    timestamp: str
    cwd: str | None
    uuid: str | None
    parent_uuid: str | None
    blocks: list[Block] = field(default_factory=list)
    raw_type: str = ""
    subtype: str | None = None
    model: str | None = None
    # is_assistant_like distinguishes "non-assistant event, no model
    # expected" (False) from "assistant-like event whose model field was
    # missing or malformed" (True). The unknown-model bucket only counts
    # the latter.
    is_assistant_like: bool = False


@dataclass
class ToolCall:
    tool_use_id: str
    session_id: str
    use_event_index: int
    tool_name: str
    tool_input: dict
    file_paths: list[str] = field(default_factory=list)
    result_event_index: int | None = None
    result_content: str | list | None = None


@dataclass
class Corpus:
    sessions: dict[str, list[ParsedEvent]] = field(default_factory=dict)
    tool_calls: dict[str, ToolCall] = field(default_factory=dict)
    session_count: int = 0
    event_count: int = 0
    unknown_types: dict[str, int] = field(default_factory=dict)
    leakage_by_file: dict[str, LeakageCounts] = field(default_factory=dict)
    tool_usage_by_file: dict[str, ToolUsage] = field(default_factory=dict)


@dataclass
class CyclomaticMetrics:
    max: int
    mean: float
    sum: int


@dataclass
class FileComplexity:
    loc: int = 0
    loc_no_blanks_comments: int = 0
    char_count: int = 0
    function_count: int = 0
    class_count: int = 0
    cyclomatic: CyclomaticMetrics | None = None
    halstead_volume: float | None = None


@dataclass
class SignalValue:
    raw: float = 0.0
    z_score: float = 0.0
    weight: float = 0.0
    contribution: float = 0.0


@dataclass
class ScoreComponents:
    markers: SignalValue = field(default_factory=SignalValue)
    block_length_words: SignalValue = field(default_factory=SignalValue)
    question_rate_per_100w: SignalValue = field(default_factory=SignalValue)
    tool_use_coupling: SignalValue = field(default_factory=SignalValue)
    reread_bursts: SignalValue = field(default_factory=SignalValue)
    edit_churn: SignalValue = field(default_factory=SignalValue)
    reasoning_to_output_ratio: SignalValue = field(default_factory=SignalValue)
    edit_failures: SignalValue = field(default_factory=SignalValue)
    grep_reformulations: SignalValue = field(default_factory=SignalValue)
    bash_retries: SignalValue = field(default_factory=SignalValue)
    read_after_edit: SignalValue = field(default_factory=SignalValue)
    normalized_by_loc: float = 0.0
    normalized_by_complexity: float | None = None
    multi_file_weight: float = 1.0


@dataclass
class RobustZBaselineStat:
    kind: Literal["robust_z"] = "robust_z"
    median: float = 0.0
    mad: float = 0.0
    n: int = 0
    low_confidence: bool = True


@dataclass
class PresenceIntensityBaselineStat:
    kind: Literal["presence_intensity"] = "presence_intensity"
    presence_rate_corpus: float = 0.0
    median_intensity_among_positives: float = 0.0
    n_blocks: int = 0
    n_positive_blocks: int = 0
    low_confidence: bool = True


# Schema 1.3 alias: legacy `BaselineStat(...)` constructors and type
# annotations resolve to the robust-z branch. The markers signal is the
# only field whose static type widens to the union.
BaselineStat = RobustZBaselineStat


@dataclass
class BaselineSet:
    block_length_words: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    question_rate_per_100w: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    markers_per_100w: RobustZBaselineStat | PresenceIntensityBaselineStat = field(
        default_factory=PresenceIntensityBaselineStat
    )
    reasoning_to_output_ratio: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    tool_use_coupling_rate: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    leakage_events_per_session: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    reread_bursts_per_file: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)
    edit_churn_per_file: RobustZBaselineStat = field(default_factory=RobustZBaselineStat)


@dataclass
class Baselines:
    corpus: BaselineSet = field(default_factory=BaselineSet)


@dataclass
class ModelDistribution:
    events_by_model: dict[str, int] = field(default_factory=dict)
    sessions_by_model: dict[str, int] = field(default_factory=dict)
    unknown_model_event_count: int = 0


@dataclass
class CodebaseMeta:
    name: str
    session_count: int
    file_count: int
    thinking_block_count: int
    total_event_count: int
    generated_at: str
    schema_version: str = "1.4"
    model_distribution: ModelDistribution = field(default_factory=ModelDistribution)


@dataclass
class FileFriction:
    path: str
    name: str
    directory: str
    score: float = 0.0
    tangle_count: int = 0
    session_count: int = 0
    loc: int = 0
    thinking_resolution_rate: float = 0.0
    score_components: ScoreComponents = field(default_factory=ScoreComponents)
    complexity: FileComplexity = field(default_factory=FileComplexity)
    leakage: LeakageCounts = field(default_factory=LeakageCounts)
    tool_usage: ToolUsage = field(default_factory=ToolUsage)
    excerpts: list[ThinkingExcerpt] = field(default_factory=list)


@dataclass
class Report:
    meta: CodebaseMeta
    baselines: Baselines = field(default_factory=Baselines)
    session_baselines: dict[str, BaselineSet] = field(default_factory=dict)
    files: list[FileFriction] = field(default_factory=list)
    session_titles: dict[str, str] = field(default_factory=dict)
