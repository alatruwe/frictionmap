"""Shared synthetic-event factories for 2B tests.

Events returned here are raw dicts matching the Claude Code session JSONL
shape. Write them with tests/test_parser.py's _jsonl helper.
"""
from __future__ import annotations

import json
from pathlib import Path


def jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def assistant(
    session_id: str,
    uuid: str,
    content: list[dict],
    cwd: str = "/proj",
    model: str | None = None,
) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if model is not None:
        message["model"] = model
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": cwd,
        "message": message,
    }


def user(session_id: str, uuid: str, content, cwd: str = "/proj") -> dict:
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:01Z",
        "cwd": cwd,
        "message": {"role": "user", "content": content},
    }


def bare(session_id: str, uuid: str, ev_type: str) -> dict:
    return {
        "type": ev_type,
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:02Z",
        "cwd": "/proj",
    }


def system_compact(session_id: str, uuid: str, cwd: str = "/proj") -> dict:
    return {
        "type": "system",
        "subtype": "compact_boundary",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:03Z",
        "cwd": cwd,
        "content": "Conversation compacted",
    }


def progress(
    session_id: str,
    uuid: str,
    nested_content: list[dict],
    cwd: str = "/proj",
    parent_tool_use_id: str | None = None,
    nested_role: str = "assistant",
    model: str | None = None,
) -> dict:
    nested_message_type = nested_role
    inner: dict = {"role": nested_role, "content": nested_content}
    if model is not None:
        inner["model"] = model
    return {
        "type": "progress",
        "parentToolUseID": parent_tool_use_id,
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:04Z",
        "cwd": cwd,
        "data": {
            "type": "agent_progress",
            "agentId": "agent-xyz",
            "message": {
                "type": nested_message_type,
                "timestamp": "2026-04-22T00:00:04Z",
                "uuid": f"{uuid}-nested",
                "message": inner,
            },
        },
    }


def non_agent_progress(session_id: str, uuid: str, cwd: str = "/proj") -> dict:
    return {
        "type": "progress",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:05Z",
        "cwd": cwd,
        "data": {"type": "other_progress_kind"},
    }
