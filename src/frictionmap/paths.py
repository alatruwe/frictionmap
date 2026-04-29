from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def canonicalize_path(raw_path: str, cwd: str | None) -> str:
    """Return the absolute, resolved POSIX form of raw_path.

    Absolute paths resolve against the filesystem. Relative paths resolve
    against cwd when available. Relative paths with no cwd are returned
    unchanged (debug-logged) — this case should be rare for assistant
    events, which carry cwd.

    resolve(strict=False) handles .., ., and symlinks without requiring
    the path to exist.
    """
    p = Path(raw_path)
    if p.is_absolute():
        return str(p.resolve(strict=False))
    if cwd:
        return str((Path(cwd) / raw_path).resolve(strict=False))
    logger.debug("relative path with no cwd: %s", raw_path)
    return raw_path
