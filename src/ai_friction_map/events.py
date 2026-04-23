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
class ThinkingExcerpt:
    cluster_index: int
    cluster_count: int
    text: str
    highlights: list[Highlight] = field(default_factory=list)


@dataclass
class LeakageCounts:
    edit_failures: int = 0
    grep_reformulations: int = 0
    bash_retries: int = 0
    read_after_edit: int = 0
    total: int = 0


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
