from __future__ import annotations

import pytest

from frictionmap.extraction import _reset_logged_unknown_tools
from frictionmap.windows import reset_boundary_clip_count

# SWE-bench adapter blindness tripwire (spec §9.1); used by tests/test_adapter_*.py.
from tests._adapter_fakes import fence  # noqa: F401


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
