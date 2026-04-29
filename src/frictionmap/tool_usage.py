"""Per-file tool usage counter.

Walks every tool_use block in the corpus (including walker-emitted /
agent_sourced ones) and increments the appropriate counter on
`corpus.tool_usage_by_file[file_path]`.

Kept separate from leakage.py: leakage detects patterns; this is a
straight counter.
"""
from __future__ import annotations

from frictionmap.events import Corpus, ToolUsage

_TOOL_TO_FIELD = {
    "Read": "read",
    "Edit": "edit",
    "Write": "write",
    "Bash": "bash",
    "Grep": "grep",
    "Glob": "glob",
}


def aggregate_tool_usage(corpus: Corpus) -> None:
    counts: dict[str, ToolUsage] = {}
    for events in corpus.sessions.values():
        for event in events:
            for block in event.blocks:
                if block.type != "tool_use" or not block.tool_name:
                    continue
                field = _TOOL_TO_FIELD.get(block.tool_name)
                if field is None:
                    continue
                seen: set[str] = set()
                for path in block.file_paths:
                    if not path or path in seen:
                        continue
                    seen.add(path)
                    entry = counts.setdefault(path, ToolUsage())
                    setattr(entry, field, getattr(entry, field) + 1)
    corpus.tool_usage_by_file = counts
