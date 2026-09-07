"""Audit sample (spec §5): deterministic, seedless, spans repos.

Per population agent, take the discovery-passing files (non_trajectory files
never enter), sort filenames bytewise, and walk from index 0 taking every
ceil(n/50)-th file (~50/agent, ~650 total).
"""
from __future__ import annotations

import math
from pathlib import Path

from swebench_adapter.discovery import Discovery

TARGET_PER_AGENT = 50


def audit_sample(discovery: Discovery, target: int = TARGET_PER_AGENT) -> list[Path]:
    files = sorted(discovery.files, key=lambda p: p.name.encode())
    if not files:
        return []
    step = math.ceil(len(files) / target)
    return files[::step]
