from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from frictionmap.events import CodebaseMeta, FileFriction, Report
from frictionmap.render import load_template_assets, render_report


def _minimal_report() -> Report:
    meta = CodebaseMeta(
        name="testproj",
        session_count=1,
        file_count=1,
        thinking_block_count=1,
        total_event_count=3,
        generated_at="2026-04-26T00:00:00+00:00",
    )
    f = FileFriction(path="src/foo.py", name="foo.py", directory="src/")
    return Report(meta=meta, files=[f], session_titles={"abcd1234": "demo title"})


def test_render_substitutes_all_placeholders():
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(_minimal_report(), template, app_jsx, styles_css)
    for placeholder in ("{{DATA}}", "{{SESSION_TITLES}}", "{{APP_JSX}}", "{{STYLES_CSS}}"):
        assert placeholder not in rendered


def test_render_is_parseable_html():
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(_minimal_report(), template, app_jsx, styles_css)
    HTMLParser().feed(rendered)


def test_render_inlines_data_and_titles():
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(_minimal_report(), template, app_jsx, styles_css)
    assert "window.FRICTION_DATA = {" in rendered
    assert "window.SESSION_TITLES = {" in rendered

    data_match = re.search(r"window\.FRICTION_DATA = (\{.*?\});", rendered, re.DOTALL)
    assert data_match is not None
    data = json.loads(data_match.group(1))
    assert data["meta"]["name"] == "testproj"
    assert data["session_titles"]["abcd1234"] == "demo title"


def test_render_has_no_sibling_file_loads():
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(_minimal_report(), template, app_jsx, styles_css)
    assert "tweaks-panel.jsx" not in rendered
    assert '<script type="text/babel" src=' not in rendered
    assert '<link rel="stylesheet" href=' not in rendered
    assert '<script src="data.js"' not in rendered


def test_render_inlines_styles_and_app_jsx():
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(_minimal_report(), template, app_jsx, styles_css)
    assert "<style>" in rendered
    assert '<script type="text/babel">' in rendered
    assert "ReactDOM.createRoot" in rendered
