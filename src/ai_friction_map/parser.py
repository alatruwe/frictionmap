from __future__ import annotations

import json
from pathlib import Path


def parse_sessions(sessions_dir: Path) -> dict:
    """Walk sessions_dir, count session files and valid events.

    A "session" is any file matching *.jsonl directly in sessions_dir
    (not recursive — sessions are flat files in the project directory).

    An "event" is one line in a session file that parses as JSON.
    Lines that fail to parse are skipped silently in v1.
    """
    session_count = 0
    event_count = 0
    for session_file in sessions_dir.glob("*.jsonl"):
        session_count += 1
        with session_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    json.loads(line)
                except ValueError:
                    continue
                event_count += 1
    return {"session_count": session_count, "event_count": event_count}
