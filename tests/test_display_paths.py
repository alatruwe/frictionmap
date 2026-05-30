"""Issue #1 — no machine-identifying absolute path in the shipped artifact.

Units for the three display helpers (derive_strip_root / display_path /
redact_prose) plus integration gates over a rendered report: the acceptance
grep (no /Users, /home, or username anywhere in the HTML), consistency-set
integrity (an `also touches` jump target survives as a file key), the
home-prefix backstop for off-repo survivors, and excerpt-prose redaction.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from frictionmap.events import Highlight
from frictionmap.parser import parse_sessions
from frictionmap.render import load_template_assets, render_report
from frictionmap.report import (
    assemble_report,
    derive_strip_root,
    display_path,
    redact_prose,
    relativize_report,
)
from tests._factories import assistant, jsonl

# --- derive_strip_root -------------------------------------------------------


def test_derive_strip_root_local_simple_name() -> None:
    root = derive_strip_root(
        "-Users-testuser-Projects-attune",
        ["/Users/testuser/Projects/attune/src/a.py"],
    )
    assert root == "/Users/testuser/Projects/attune"


def test_derive_strip_root_repairs_dash_in_project_name() -> None:
    # The slug is ambiguous (ai/friction/map vs ai-friction-map); the real
    # file path disambiguates the dash boundary.
    root = derive_strip_root(
        "-Users-testuser-Projects-ai-friction-map",
        ["/Users/testuser/Projects/ai-friction-map/src/cli.py"],
    )
    assert root == "/Users/testuser/Projects/ai-friction-map"


def test_derive_strip_root_none_when_no_path_aligns() -> None:
    # Corpus recorded on another machine: the slug names this machine's import
    # dir, but the recorded paths carry a different username → no alignment.
    root = derive_strip_root(
        "-Users-localuser-Projects-demo",
        ["/Users/otheruser/projects/demo/api/foo.py"],
    )
    assert root is None


def test_derive_strip_root_empty_slug() -> None:
    assert derive_strip_root("", ["/Users/x/Projects/demo/a.py"]) is None


# --- display_path ------------------------------------------------------------


def test_display_path_strips_under_root() -> None:
    root = "/Users/testuser/Projects/demo"
    assert display_path(f"{root}/src/foo.py", root) == "src/foo.py"


def test_display_path_root_level_file_directory_is_empty() -> None:
    root = "/Users/testuser/Projects/demo"
    # FileFriction.directory is str(parent) + "/"; a repo-root file's directory
    # is exactly root + "/" → strips to "".
    assert display_path(f"{root}/", root) == ""


def test_display_path_backstop_redacts_offrepo_home() -> None:
    root = "/Users/testuser/Projects/demo"
    # An off-repo sibling the root doesn't cover still must not leak a home dir.
    assert display_path("/Users/testuser/Documents/notes.md", root) == "~/Documents/notes.md"


def test_display_path_backstop_redacts_foreign_home_and_linux() -> None:
    assert display_path("/Users/someoneelse/x/a.py", None) == "~/x/a.py"
    assert display_path("/home/bob/x/a.py", None) == "~/x/a.py"


def test_display_path_passthrough_for_non_home_non_root() -> None:
    # A path the root isn't a prefix of, carrying no home prefix, is untouched
    # (this is what keeps the /proj/... test fixtures intact).
    assert display_path("/proj/a.py", "/Users/x/Projects/demo") == "/proj/a.py"


# --- redact_prose ------------------------------------------------------------


def test_redact_prose_noop_without_home() -> None:
    text = "no paths here, just words"
    h = [Highlight(start=3, end=8, marker="paths")]
    new_text, new_h = redact_prose(text, h)
    assert new_text == text
    assert new_h == h


def test_redact_prose_redacts_and_remaps_highlight_after_path() -> None:
    # The trap: a marker AFTER an inline absolute path. Redaction shortens the
    # text, so the highlight offset must shift or it bolds the wrong chars.
    text = "see /Users/bob/Projects/x/a.py now wait"
    start = text.index("wait")
    new_text, new_h = redact_prose(text, [Highlight(start=start, end=start + 4, marker="wait")])
    assert "/Users/" not in new_text
    assert new_text == "see ~/Projects/x/a.py now wait"
    # The remapped span still lands exactly on the marker word.
    assert new_text[new_h[0].start:new_h[0].end] == "wait"


# --- integration: relativize + render ----------------------------------------

_SLUG = "-Users-testuser-Projects-demo"
_ROOT = "/Users/testuser/Projects/demo"


def _relativized_report(tmp_path: Path):
    """Build a report on a corpus rooted under _ROOT, with one off-repo survivor
    and an inline foreign-looking home path in thinking prose, then relativize.
    """
    records = [
        assistant("s1", "u1", [
            {"type": "thinking",
             "thinking": (
                 f"wait, looking at {_ROOT}/src/foo.py — and a stray "
                 f"/Users/testuser/secrets/key.txt — actually, let me reconsider."
             )},
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": f"{_ROOT}/src/foo.py",
                       "old_string": "a", "new_string": "b"}},
        ]),
        # Off-repo survivor: the root doesn't cover ~/Documents; backstop must.
        assistant("s1", "u2", [
            {"type": "tool_use", "id": "t2", "name": "Edit",
             "input": {"file_path": "/Users/testuser/Documents/notes.md",
                       "old_string": "x", "new_string": "y"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    corpus = parse_sessions(tmp_path)
    report = assemble_report(corpus, sessions_dir_name=_SLUG)
    root = derive_strip_root(_SLUG, [f.path for f in report.files])
    return relativize_report(report, root), root


def test_meta_name_from_derived_root(tmp_path: Path) -> None:
    report, root = _relativized_report(tmp_path)
    assert root == _ROOT
    assert report.meta.name == "demo"


def test_repo_file_displays_relative(tmp_path: Path) -> None:
    report, _ = _relativized_report(tmp_path)
    paths = {f.path for f in report.files}
    assert "src/foo.py" in paths


def test_offrepo_survivor_home_redacted(tmp_path: Path) -> None:
    report, _ = _relativized_report(tmp_path)
    paths = {f.path for f in report.files}
    assert "~/Documents/notes.md" in paths
    assert not any(p.startswith("/Users/") for p in paths)


def test_consistency_set_jump_target_is_a_file_key(tmp_path: Path) -> None:
    # Every attribution.file_paths entry (an `also touches` jump target) must
    # exist as a FileFriction.path key after relativization, or cross-file
    # navigation breaks.
    report, _ = _relativized_report(tmp_path)
    keys = {f.path for f in report.files}
    seen_any = False
    for f in report.files:
        for ex in f.excerpts:
            if ex.attribution:
                for p in ex.attribution.file_paths:
                    seen_any = True
                    assert p in keys, f"jump target {p!r} not a file key"
    assert seen_any, "fixture produced no attributed excerpts"


def test_excerpt_prose_home_redacted(tmp_path: Path) -> None:
    report, _ = _relativized_report(tmp_path)
    texts = [ex.text for f in report.files for ex in f.excerpts]
    assert texts, "fixture produced no excerpts"
    blob = "\n".join(texts)
    assert "/Users/" not in blob
    assert "testuser" not in blob
    assert "~/secrets/key.txt" in blob


def test_rendered_html_has_no_home_dir_anywhere(tmp_path: Path) -> None:
    # The acceptance gate: grep the FULL rendered HTML (payload included) for
    # any home identity. Zero hits.
    report, _ = _relativized_report(tmp_path)
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(report, template, app_jsx, styles_css)

    assert "/Users/" not in rendered
    assert "/home/" not in rendered
    assert "testuser" not in rendered

    # Sanity: the payload is present and the relative path actually shipped.
    data_match = re.search(r"window\.FRICTION_DATA = (\{.*?\});", rendered, re.DOTALL)
    assert data_match is not None
    data = json.loads(data_match.group(1))
    shipped = {f["path"] for f in data["files"]}
    assert "src/foo.py" in shipped
    assert "~/Documents/notes.md" in shipped
