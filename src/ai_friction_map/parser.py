from __future__ import annotations

import json
import logging
from pathlib import Path

from ai_friction_map.attribution import attribute_thinking_blocks
from ai_friction_map.clusters import detect_excerpts
from ai_friction_map.events import Block, Corpus, ParsedEvent, ToolCall
from ai_friction_map.extraction import extract_file_paths
from ai_friction_map.leakage import aggregate_leakage
from ai_friction_map.paths import canonicalize_path

logger = logging.getLogger(__name__)

_KNOWN_TYPES = frozenset({
    "assistant", "user", "file-history-snapshot", "queue-operation",
    "attachment", "pr-link", "ai-title", "last-prompt",
    "progress", "system",
})


def parse_sessions(sessions_dir: Path) -> Corpus:
    """Stream-parse every *.jsonl file in sessions_dir into a Corpus.

    Line-by-line read; malformed JSON lines are warned and skipped.
    Unknown top-level type values are warned once per type value and
    counted in corpus.unknown_types but otherwise skipped. Within a
    session, event order is preserved via event_index. Tool-use blocks
    get file_paths extracted and canonicalized in the same pass.
    After the read, tool_use <-> tool_result matches are resolved per
    session by tool_use_id.
    """
    corpus = Corpus()
    logged_unknown: set[str] = set()

    for session_file in sorted(sessions_dir.glob("*.jsonl")):
        events = _parse_one_session(session_file, corpus, logged_unknown)
        if not events:
            continue
        session_id = events[0].session_id or session_file.stem
        corpus.sessions[session_id] = events
        corpus.session_count += 1
        corpus.event_count += len(events)

    _resolve_tool_calls(corpus)
    attribute_thinking_blocks(corpus)
    detect_excerpts(corpus)
    aggregate_leakage(corpus)
    return corpus


def _parse_one_session(
    path: Path,
    corpus: Corpus,
    logged_unknown: set[str],
) -> list[ParsedEvent]:
    events: list[ParsedEvent] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                logger.warning("skipping malformed line %s:%d", path.name, line_no)
                continue
            if not isinstance(raw, dict):
                logger.warning("skipping non-object line %s:%d", path.name, line_no)
                continue

            ev_type = raw.get("type", "")
            if ev_type not in _KNOWN_TYPES:
                corpus.unknown_types[ev_type] = corpus.unknown_types.get(ev_type, 0) + 1
                if ev_type not in logged_unknown:
                    logged_unknown.add(ev_type)
                    logger.warning("unknown event type (logged once): %r", ev_type)
                continue

            event = _build_event(raw, event_index=len(events))
            events.append(event)
    return events


def _build_event(raw: dict, event_index: int) -> ParsedEvent:
    ev_type = raw.get("type", "")
    session_id = raw.get("sessionId", "")
    cwd = raw.get("cwd")
    blocks = _build_blocks(raw, cwd)
    subtype = raw.get("subtype") if ev_type == "system" else None
    return ParsedEvent(
        session_id=session_id,
        event_index=event_index,
        type=ev_type,
        timestamp=raw.get("timestamp", ""),
        cwd=cwd,
        uuid=raw.get("uuid"),
        parent_uuid=raw.get("parentUuid"),
        blocks=blocks,
        raw_type=ev_type,
        subtype=subtype,
    )


def _build_blocks(raw: dict, cwd: str | None) -> list[Block]:
    ev_type = raw.get("type")
    if ev_type in ("assistant", "user"):
        message = raw.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            # user events can have plain-string content (user prompts)
            return []
        return _blocks_from_content(content, cwd, agent_sourced=False)

    if ev_type == "progress":
        return _walk_agent_progress(raw)

    return []


def _walk_agent_progress(raw: dict) -> list[Block]:
    """Recover nested tool_use / thinking / text / tool_result blocks from
    an agent_progress event and emit them as blocks on the progress event
    itself. Missing or malformed nested structure returns [] gracefully.
    """
    data = raw.get("data")
    if not isinstance(data, dict) or data.get("type") != "agent_progress":
        return []
    outer_msg = data.get("message")
    if not isinstance(outer_msg, dict):
        return []
    inner_msg = outer_msg.get("message")
    if not isinstance(inner_msg, dict):
        return []
    content = inner_msg.get("content")
    if not isinstance(content, list):
        return []
    cwd = raw.get("cwd")
    return _blocks_from_content(content, cwd, agent_sourced=True)


def _blocks_from_content(
    content: list,
    cwd: str | None,
    agent_sourced: bool = False,
) -> list[Block]:
    blocks: list[Block] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        btype = item.get("type")
        if btype == "text":
            blocks.append(Block(
                type="text",
                text=item.get("text"),
                agent_sourced=agent_sourced,
            ))
        elif btype == "thinking":
            blocks.append(Block(
                type="thinking",
                thinking=item.get("thinking"),
                agent_sourced=agent_sourced,
            ))
        elif btype == "tool_use":
            tool_input = item.get("input") if isinstance(item.get("input"), dict) else {}
            raw_paths = extract_file_paths(
                item.get("name", ""),
                tool_input,
                tool_result_content=None,
            )
            canon = _canonicalize_list(raw_paths, cwd)
            blocks.append(Block(
                type="tool_use",
                tool_name=item.get("name"),
                tool_use_id=item.get("id"),
                tool_input=tool_input,
                file_paths=canon,
                agent_sourced=agent_sourced,
            ))
        elif btype == "tool_result":
            blocks.append(Block(
                type="tool_result",
                tool_use_id=item.get("tool_use_id"),
                tool_result_content=item.get("content"),
                agent_sourced=agent_sourced,
            ))
    return blocks


def _canonicalize_list(paths: list[str], cwd: str | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        canon = canonicalize_path(p, cwd)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def _resolve_tool_calls(corpus: Corpus) -> None:
    """Build corpus.tool_calls by matching tool_use blocks to tool_result
    blocks within each session. Matching is by tool_use_id, which is
    unique within a session.
    """
    for session_id, events in corpus.sessions.items():
        pending: dict[str, ToolCall] = {}
        for event in events:
            for block in event.blocks:
                if block.type == "tool_use" and block.tool_use_id:
                    tc = ToolCall(
                        tool_use_id=block.tool_use_id,
                        session_id=session_id,
                        use_event_index=event.event_index,
                        tool_name=block.tool_name or "",
                        tool_input=block.tool_input or {},
                        file_paths=list(block.file_paths),
                    )
                    pending[block.tool_use_id] = tc
                    corpus.tool_calls[block.tool_use_id] = tc
                elif block.type == "tool_result" and block.tool_use_id:
                    tc = pending.get(block.tool_use_id)
                    if tc is None:
                        continue
                    tc.result_event_index = event.event_index
                    tc.result_content = block.tool_result_content
                    # Grep/Glob file paths live in the result content; now
                    # that we have it, re-extract and push back onto the
                    # originating use block so per-event iteration sees it.
                    if tc.tool_name in ("Grep", "Glob"):
                        raw_paths = extract_file_paths(
                            tc.tool_name,
                            tc.tool_input,
                            block.tool_result_content,
                        )
                        use_event = events[tc.use_event_index]
                        canon = _canonicalize_list(raw_paths, use_event.cwd)
                        tc.file_paths = canon
                        for b in use_event.blocks:
                            if b.type == "tool_use" and b.tool_use_id == tc.tool_use_id:
                                b.file_paths = canon
                                break
