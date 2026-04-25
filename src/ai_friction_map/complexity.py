"""Per-file complexity metrics.

Tier 1 (this module): language-agnostic — line counts, byte counts, and
regex-based function/class counts dispatched per language.

Tier 2: Python-only cyclomatic + Halstead via `radon`. Tier 2 is appended
in Task 2; non-Python files always get cyclomatic=None, halstead_volume=None.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ai_friction_map.events import CyclomaticMetrics, FileComplexity

logger = logging.getLogger(__name__)


_FUNC_RE_BY_EXT: dict[str, re.Pattern[str]] = {
    ".py": re.compile(r"^\s*(?:async\s+)?def\s+\w+\s*\(", re.MULTILINE),
    ".js": re.compile(
        r"(?:^\s*function\s+\w+\s*\()"
        r"|(?:^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>))"
        r"|(?:^\s*\w+\s*\([^)]*\)\s*\{)",
        re.MULTILINE,
    ),
    ".go": re.compile(r"^func\s+(?:\([^)]*\)\s+)?\w+\s*\(", re.MULTILINE),
    ".rs": re.compile(r"^\s*(?:pub\s+)?fn\s+\w+", re.MULTILINE),
}
for ext in (".jsx", ".ts", ".tsx"):
    _FUNC_RE_BY_EXT[ext] = _FUNC_RE_BY_EXT[".js"]

_CLASS_RE_BY_EXT: dict[str, re.Pattern[str]] = {
    ".py": re.compile(r"^\s*class\s+\w+", re.MULTILINE),
    ".js": re.compile(r"^\s*(?:export\s+)?class\s+\w+", re.MULTILINE),
    ".go": re.compile(r"^type\s+\w+\s+struct", re.MULTILINE),
    ".rs": re.compile(r"^\s*(?:pub\s+)?struct\s+\w+", re.MULTILINE),
}
for ext in (".jsx", ".ts", ".tsx"):
    _CLASS_RE_BY_EXT[ext] = _CLASS_RE_BY_EXT[".js"]


_HASH_COMMENT_EXTS = {".py", ".yaml", ".yml", ".toml", ".sh"}
_SLASH_COMMENT_EXTS = {".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".c", ".cpp", ".java"}


def _is_comment_line(line: str, ext: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return False
    if ext in _HASH_COMMENT_EXTS:
        return stripped.startswith("#")
    if ext in _SLASH_COMMENT_EXTS:
        return stripped.startswith("//")
    return False


def compute_file_complexity(canonical_path: str) -> FileComplexity:
    path = Path(canonical_path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.debug("complexity: file not found: %s", canonical_path)
        return FileComplexity()

    ext = path.suffix.lower()
    lines = source.splitlines()
    loc = len(lines)
    char_count = len(source)
    loc_no_blanks_comments = sum(
        1 for line in lines if line.strip() and not _is_comment_line(line, ext)
    )

    func_re = _FUNC_RE_BY_EXT.get(ext)
    class_re = _CLASS_RE_BY_EXT.get(ext)
    function_count = len(func_re.findall(source)) if func_re else 0
    class_count = len(class_re.findall(source)) if class_re else 0

    cyclomatic, halstead_volume = _compute_python_metrics(source) if ext == ".py" else (None, None)

    return FileComplexity(
        loc=loc,
        loc_no_blanks_comments=loc_no_blanks_comments,
        char_count=char_count,
        function_count=function_count,
        class_count=class_count,
        cyclomatic=cyclomatic,
        halstead_volume=halstead_volume,
    )


def _compute_python_metrics(source: str) -> tuple[CyclomaticMetrics | None, float | None]:
    try:
        from radon.complexity import cc_visit
        from radon.metrics import h_visit
    except ImportError:
        logger.debug("complexity: radon not installed; skipping tier 2 metrics")
        return None, None

    try:
        cc_results = cc_visit(source)
    except Exception as exc:  # noqa: BLE001 — radon raises various parse errors
        logger.debug("complexity: cc_visit failed: %s", exc)
        return None, None

    if not cc_results:
        cyclomatic: CyclomaticMetrics | None = CyclomaticMetrics(max=0, mean=0.0, sum=0)
    else:
        complexities = [r.complexity for r in cc_results]
        cyclomatic = CyclomaticMetrics(
            max=max(complexities),
            mean=sum(complexities) / len(complexities),
            sum=sum(complexities),
        )

    try:
        h_report = h_visit(source)
        halstead_volume: float | None = h_report.total.volume
    except Exception as exc:  # noqa: BLE001
        logger.debug("complexity: h_visit failed: %s", exc)
        halstead_volume = None

    return cyclomatic, halstead_volume
