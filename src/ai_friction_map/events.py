from __future__ import annotations

from dataclasses import dataclass, field


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
