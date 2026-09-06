"""FrictionMap v2 judge-run harness (pre-registration §5).

Scores thinking blocks with a frozen judge prompt, one independent API call per
unit, and stores every attempt under judge-runs/ (gitignored). Default mode is
dry-run over the anchor sessions; the validation sample is reachable only
through the gated --validation-run path.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
