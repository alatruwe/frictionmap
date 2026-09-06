"""Prompt assembly against the three frozen files, with synthetic thinking text."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from judge_harness.prompts import (
    MARKER, PLACEHOLDER, PROMPT_DIR, PROMPT_FILES, Prompt, PromptError,
    assemble, load_prompt, prompt_for_pass, split_prompt,
)


@pytest.mark.parametrize("name", sorted(PROMPT_FILES))
def test_frozen_files_split_and_hash(name):
    prompt = load_prompt(name)
    raw = (PROMPT_DIR / PROMPT_FILES[name]).read_bytes()
    text = raw.decode("utf-8")
    marker_at = text.index("\n" + MARKER + "\n") + 1
    # system is byte-identical to everything above the marker line
    assert prompt.system == text[:marker_at]
    assert MARKER not in prompt.system
    assert PLACEHOLDER not in prompt.system
    assert prompt.user_template.count(PLACEHOLDER) == 1
    assert prompt.system + MARKER + "\n" + prompt.user_template == text
    assert prompt.sha256 == hashlib.sha256(raw).hexdigest()


def test_assemble_substitutes_once_and_never_rescans():
    prompt = Prompt(name="x", path=Path("x"), sha256="0", system="SYS\n",
                    user_template=f"<t>\n{PLACEHOLDER}\n</t>")
    thinking = f"wait {PLACEHOLDER} actually"
    system, user = assemble(prompt, thinking)
    assert system == "SYS\n"
    assert user == f"<t>\nwait {PLACEHOLDER} actually\n</t>"
    assert user.count(PLACEHOLDER) == 1  # the one inside the thinking text, untouched


def test_split_rejects_malformed_files():
    with pytest.raises(PromptError):
        split_prompt(f"a\n{PLACEHOLDER}\n")                    # no marker
    with pytest.raises(PromptError):
        split_prompt(f"a\n{MARKER}\nb\n{MARKER}\n{PLACEHOLDER}")  # two markers
    with pytest.raises(PromptError):
        split_prompt(f"a\n{MARKER}\nno placeholder")           # zero placeholders
    with pytest.raises(PromptError):
        split_prompt(f"{PLACEHOLDER}\n{MARKER}\n{PLACEHOLDER}")  # placeholder above marker


def test_pass_to_prompt_mapping():
    assert prompt_for_pass("v1-pass1") == prompt_for_pass("v1-pass3") == "v1"
    assert prompt_for_pass("paraphrase-a") == "paraphrase-a"
    with pytest.raises(PromptError):
        prompt_for_pass("v1-pass4")
