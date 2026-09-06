"""Frozen judge prompts: load, split, substitute. Read-only over judge-prompts/.

Per judge-prompts/README.md: text above the `=== USER TURN ===` line is the
system prompt, sent verbatim; the template below it takes the unit's thinking
text at `{{THINKING_TEXT}}`. Nothing else is modified. A file that does not
have exactly one marker line and exactly one placeholder is a defect in a
frozen artifact — raise, never repair.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from judge_harness import REPO_ROOT

MARKER = "=== USER TURN ==="
PLACEHOLDER = "{{THINKING_TEXT}}"
PROMPT_DIR = REPO_ROOT / "methodology" / "judge-prompts"
PROMPT_FILES = {
    "v1": "v1.md",
    "paraphrase-a": "v1-paraphrase-a.md",
    "paraphrase-b": "v1-paraphrase-b.md",
}
# pass_id -> prompt name. The three v1 passes are the §5 rerun-stability check.
PASS_PROMPTS = {
    "v1-pass1": "v1",
    "v1-pass2": "v1",
    "v1-pass3": "v1",
    "paraphrase-a": "paraphrase-a",
    "paraphrase-b": "paraphrase-b",
}


class PromptError(ValueError):
    """A frozen prompt file does not have the shape README.md binds."""


@dataclass(frozen=True)
class Prompt:
    name: str
    path: Path
    sha256: str
    system: str          # bytes above the marker line, verbatim
    user_template: str   # everything after the marker line


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_prompt(text: str) -> tuple[str, str]:
    """Split at the single marker line. System keeps everything before it,
    including its trailing newline(s); the template is everything after."""
    lines = text.split("\n")
    marker_lines = [i for i, line in enumerate(lines) if line == MARKER]
    if len(marker_lines) != 1:
        raise PromptError(f"expected exactly one {MARKER!r} line, found {len(marker_lines)}")
    idx = marker_lines[0]
    system = "\n".join(lines[:idx]) + "\n" if idx > 0 else ""
    template = "\n".join(lines[idx + 1:])
    if template.count(PLACEHOLDER) != 1:
        raise PromptError(
            f"expected exactly one {PLACEHOLDER!r} below the marker, "
            f"found {template.count(PLACEHOLDER)}"
        )
    if PLACEHOLDER in system:
        raise PromptError(f"{PLACEHOLDER!r} appears above the marker")
    return system, template


def load_prompt(name: str, prompt_dir: Path = PROMPT_DIR) -> Prompt:
    if name not in PROMPT_FILES:
        raise PromptError(f"unknown prompt {name!r}; known: {sorted(PROMPT_FILES)}")
    path = prompt_dir / PROMPT_FILES[name]
    raw = path.read_bytes()
    system, template = split_prompt(raw.decode("utf-8"))
    return Prompt(name=name, path=path, sha256=sha256_bytes(raw),
                  system=system, user_template=template)


def prompt_for_pass(pass_id: str) -> str:
    if pass_id not in PASS_PROMPTS:
        raise PromptError(f"unknown pass {pass_id!r}; known: {sorted(PASS_PROMPTS)}")
    return PASS_PROMPTS[pass_id]


def assemble(prompt: Prompt, thinking_text: str) -> tuple[str, str]:
    """(system, user) for one unit. Single substitution; the inserted text is
    never rescanned, so a placeholder inside a thinking block stays literal."""
    return prompt.system, prompt.user_template.replace(PLACEHOLDER, thinking_text, 1)
