"""Structural audit (spec §5, §9.6): outputs 1–7 on the §5 audit sample,
after the extractors. Descriptive only — it may not change the unit
definition, join outcome data, or rank anything. Same fence as recon:
structure only; no resolution contact; no marker counts; no signal values;
no v1 code over trajectories. "Words" = whitespace-split tokens.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from swebench_adapter import registry
from swebench_adapter.anchoring import TERMINAL
from swebench_adapter.discovery import discover, instance_stem
from swebench_adapter.extractors import HARNESS_TEMPLATE_PREFIXES, TrajectoryResult, extract
from swebench_adapter.loaders import FileLevelFailure, load_trajectory_file
from swebench_adapter.mention import MentionIndex
from swebench_adapter.sample import audit_sample
from swebench_adapter.seam import SAGE_INSPECTION, TRAE_INSPECTION, _table

FAMILY_LABEL = {registry.THOUGHT: "`thought` field", registry.EPAM: "`Thoughts` entries", registry.SAGE: "`THOUGHT:` prefix",
                registry.SONAR: "thinking blocks", registry.TRAE: "`<think>` tags", registry.THINK_TOOL: "think-tool args"}


def _pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100.0 * n / d:.1f}%"


def _q(xs: list[int], p: float) -> int:
    if not xs:
        return 0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, round(p * (len(s) - 1))))
    return s[k]


def _dist(xs: list[int]) -> list:
    if not xs:
        return [0, "—", "—", "—", "—", "—", "—", "—"]
    return [len(xs), min(xs), _q(xs, .25), _q(xs, .5), _q(xs, .75), _q(xs, .9), max(xs), f"{statistics.mean(xs):.0f}"]


@dataclass
class AgentAudit:
    folder: str
    family: str
    n_sampled: int = 0
    n_loaded: int = 0
    results: list[TrajectoryResult] = field(default_factory=list)


def run_audit(root: Path) -> list[AgentAudit]:
    out = []
    for folder in registry.population_folders():
        sub = registry.resolve(folder)
        files = audit_sample(discover(root / folder))
        a = AgentAudit(folder=folder, family=sub.family, n_sampled=len(files))
        for f in files:
            try:
                loaded = load_trajectory_file(f, folder)
            except FileLevelFailure:
                continue
            a.n_loaded += 1
            a.results.append(extract(loaded))
        out.append(a)
    return out


def render(audits: list[AgentAudit], root: Path, date: str) -> str:
    body = [
        "# Adapter structural audit report (spec §5)",
        "",
        f"*Generated {date} by `methodology/scripts/run_adapter_audit.py` against `{root}`, on the §5 audit sample "
        f"({sum(a.n_sampled for a in audits)} files, {len(audits)} agents; every ⌈n/50⌉-th discovery-passing file from "
        "index 0, bytewise order), after the extractors. Descriptive only: no unit-definition change, no outcome join, "
        "no ranking. Structure only: no resolution contact, no marker counts, no signal values, no v1 code over trajectories. "
        "Words = whitespace-split tokens.*",
        "",
        "Rule versions: SAGE `sage-1`, Trae `trae-b-1` (spec rev 3 §4). Harness-string rule §2.4 (D3): prefix `Exit due to`, "
        "SWE-agent family only. Build-level note: unit text excludes the boundary delimiters (SAGE `THOUGHT:` label, "
        "Trae `<think>` opener and final `</think>`); interior content is verbatim.",
        "",
    ]

    # ---- 1. multiplicity per family
    body += ["## 1. Emission-per-anchor multiplicity (fragment_count) per family", ""]
    per_family: dict[str, Counter] = defaultdict(Counter)
    for a in audits:
        for r in a.results:
            for u in r.units:
                per_family[a.family][u.unit.fragment_count] += 1
    rows = []
    for fam in (registry.THOUGHT, registry.EPAM, registry.SAGE, registry.SONAR, registry.TRAE, registry.THINK_TOOL):
        c = per_family[fam]
        n = sum(c.values())
        rows.append([FAMILY_LABEL[fam], n, c[1], sum(v for k, v in c.items() if k > 1),
                     _pct(sum(v for k, v in c.items() if k > 1), n), max(c) if c else "—",
                     "; ".join(f"{k}: {v}" for k, v in sorted(c.items()))])
    body += [_table(["family", "units", "fragment_count = 1", "> 1", "> 1 rate", "max", "distribution"], rows), ""]

    # ---- 2. unit length (words) per agent
    body += ["## 2. Unit length distribution (words) per agent", "",
             "Non-terminal and terminal units separately (§2.3 stratification). Feeds the pre-registration §5 "
             "length-shift limitation; reported next to κ context in the writeup.", ""]
    rows = []
    for a in audits:
        nt = [len(u.text.split()) for r in a.results for u in r.units if not u.unit.terminal]
        t = [len(u.text.split()) for r in a.results for u in r.units if u.unit.terminal]
        rows.append([a.folder, "non-terminal", *_dist(nt)])
        rows.append(["", "terminal", *_dist(t)])
    body += [_table(["submission folder", "stratum", "n", "min", "p25", "median", "p75", "p90", "max", "mean"], rows), ""]

    # ---- 3. presence per trajectory
    body += ["## 3. Presence per trajectory", "",
             "Fraction of trajectories with ≥1 unit, per agent. Agent behaviour under §6, not a failure threshold.", ""]
    rows = []
    for a in audits:
        with_units = sum(1 for r in a.results if r.units)
        n_units = sum(len(r.units) for r in a.results)
        per_traj = [len(r.units) for r in a.results]
        rows.append([a.folder, a.n_loaded, with_units, _pct(with_units, a.n_loaded), n_units,
                     f"{statistics.mean(per_traj):.1f}" if per_traj else "—", _q(per_traj, .5)])
    body += [_table(["submission folder", "trajectories", "with ≥1 unit", "presence", "units", "mean units/traj",
                     "median units/traj"], rows), ""]

    # ---- 4. terminal-unit and empty-anchor rates
    body += ["## 4. Terminal-unit and empty-anchor rates", "",
             "Terminal units are stratified as a genre (wrap-up summaries, §2.3); the stratification carries to the writeup. "
             "Empty anchors = action steps with no preceding reasoning (§2.4). Empty emissions = designated slots that were "
             "empty / whitespace-only (no emission).", ""]
    rows = []
    for a in audits:
        n_units = sum(len(r.units) for r in a.results)
        n_term = sum(1 for r in a.results for u in r.units if u.unit.terminal)
        traj_term = sum(1 for r in a.results if any(u.unit.terminal for u in r.units))
        steps = sum(r.anchoring.n_action_steps for r in a.results)
        empty_anchors = sum(r.anchoring.n_empty_anchors for r in a.results)
        empty_em = sum(r.anchoring.n_empty_emissions for r in a.results)
        n_em = sum(r.anchoring.n_emissions for r in a.results)
        free = sum(1 for r in a.results for u in r.units if u.unit.emission_kind == "free-standing")
        rows.append([a.folder, n_units, n_term, _pct(n_term, n_units), f"{traj_term}/{a.n_loaded}", steps,
                     empty_anchors, _pct(empty_anchors, steps), f"{empty_em} / {empty_em + n_em}", free,
                     _pct(free, n_units)])
    body += [_table(["submission folder", "units", "terminal", "terminal rate", "trajectories ending in a terminal unit",
                     "action steps", "empty anchors", "empty-anchor rate", "empty emissions / designated slots",
                     "free-standing units", "free-standing rate"], rows), ""]

    # ---- 5. SAGE
    body += ["## 5. SAGE boundary rule (`sage-1`) validation counts and anomaly rates", "",
             f"Audit-sample files minus the §4.1 inspection files {sorted(SAGE_INSPECTION)} (disjoint).", ""]
    for a in audits:
        if a.family != registry.SAGE:
            continue
        c: Counter = Counter()
        n_files = 0
        for r in a.results:
            if instance_stem(r.path) in SAGE_INSPECTION:
                continue
            n_files += 1
            c.update(r.notes)
            c["units"] += len(r.units)
        msgs = c["assistant_messages"]
        body += [_table(["check", "count", "rate"], [
            ["files (disjoint)", n_files, ""],
            ["assistant messages", msgs, ""],
            ["units produced", c["units"], _pct(c["units"], msgs)],
            ["`THOUGHT:` absent (no emission)", c["thought_absent"], _pct(c["thought_absent"], msgs)],
            ["`THOUGHT:` at offset ≠ 0 (prose before it excluded)", c["thought_offset_nonzero"],
             _pct(c["thought_offset_nonzero"], msgs)],
            ["non-bash fences before the bash fence (rev-1 template's cut class)", c["non_bash_fences_before_bash_msgs"],
             _pct(c["non_bash_fences_before_bash_msgs"], msgs)],
            ["missing bash fence (emission runs to end of message)", c["missing_bash_fence"],
             _pct(c["missing_bash_fence"], msgs)],
        ]), ""]

    # ---- 6. Trae
    body += ["## 6. Trae stray-closer rate (option-B-affected, `trae-b-1`)", "",
             f"Audit-sample files minus the §4.2 inspection files {sorted(TRAE_INSPECTION)} (disjoint).", ""]
    for a in audits:
        if a.family != registry.TRAE:
            continue
        c: Counter = Counter()
        n_files = 0
        affected_units = 0
        for r in a.results:
            if instance_stem(r.path) in TRAE_INSPECTION:
                continue
            n_files += 1
            c.update(r.notes)
            c["units"] += len(r.units)
            affected_units += sum(1 for u in r.units if any(f.meta.get("closers", 1) > 1 for f in u.unit.fragments))
        msgs = c["assistant_messages"]
        body += [_table(["check", "count", "rate"], [
            ["files (disjoint)", n_files, ""],
            ["assistant messages", msgs, ""],
            ["units produced", c["units"], _pct(c["units"], msgs)],
            ["messages with > 1 `</think>` (option-B-affected)", c["multi_closer_messages"],
             _pct(c["multi_closer_messages"], msgs)],
            ["units containing an affected fragment", affected_units, _pct(affected_units, c["units"])],
            ["`<think>` with no closer (emission runs to end of message)", c["unclosed_think"],
             _pct(c["unclosed_think"], msgs)],
        ]), ""]

    # ---- 7. harness strings
    body += ["## 7. Harness-string census (§2.4, D3)", "",
             "`n_harness_strings` = designated slots excluded by the documented-prefix rule (`Exit due to`, SWE-agent "
             "family only). The duplicate census lists the top exact-duplicate designated strings on action-less "
             "containers (text-only steps and their analogues in other families), per agent — to surface any further "
             "harness template structurally for a documented addition. Strings are shown truncated; counts are of "
             "exact duplicates. In old-format SWE-agent files the exit string sits on a step whose action is "
             "`exit_cost` / `exit_context` (an action-bearing step), so it counts under `n_harness_strings` — the anchor "
             "then has no emission — but never enters the action-less census; the split is shown.", ""]
    rows = []
    prefixes = HARNESS_TEMPLATE_PREFIXES.get(registry.THOUGHT, ())
    for a in audits:
        n_h = sum(r.anchoring.n_harness_strings for r in a.results)
        free_texts = [t.strip() for r in a.results for t in r.free_standing_texts if t.strip()]
        n_h_free = sum(1 for t in free_texts if any(t.startswith(p) for p in prefixes)) if a.family == registry.THOUGHT else 0
        dups = Counter(free_texts)
        top = [(k, v) for k, v in dups.most_common(5) if v >= 2]
        shown = "; ".join(f"`{repr(k[:60])}` ×{v}" for k, v in top) or "—"
        rows.append([a.folder, n_h, n_h_free, n_h - n_h_free, len(free_texts), shown])
    body += [_table(["submission folder", "n_harness_strings", "  on action-less steps", "  on action-bearing steps",
                     "action-less designated strings", "top exact duplicates (≥2)"], rows), ""]

    # ---- supplementary
    body += ["## Supplementary (descriptive): path-layer and mention coverage", "",
             "Fraction of actions with ≥1 extracted path (feeds Phase 3's ability to compute reread_bursts / edit_churn), "
             "and fraction of units with a tier-1/2 mention attribution against the trajectory's touched-path set. "
             "Old-format `edit` resolves to the currently open file (documented stateful rule in paths.py).", ""]
    rows = []
    for a in audits:
        n_actions = sum(len(r.actions) for r in a.results)
        with_path = sum(1 for r in a.results for act in r.actions if act.paths)
        n_units = sum(len(r.units) for r in a.results)
        tiers: Counter = Counter()
        for r in a.results:
            idx = MentionIndex({p for act in r.actions for p in act.paths})
            for u in r.units:
                tier, _ = idx.attribute(u.text)
                tiers[tier or "none"] += 1
        edits_no_file = sum(r.notes.get("old_edits_without_open_file", 0) for r in a.results)
        unparsed = sum(r.notes.get("tool_args_unparsed", 0) + r.notes.get("epam_input_text_unparsed", 0)
                       + r.notes.get("think_args_unparsed", 0) for r in a.results)
        rows.append([a.folder, n_actions, _pct(with_path, n_actions), unparsed, edits_no_file, n_units,
                     _pct(tiers["exact_path"], n_units), _pct(tiers["unique_basename"], n_units)])
    body += [_table(["submission folder", "actions", "with ≥1 path", "args unparsed", "old `edit` w/o open file", "units",
                     "tier 1 (exact_path)", "tier 2 (unique_basename)"], rows), ""]
    return "\n".join(body)
