"""Population registry, keyed on submission folder (spec §1).

Dispatch never keys on their format string: `openhands` and `trae` each serve
both population and excluded agents. The 20-entry SUBMISSION_META table is
vendored from their `scripts/config.py` (Zenodo 19351830) together with that
file's sha256, so registry drift is detectable without importing it (Q8 —
their module calls `mkdir()` and resolves `RESOLUTION_FILE` at import time).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

# sha256 of their scripts/config.py at vendoring time (spec §1).
THEIR_CONFIG_SHA256 = "8f6da96e829eb6b492e55a1f5569258c129987e3d988177a2ce9b3a8822e276e"

# Vendored verbatim (keys and values) from their SUBMISSION_META; s3_prefix dropped.
SUBMISSION_META: dict[str, dict[str, str]] = {
    "20240402_sweagent_claude3opus": {"agent": "SWE-agent", "llm": "claude-3-opus", "format": "swe-agent-old"},
    "20240402_sweagent_gpt4": {"agent": "SWE-agent", "llm": "gpt-4", "format": "swe-agent-old"},
    "20240620_sweagent_claude3.5sonnet": {"agent": "SWE-agent", "llm": "claude-3.5-sonnet", "format": "swe-agent-old"},
    "20240728_sweagent_gpt4o": {"agent": "SWE-agent", "llm": "gpt-4o", "format": "swe-agent-old"},
    "20250511_sweagent_lm_32b": {"agent": "SWE-agent", "llm": "lm-32b", "format": "swe-agent-new"},
    "20250522_sweagent_claude-4-sonnet-20250514": {"agent": "SWE-agent", "llm": "claude-4-sonnet",
                                                   "format": "swe-agent-new"},
    "20250804_codesweep_sweagent_kimi_k2_instruct": {"agent": "CodeSweep", "llm": "kimi-k2",
                                                     "format": "swe-agent-new"},
    "20241029_OpenHands-CodeAct-2.1-sonnet-20241022": {"agent": "OpenHands", "llm": "claude-3.5-sonnet",
                                                       "format": "openhands"},
    "20250415_openhands": {"agent": "OpenHands", "llm": "unknown", "format": "openhands"},
    "20250520_openhands_devstral_small": {"agent": "OpenHands", "llm": "devstral-small", "format": "openhands"},
    "20250524_openhands_claude_4_sonnet": {"agent": "OpenHands", "llm": "claude-4-sonnet", "format": "openhands"},
    "20250716_openhands_kimi_k2": {"agent": "OpenHands", "llm": "kimi-k2", "format": "openhands"},
    "20250807_openhands_gpt5": {"agent": "OpenHands", "llm": "gpt-5", "format": "openhands"},
    "20251127_openhands_claude-opus-4-5": {"agent": "OpenHands", "llm": "claude-opus-4.5",
                                           "format": "openhands-lossy"},
    "20250612_trae": {"agent": "Trae", "llm": "claude-4-sonnet+opus", "format": "trae"},
    "20250928_trae_doubao_seed_code": {"agent": "Trae", "llm": "doubao-seed-code", "format": "trae"},
    "20250616_Skywork-SWE-32B": {"agent": "Skywork", "llm": "qwen-32b", "format": "messages-xml"},
    "20251021_SalesforceAIResearch_SAGE_bash_only": {"agent": "SAGE", "llm": "claude-4.5+gpt-5",
                                                     "format": "messages-codeblock"},
    "20250804_epam-ai-run-claude-4-sonnet": {"agent": "EPAM-AI", "llm": "claude-4-sonnet", "format": "epam"},
    "20251205_sonar-foundation-agent_claude-opus-4-5": {"agent": "Sonar", "llm": "claude-opus-4.5",
                                                        "format": "sonar"},
}

# Our family identifiers (spec §1 population table, "Our family" column).
THOUGHT = "thought"            # `thought` field, swe-agent-old and swe-agent-new
EPAM = "epam"                  # `Thoughts` entries
SAGE = "sage"                  # `THOUGHT:` prefix
SONAR = "sonar"                # thinking blocks
TRAE = "trae"                  # `<think>` tags
THINK_TOOL = "think_tool"      # think-tool args

POPULATION: dict[str, str] = {
    "20240402_sweagent_claude3opus": THOUGHT,
    "20240402_sweagent_gpt4": THOUGHT,
    "20240620_sweagent_claude3.5sonnet": THOUGHT,
    "20240728_sweagent_gpt4o": THOUGHT,
    "20250511_sweagent_lm_32b": THOUGHT,
    "20250522_sweagent_claude-4-sonnet-20250514": THOUGHT,
    "20250804_codesweep_sweagent_kimi_k2_instruct": THOUGHT,
    "20250804_epam-ai-run-claude-4-sonnet": EPAM,
    "20251021_SalesforceAIResearch_SAGE_bash_only": SAGE,
    "20251205_sonar-foundation-agent_claude-opus-4-5": SONAR,
    "20250928_trae_doubao_seed_code": TRAE,
    "20250524_openhands_claude_4_sonnet": THINK_TOOL,
    "20250716_openhands_kimi_k2": THINK_TOOL,
}

EXCLUDED: dict[str, str] = {
    "20241029_OpenHands-CodeAct-2.1-sonnet-20241022": "undesignated narration (pre-reg §6)",
    "20250612_trae": "undesignated (`reasoning` key never populated)",
    "20250616_Skywork-SWE-32B": "undesignated narration",
    "20250520_openhands_devstral_small": "undesignated narration",
    "20250807_openhands_gpt5": "none (reasoning tokens withheld)",
    "20251127_openhands_claude-opus-4-5": "none (think-tool args severed; their `openhands-lossy`)",
    "20250415_openhands": "not in the paper's 19-agent population",
}

# The three SWE-agent old-format folders vs. new-format folders matter to the
# `thought` extractor (history layout differs); both read `trajectory[]` only.
SWEAGENT_OLD_FOLDERS = frozenset(k for k, m in SUBMISSION_META.items() if m["format"] == "swe-agent-old")
SWEAGENT_NEW_FOLDERS = frozenset(k for k, m in SUBMISSION_META.items() if m["format"] == "swe-agent-new")


class UnknownSubmission(KeyError):
    """Folder is not one of the 20 registry entries."""


class ExcludedSubmission(ValueError):
    """Folder is a registry entry outside the 13-agent population."""


@dataclass(frozen=True)
class Submission:
    folder: str
    family: str
    their_format: str
    agent: str
    llm: str


def resolve(folder: str) -> Submission:
    """Return the population entry for a submission folder, or refuse it.

    Raises ExcludedSubmission for the 7 excluded folders (even if present on
    disk) and UnknownSubmission for anything not in the vendored table.
    """
    if folder in EXCLUDED:
        raise ExcludedSubmission(f"{folder}: excluded — {EXCLUDED[folder]}")
    if folder not in POPULATION:
        raise UnknownSubmission(folder)
    meta = SUBMISSION_META[folder]
    return Submission(folder=folder, family=POPULATION[folder], their_format=meta["format"],
                      agent=meta["agent"], llm=meta["llm"])


def population_folders() -> list[str]:
    return sorted(POPULATION)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def their_config_drifted(config_path: Path) -> bool:
    """True if their scripts/config.py no longer matches the vendored hash.

    Reads the file as bytes only — never imports it (Q8).
    """
    return sha256_of(config_path) != THEIR_CONFIG_SHA256


def _self_check() -> None:
    assert len(SUBMISSION_META) == 20
    assert len(POPULATION) == 13 and len(EXCLUDED) == 7
    assert not set(POPULATION) & set(EXCLUDED)
    assert set(POPULATION) | set(EXCLUDED) == set(SUBMISSION_META)
    for folder in POPULATION:
        assert SUBMISSION_META[folder]["format"] != "openhands-lossy", folder


_self_check()
