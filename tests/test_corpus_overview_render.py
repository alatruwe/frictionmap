"""Smoke tests for the corpus-overview v2 left panel.

Fixtures in tests/fixtures/corpus_overview/ encode the four corpus shapes the
decision tree branches on: outlier_heavy, healthy, calm, empty. The fixtures
are pre-serialized to the post-asdict shape consumed by window.FRICTION_DATA,
so these tests substitute them straight into the template (bypassing the
Report dataclass round-trip).

These are smoke tests, not behavior tests. They verify that:
  - fixture data inlines correctly into window.FRICTION_DATA
  - the new component identifiers reach the bundled app.jsx
  - rendered output stays parseable HTML with no leftover placeholders

They do NOT verify that classifyCorpus fires the right mode at runtime —
Babel transpiles in the browser, not at template-render time, so DOM-level
assertions need a JS runner / headless browser (out of scope per handoff).
Behavioral verification of the decision tree is via manual smoke against
/tmp/corpus_*.html, or via the Python parallel reference walk in classify
exercised below.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from frictionmap.render import load_template_assets


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "corpus_overview"
FIXTURE_NAMES = ["outlier_heavy", "healthy", "calm", "empty"]


def _render_fixture(name: str) -> str:
    """Substitute a fixture JSON directly into the bundled template.

    Bypasses render_report's asdict() round-trip — fixtures are already the
    post-asdict shape, so this exercises the same substitution path that
    the production renderer uses without forcing fixture authors to
    construct nested dataclasses.
    """
    fixture_path = FIXTURES_DIR / f"{name}.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    titles = data.get("session_titles", {})

    template, app_jsx, styles_css = load_template_assets()
    return (
        template
        .replace("{{DATA}}", json.dumps(data, indent=2))
        .replace("{{SESSION_TITLES}}", json.dumps(titles, indent=2))
        .replace("{{STYLES_CSS}}", styles_css)
        .replace("{{APP_JSX}}", app_jsx)
    )


def _extract_friction_data(rendered: str) -> dict:
    match = re.search(r"window\.FRICTION_DATA = (\{.*?\});", rendered, re.DOTALL)
    assert match is not None, "window.FRICTION_DATA assignment not found"
    return json.loads(match.group(1))


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_fixture_renders_without_placeholders(fixture_name: str):
    rendered = _render_fixture(fixture_name)
    for placeholder in ("{{DATA}}", "{{SESSION_TITLES}}", "{{APP_JSX}}", "{{STYLES_CSS}}"):
        assert placeholder not in rendered
    HTMLParser().feed(rendered)


def test_corpus_overview_component_present():
    rendered = _render_fixture("healthy")
    for ident in ("CorpusOverview", "classifyCorpus", "StandoutsStrip", "TreemapView"):
        assert ident in rendered, f"{ident} missing from bundled app.jsx"


def test_outlier_heavy_fixture_inlines_standout_filenames():
    """The two files the cliff-scan should promote must be present in the
    inlined data (necessary precondition for the Standouts strip to render
    them). This doesn't prove the strip renders — it proves the data the
    strip reads is what we expect."""
    data = _extract_friction_data(_render_fixture("outlier_heavy"))
    paths = {f["path"] for f in data["files"]}
    assert "findings.md" in paths
    assert "investigate.py" in paths


def test_empty_fixture_triggers_no_signal_clause():
    """Empty mode fires via the 'no scores >= 0.10' clause when the file
    list is non-empty. Verify the data shape reflects that — every file
    score is below the FRICTION_FLOOR threshold."""
    data = _extract_friction_data(_render_fixture("empty"))
    assert len(data["files"]) > 0
    assert all(f["score"] < 0.10 for f in data["files"])


def test_calm_fixture_has_few_meaningful_files():
    """Calm mode fires when meaningful (score >= 0.10) files are between 1
    and TREEMAP_MIN_FILES (10). Verify the fixture data lands in that band."""
    data = _extract_friction_data(_render_fixture("calm"))
    meaningful = [f for f in data["files"] if f["score"] >= 0.10]
    assert 1 <= len(meaningful) < 10


def test_healthy_fixture_has_enough_meaningful_files():
    """Healthy mode requires >= TREEMAP_MIN_FILES (10) meaningful files."""
    data = _extract_friction_data(_render_fixture("healthy"))
    meaningful = [f for f in data["files"] if f["score"] >= 0.10]
    assert len(meaningful) >= 10
