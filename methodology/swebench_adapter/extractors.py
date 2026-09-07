"""Family extractors (spec §3, §9.4): loaded file → ordered event sequence →
step-anchored units with provenance.

Every extractor emits `Emission` / `ActionStep` events in document order for
the family-agnostic engine (anchoring.py). Units carry: submission, file,
instance id, family, `rule_version` (SAGE `sage-1`, Trae `trae-b-1`),
container, emission_kind, fragment offsets, `anchor_files` from the anchor's
path extraction, and per-fragment riders (Trae first-closer offset, Sonar
`num_tokens`).

Build-level note on delimiters: boundary rules define a span; the delimiters
themselves are not reasoning text. SAGE units exclude the leading `THOUGHT:`
label; Trae units exclude the boundary `<think>` opener and the final
`</think>` closer — interior content (stray closers, abandoned-call XML per
D1) is kept verbatim. Offsets stored on Trae fragments are relative to the
message content so the message span is recoverable.

Gate states (checkpoint 2026-09-06): EPAM §7.1 gate passed — built. Trae
against `trae-b-1`, SAGE against `sage-1`.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swebench_adapter import registry
from swebench_adapter.anchoring import ActionStep, AnchoringResult, Emission, Event, Unit, anchor
from swebench_adapter.discovery import instance_stem
from swebench_adapter.loaders import Loaded
from swebench_adapter.paths import (Action, OldSweAgentState, action_from_args, action_from_bash,
                                    parse_epam_input_text, sweagent_new_action, sweagent_old_action,
                                    trae_actions)

SAGE_RULE_VERSION = "sage-1"
TRAE_RULE_VERSION = "trae-b-1"

# §2.4 (D3): documented harness template prefixes, per family. SWE-agent families only;
# do not generalize by heuristic — additions come by documented amendment.
HARNESS_TEMPLATE_PREFIXES: dict[str, tuple[str, ...]] = {
    registry.THOUGHT: ("Exit due to",),
}

_SAGE_BASH_FENCE_RE = re.compile(r"```bash[ \t]*\n(.*?)```", re.S)
_FENCE_LANG_RE = re.compile(r"```([A-Za-z0-9_+-]*)")


@dataclass(frozen=True)
class UnitRecord:
    unit: Unit
    unit_index: int                         # ordinal within the trajectory
    submission: str
    file: str
    instance_id: str
    family: str
    rule_version: str | None
    container: str
    anchor_files: tuple[str, ...]

    @property
    def text(self) -> str:
        return self.unit.text

    @property
    def emission_kind(self) -> str:
        return self.unit.emission_kind

    def to_dict(self) -> dict[str, Any]:
        u = self.unit
        return {
            "submission": self.submission, "file": self.file, "instance_id": self.instance_id,
            "unit_index": self.unit_index, "family": self.family, "rule_version": self.rule_version,
            "container": self.container, "emission_kind": u.emission_kind, "terminal": u.terminal,
            "anchor_step": u.anchor_step, "anchor_container": u.anchor_container,
            "anchor_files": list(self.anchor_files), "fragment_count": u.fragment_count,
            "fragments": [{"start": f.start, "end": f.end, "container": f.container, "kind": f.kind, **f.meta}
                          for f in u.fragments],
            "text": u.text,
        }


@dataclass
class TrajectoryResult:
    submission: str
    path: Path
    instance_id: str
    family: str
    rule_version: str | None
    container: str
    structure_present: bool                 # §6 unit-level failure iff False (think-tool: always True)
    units: list[UnitRecord]
    anchoring: AnchoringResult
    actions: list[Action]                   # every action across action steps, in order
    free_standing_texts: list[str]          # raw designated text of action-less containers (§5.7 census)
    notes: Counter                          # family-specific structural counters (audit §5.5–5.6)


# ---------------------------------------------------------------------------
# per-family event builders: (data) -> (events, structure_present, free_standing_texts, notes)
# ---------------------------------------------------------------------------

def _events_thought(data: Any, folder: str) -> tuple[list[Event], bool, list[str], Counter]:
    steps = data.get("trajectory") or []
    old = folder in registry.SWEAGENT_OLD_FOLDERS
    state = OldSweAgentState()
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    structure = any(isinstance(s, dict) and "thought" in s for s in steps)
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        thought = step.get("thought")
        action = (step.get("action") or "")
        if isinstance(thought, str):
            events.append(Emission(thought, container=i))
        if action.strip():
            act = sweagent_old_action(action, state) if old else sweagent_new_action(action)
            events.append(ActionStep(container=i, actions=(act,)))
        else:
            notes["text_only_steps"] += 1
            if isinstance(thought, str):
                free.append(thought)
    notes["old_edits_without_open_file"] = state.edits_without_open_file
    return events, structure, free, notes


def _events_epam(data: Any) -> tuple[list[Event], bool, list[str], Counter]:
    entries = list(data[0].values())        # document order; never sorted (§2.7)
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    structure = False
    for i, e in enumerate(entries):
        author = e.get("author_name")
        if author == "Thoughts":
            structure = True
            msg = e.get("message")
            text = msg if isinstance(msg, str) else ""
            events.append(Emission(text, container=i))
            free.append(text)
        else:
            args = parse_epam_input_text(e.get("input_text", "")) if isinstance(e.get("input_text"), str) else None
            if args is None:
                notes["epam_input_text_unparsed"] += 1
            events.append(ActionStep(container=i, actions=(action_from_args(str(author), args, raw=str(author)),)))
    return events, structure, free, notes


def sage_emission(content: str) -> tuple[str | None, dict[str, Any]]:
    """`sage-1`: first `THOUGHT:` through the first ```bash opener. Returns
    (text-after-label or None, structural facts for the audit)."""
    i = content.find("THOUGHT:")
    langs = _FENCE_LANG_RE.findall(content)[0::2]
    bash_idx = next((k for k, lang in enumerate(langs) if lang == "bash"), None)
    facts = {
        "thought_offset": i,
        "non_bash_fences_before_bash": bash_idx if bash_idx is not None else len(langs),
        "missing_bash_fence": bash_idx is None,
    }
    if i < 0:
        return None, facts
    end = content.find("```bash")
    span = content[i + len("THOUGHT:"): end if end >= 0 else len(content)]
    facts["span_start"] = i + len("THOUGHT:")
    facts["span_end"] = end if end >= 0 else len(content)
    return span, facts


def _events_sage(data: Any) -> tuple[list[Event], bool, list[str], Counter]:
    messages = data.get("messages") or []
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    structure = False
    for i, m in enumerate(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant" or not isinstance(m.get("content"), str):
            continue
        content = m["content"]
        notes["assistant_messages"] += 1
        text, facts = sage_emission(content)
        if facts["thought_offset"] >= 0:
            structure = True
            notes["thought_offset_nonzero"] += facts["thought_offset"] != 0
        else:
            notes["thought_absent"] += 1
        notes["non_bash_fences_before_bash_msgs"] += facts["non_bash_fences_before_bash"] > 0 and not facts[
            "missing_bash_fence"]
        notes["missing_bash_fence"] += facts["missing_bash_fence"]
        bodies = _SAGE_BASH_FENCE_RE.findall(content)
        if text is not None:
            events.append(Emission(text, container=i, meta={"span_start": facts["span_start"],
                                                           "span_end": facts["span_end"]}))
            if not bodies:
                free.append(text)
        if bodies:
            events.append(ActionStep(container=i, actions=tuple(action_from_bash(b) for b in bodies)))
    return events, structure, free, notes


def _events_sonar(data: Any) -> tuple[list[Event], bool, list[str], Counter]:
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    structure = False
    for i, m in enumerate(data):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        texts: list[str] = []
        for b in m.get("blocks") or []:
            if isinstance(b, dict) and b.get("block_type") == "thinking":
                structure = True
                c = b.get("content")
                text = c if isinstance(c, str) else ""
                meta = {"num_tokens": b.get("num_tokens")} if "num_tokens" in b else {}
                events.append(Emission(text, container=i, meta=meta))
                texts.append(text)
        actions: list[Action] = []
        for tc in (m.get("additional_kwargs") or {}).get("tool_calls") or []:
            fn = (tc or {}).get("function") or {}
            name = str(fn.get("name"))
            args = _json_args(fn.get("arguments"))
            if args is None:
                notes["tool_args_unparsed"] += 1
            actions.append(action_from_args(name, args, raw=name))
        if actions:
            events.append(ActionStep(container=i, actions=tuple(actions)))
        else:
            free.extend(texts)
    return events, structure, free, notes


def trae_emission(content: str) -> tuple[str | None, dict[str, Any]]:
    """`trae-b-1`: `<think>` opener through the last `</think>`; interior kept
    verbatim (stray closers, abandoned-call XML). Facts carry the first-closer
    offset (option A recoverable) and closer count."""
    start = content.find("<think>")
    if start < 0:
        return None, {"closers": 0}
    body_start = start + len("<think>")
    closers = [m.start() for m in re.finditer(r"</think>", content)]
    closers = [c for c in closers if c >= body_start]
    facts: dict[str, Any] = {"closers": len(closers), "span_start": body_start}
    if not closers:
        facts["unclosed"] = True
        facts["span_end"] = len(content)
        return content[body_start:], facts
    facts["span_end"] = closers[-1]
    facts["first_closer_offset"] = closers[0]
    return content[body_start:closers[-1]], facts


def _events_trae(data: Any) -> tuple[list[Event], bool, list[str], Counter]:
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    structure = False
    for i, m in enumerate(data):
        if not isinstance(m, dict) or m.get("role") != "assistant" or not isinstance(m.get("content"), str):
            continue
        content = m["content"]
        notes["assistant_messages"] += 1
        text, facts = trae_emission(content)
        actions = trae_actions(content)
        if text is not None:
            structure = True
            notes["multi_closer_messages"] += facts["closers"] > 1
            notes["unclosed_think"] += bool(facts.get("unclosed"))
            meta = {k: v for k, v in facts.items() if k in ("span_start", "span_end", "first_closer_offset", "closers")}
            events.append(Emission(text, container=i, meta=meta))
            if not actions:
                free.append(text)
        if actions:
            events.append(ActionStep(container=i, actions=tuple(actions)))
    return events, structure, free, notes


def _events_think_tool(data: Any) -> tuple[list[Event], bool, list[str], Counter]:
    events: list[Event] = []
    free: list[str] = []
    notes: Counter = Counter()
    for i, m in enumerate(data):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        thinks: list[str] = []
        actions: list[Action] = []
        for tc in m.get("tool_calls") or []:
            fn = (tc or {}).get("function") or {}
            name = str(fn.get("name"))
            args = _json_args(fn.get("arguments"))
            if name == "think":
                if args is None:
                    notes["think_args_unparsed"] += 1
                    continue
                t = args.get("thought")
                thinks.append(t if isinstance(t, str) else "")
            else:
                if args is None:
                    notes["tool_args_unparsed"] += 1
                actions.append(action_from_args(name, args, raw=name))
        for t in thinks:
            events.append(Emission(t, container=i))
        if actions:
            events.append(ActionStep(container=i, actions=tuple(actions)))
            if thinks:
                notes["think_with_action_same_message"] += 1
        else:
            free.extend(thinks)
    return events, True, free, notes          # unit-level failure n/a for think-tool (§6)


def _json_args(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

_CONTAINER = {
    registry.THOUGHT: "trajectory[].thought",
    registry.EPAM: "Thoughts entry .message",
    registry.SAGE: "assistant message content (THOUGHT: … ```bash)",
    registry.SONAR: "assistant blocks[] block_type=thinking .content",
    registry.TRAE: "assistant message content (<think> … </think>)",
    registry.THINK_TOOL: "tool_calls[function.name=think].arguments.thought",
}
_RULE_VERSION = {registry.SAGE: SAGE_RULE_VERSION, registry.TRAE: TRAE_RULE_VERSION}


def build_events(loaded: Loaded) -> tuple[list[Event], bool, list[str], Counter]:
    fam = loaded.submission.family
    if fam == registry.THOUGHT:
        return _events_thought(loaded.data, loaded.submission.folder)
    if fam == registry.EPAM:
        return _events_epam(loaded.data)
    if fam == registry.SAGE:
        return _events_sage(loaded.data)
    if fam == registry.SONAR:
        return _events_sonar(loaded.data)
    if fam == registry.TRAE:
        return _events_trae(loaded.data)
    if fam == registry.THINK_TOOL:
        return _events_think_tool(loaded.data)
    raise ValueError(fam)


def extract(loaded: Loaded) -> TrajectoryResult:
    """Full extraction for one loaded file: events → anchored units → provenance."""
    fam = loaded.submission.family
    events, structure, free, notes = build_events(loaded)
    result = anchor(events, harness_prefixes=HARNESS_TEMPLATE_PREFIXES.get(fam, ()))
    iid = instance_stem(loaded.path)
    records = [
        UnitRecord(unit=u, unit_index=k, submission=loaded.submission.folder, file=loaded.path.name,
                   instance_id=iid, family=fam, rule_version=_RULE_VERSION.get(fam), container=_CONTAINER[fam],
                   anchor_files=tuple(p for a in u.actions for p in a.paths))
        for k, u in enumerate(result.units)
    ]
    actions = [a for ev in events if isinstance(ev, ActionStep) for a in ev.actions]
    return TrajectoryResult(submission=loaded.submission.folder, path=loaded.path, instance_id=iid, family=fam,
                            rule_version=_RULE_VERSION.get(fam), container=_CONTAINER[fam],
                            structure_present=structure, units=records, anchoring=result, actions=actions,
                            free_standing_texts=free, notes=notes)
