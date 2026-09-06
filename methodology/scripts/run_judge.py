"""Launcher for the v2 judge harness (methodology/judge_harness).

Puts methodology/ on sys.path so the package imports outside pytest.
Usage: uv run python methodology/scripts/run_judge.py --help
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judge_harness.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
