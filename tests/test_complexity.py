from __future__ import annotations

from pathlib import Path

from ai_friction_map.complexity import compute_file_complexity
from ai_friction_map.events import CyclomaticMetrics


def test_python_file_basic_counts(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text(
        "class Foo:\n"
        "    def a(self):\n"
        "        return 1\n"
        "\n"
        "def top():\n"
        "    return 2\n"
        "\n"
        "async def fetch():\n"
        "    return 3\n",
        encoding="utf-8",
    )
    c = compute_file_complexity(str(src))
    assert c.function_count == 3
    assert c.class_count == 1
    assert c.loc == 9


def test_javascript_function_forms(tmp_path: Path) -> None:
    src = tmp_path / "sample.js"
    src.write_text(
        "function foo() {}\n"
        "const bar = () => {}\n"
        "let asyncFn = async function() {}\n"
        "class Widget {}\n",
        encoding="utf-8",
    )
    c = compute_file_complexity(str(src))
    assert c.function_count >= 3
    assert c.class_count == 1


def test_non_source_file_returns_zero_counts(tmp_path: Path) -> None:
    src = tmp_path / "notes.md"
    src.write_text("# Title\n\nSome notes.\n", encoding="utf-8")
    c = compute_file_complexity(str(src))
    assert c.function_count == 0
    assert c.class_count == 0
    assert c.loc == 3
    assert c.char_count > 0


def test_missing_file_returns_empty_complexity(tmp_path: Path) -> None:
    c = compute_file_complexity(str(tmp_path / "does_not_exist.py"))
    assert c.loc == 0
    assert c.char_count == 0
    assert c.function_count == 0
    assert c.class_count == 0
    assert c.cyclomatic is None
    assert c.halstead_volume is None


def test_blank_and_comment_lines_excluded(tmp_path: Path) -> None:
    src = tmp_path / "mixed.py"
    src.write_text(
        "# top comment\n"
        "\n"
        "def f():\n"
        "    # inline comment\n"
        "    return 1\n"
        "\n",
        encoding="utf-8",
    )
    c = compute_file_complexity(str(src))
    assert c.loc == 6
    assert c.loc_no_blanks_comments == 2  # def f(): and return 1


def test_python_cyclomatic_simple_function(tmp_path: Path) -> None:
    src = tmp_path / "simple.py"
    src.write_text("def f():\n    return 1\n", encoding="utf-8")
    c = compute_file_complexity(str(src))
    assert isinstance(c.cyclomatic, CyclomaticMetrics)
    assert c.cyclomatic.max == 1


def test_python_cyclomatic_branching_function(tmp_path: Path) -> None:
    src = tmp_path / "branching.py"
    src.write_text(
        "def f(x):\n"
        "    if x > 0:\n"
        "        return 1\n"
        "    elif x < 0:\n"
        "        return -1\n"
        "    else:\n"
        "        return 0\n",
        encoding="utf-8",
    )
    c = compute_file_complexity(str(src))
    assert isinstance(c.cyclomatic, CyclomaticMetrics)
    assert c.cyclomatic.max > 1


def test_python_syntax_error_returns_none(tmp_path: Path) -> None:
    src = tmp_path / "broken.py"
    src.write_text("def (:\n    pass\n", encoding="utf-8")
    c = compute_file_complexity(str(src))
    assert c.cyclomatic is None


def test_python_empty_file_returns_zero_metrics(tmp_path: Path) -> None:
    src = tmp_path / "module_only.py"
    src.write_text("x = 1\ny = 2\nprint(x + y)\n", encoding="utf-8")
    c = compute_file_complexity(str(src))
    assert isinstance(c.cyclomatic, CyclomaticMetrics)
    assert c.cyclomatic.max == 0
    assert c.cyclomatic.sum == 0


def test_non_python_file_returns_none_for_tier2(tmp_path: Path) -> None:
    src = tmp_path / "sample.js"
    src.write_text("function foo() { return 1; }\n", encoding="utf-8")
    c = compute_file_complexity(str(src))
    assert c.cyclomatic is None
    assert c.halstead_volume is None
