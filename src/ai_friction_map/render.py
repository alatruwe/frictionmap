"""HTML render layer — substitute Report data + bundled assets into the template.

Single self-contained `report.html` output. JSX and CSS are inlined
into the template (not loaded as sibling files) so the report works
under `file://` without browser CORS blocks.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from importlib.resources import files

from ai_friction_map.events import Report


def load_template_assets() -> tuple[str, str, str]:
    """Read the three bundled template assets from the package."""
    pkg = files("ai_friction_map")
    template = pkg.joinpath("templates/report.html.template").read_text(encoding="utf-8")
    app_jsx = pkg.joinpath("templates/app.jsx").read_text(encoding="utf-8")
    styles_css = pkg.joinpath("templates/styles.css").read_text(encoding="utf-8")
    return template, app_jsx, styles_css


def render_report(report: Report, template: str, app_jsx: str, styles_css: str) -> str:
    """Substitute the four placeholders into the template and return HTML.

    Placeholders: {{DATA}}, {{SESSION_TITLES}}, {{APP_JSX}}, {{STYLES_CSS}}.
    Order matters only for {{DATA}}/{{SESSION_TITLES}} vs {{APP_JSX}} —
    the JSX could legally contain those literal strings (it doesn't), so
    inline {{DATA}}/{{SESSION_TITLES}} first to avoid that surface.
    """
    data_json = json.dumps(asdict(report), default=str)
    titles_json = json.dumps(report.session_titles)
    return (
        template
        .replace("{{DATA}}", data_json)
        .replace("{{SESSION_TITLES}}", titles_json)
        .replace("{{STYLES_CSS}}", styles_css)
        .replace("{{APP_JSX}}", app_jsx)
    )
