"""unit → file mention tiers 1–2 (spec §8, Q10): synthetic cases plus the
fixture test against the pinned callable `attribute_thinking_blocks`
(src/frictionmap/attribution.py at e2d6db2) on own-corpus blocks drawn from
the anchor sessions — never from the sealed sample-manifest.csv."""
from __future__ import annotations

import hashlib
import os
import pathlib

import pytest

from swebench_adapter.mention import EXACT_PATH, UNIQUE_BASENAME, PATH_SUFFIXES, MentionIndex, attribute_mentions

REPO = pathlib.Path(__file__).resolve().parents[1]
PIN_SHA256 = "a96d7d053f85ce0c793782fafbdce80d090ea3c760e01ef027685438bc93f90e"   # git show e2d6db2:src/frictionmap/attribution.py
CORPUS_ROOT = pathlib.Path(os.environ.get("FRICTIONMAP_V2_CORPUS", "~/Projects/v2-sessions")).expanduser()


def test_vendored_suffixes_match_v1():
    from frictionmap.extraction import _PATH_SUFFIXES
    assert PATH_SUFFIXES == _PATH_SUFFIXES


def test_tier1_path_fragment_with_boundaries():
    paths = ["/proj/src/logger.py", "/proj/src/my_logger.py", "/proj/storage.py"]
    assert attribute_mentions("see src/logger.py here", paths) == (EXACT_PATH, ["/proj/src/logger.py"])
    assert attribute_mentions("see /proj/src/my_logger.py", paths) == (EXACT_PATH, ["/proj/src/my_logger.py"])
    # `-` is a boundary: my-storage.py must not match storage.py at tier 1, and tier 2 sees `my-storage.py`
    assert attribute_mentions("my-storage.py", paths) == (None, [])
    assert attribute_mentions("touch src/logger.py and src/my_logger.py", paths)[1] == [
        "/proj/src/logger.py", "/proj/src/my_logger.py"]


def test_tier2_unique_basename_and_ambiguity():
    paths = ["/a/x/util.py", "/a/y/util.py", "/a/main.py"]
    assert attribute_mentions("fix main.py", paths) == (UNIQUE_BASENAME, ["/a/main.py"])
    assert attribute_mentions("fix util.py", paths) == (None, [])          # two candidates → no attribution
    assert attribute_mentions("nothing here", paths) == (None, [])
    assert attribute_mentions("main.py", []) == (None, [])


def test_tier1_wins_over_tier2():
    paths = ["/a/main.py", "/a/b/other.py"]
    assert attribute_mentions("main.py and b/other.py", paths) == (EXACT_PATH, ["/a/b/other.py"])


def _session_files(anchor_list: pathlib.Path):
    from judge_harness.units import read_session_list
    return read_session_list(anchor_list)


@pytest.mark.skipif(not CORPUS_ROOT.is_dir(), reason="own corpus not available on this machine")
def test_fixture_against_pinned_attribute_thinking_blocks(fence):
    """For every thinking block in the anchor sessions: pinned tier-1/2 output
    == reimplementation on (block text, session touched-path set); pinned
    tier-3 blocks → no mention attribution (tier 3 is not rebuilt)."""
    import frictionmap.attribution as pinned_mod
    from frictionmap.attribution import attribute_thinking_blocks
    from frictionmap.parser import parse_sessions

    assert hashlib.sha256(pathlib.Path(pinned_mod.__file__).read_bytes()).hexdigest() == PIN_SHA256, \
        "attribution.py drifted from the e2d6db2 pin"
    anchors = _session_files(REPO / "methodology" / "anchor-sessions.txt")
    n_blocks = n_mention = 0
    for label in ("attune", "brownfield"):
        corpus = parse_sessions(CORPUS_ROOT / label)
        attribute_thinking_blocks(corpus)
        for sid, events in corpus.sessions.items():
            if sid not in anchors:
                continue
            touched = {p for ev in events for b in ev.blocks for p in b.file_paths}
            index = MentionIndex(touched)
            for ev in events:
                for b in ev.blocks:
                    if b.type != "thinking" or not b.thinking:
                        continue
                    n_blocks += 1
                    tier, paths = index.attribute(b.thinking)
                    if b.attribution.tier in (EXACT_PATH, UNIQUE_BASENAME):
                        n_mention += 1
                        assert (tier, paths) == (b.attribution.tier, list(b.attribution.file_paths)), (sid, b.thinking[:80])
                    else:
                        assert tier is None and paths == [], (sid, b.thinking[:80])
    assert n_blocks > 0 and n_mention > 0, (n_blocks, n_mention)
