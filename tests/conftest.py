from __future__ import annotations

import pytest

from ai_friction_map.extraction import _reset_logged_unknown_tools
from ai_friction_map.windows import reset_boundary_clip_count


@pytest.fixture(autouse=True)
def _clear_extraction_unknown_tool_cache():
    # extraction._logged_unknown_tools is process-wide; without a reset
    # between tests, the "logged once" assertion depends on test ordering.
    _reset_logged_unknown_tools()
    yield
    _reset_logged_unknown_tools()


@pytest.fixture(autouse=True)
def _clear_boundary_clip_count():
    reset_boundary_clip_count()
    yield
    reset_boundary_clip_count()
