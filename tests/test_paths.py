from __future__ import annotations

import os
from pathlib import Path

from ai_friction_map.paths import canonicalize_path


def test_relative_resolves_against_cwd(tmp_path):
    # tmp_path is already canonical on the test platform.
    result = canonicalize_path("./storage.py", str(tmp_path))
    assert result == str(tmp_path / "storage.py")


def test_absolute_path_unchanged(tmp_path):
    # tmp_path is absolute and already resolved, so canonicalize is a no-op.
    abs_path = str(tmp_path / "storage.py")
    assert canonicalize_path(abs_path, "/any/other/cwd") == abs_path


def test_symlink_resolution(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.py"
    os.symlink(real, link)
    # Relative input through the link should resolve to the real file.
    assert canonicalize_path("link.py", str(tmp_path)) == str(real)


def test_missing_cwd_returns_raw(caplog):
    raw = "some/relative/path.py"
    with caplog.at_level("DEBUG", logger="ai_friction_map.paths"):
        assert canonicalize_path(raw, None) == raw


def test_dotdot_handling(tmp_path):
    a_b_c = tmp_path / "a" / "b" / "c"
    a_b_c.mkdir(parents=True)
    result = canonicalize_path("../other/file.py", str(a_b_c))
    assert result == str(tmp_path / "a" / "b" / "other" / "file.py")


def test_nonexistent_path_still_canonicalizes(tmp_path):
    # strict=False: resolving a path that doesn't exist is fine.
    result = canonicalize_path("does/not/exist.py", str(tmp_path))
    assert result == str(tmp_path / "does" / "not" / "exist.py")


def test_empty_cwd_treated_as_missing():
    raw = "relative.py"
    assert canonicalize_path(raw, "") == raw
