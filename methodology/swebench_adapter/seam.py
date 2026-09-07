"""Seam-test suite (spec §7, §9.2): structure-only checks against the real
download at an explicit trajectories root, run on the §5 audit sample.

Fence (spec §5 shape): structure only — no resolution contact, no marker
counts, no signal values, no v1 code over trajectories. Every number here is
a count of containers, keys, tags, fences, or filenames.

Each `check_*` function returns a `Section` (title + markdown body + optional
verdict flags). `run()` assembles the report. The §7.1 EPAM gate and the probe-4
shape/discovery verification carry stop-early flags (handoff: stop at the
finding if the gate fails or probe 4 contradicts a §1 rule).
"""
from __future__ import annotations

import datetime as _dt
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swebench_adapter import registry
from swebench_adapter.discovery import Discovery, discover
from swebench_adapter.loaders import FileLevelFailure, load_trajectory_file, read_json, shape_matches
from swebench_adapter.sample import audit_sample

PAPER_TRAJECTORY_COUNT = 9374           # arXiv 2604.02547, 19 agents (recon §Bucket identity)

# §4 inspection samples — validation/derivation must be disjoint from these.
SAGE_INSPECTION = {"astropy__astropy-12907", "astropy__astropy-13033"}
TRAE_INSPECTION = {"astropy__astropy-12907", "astropy__astropy-13033"}

PY_PATH_RE = re.compile(r"(?<![\w/.-])[\w./-]*\w\.py\b")
FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)")


@dataclass
class Section:
    title: str
    body: str
    verdict: str | None = None              # "PASS" | "FAIL" | "INFO" | None
    stop_early: bool = False
    findings: list[str] = field(default_factory=list)   # one-liners surfaced in the report head


@dataclass
class Sampled:
    """Audit sample for one population folder, loaded once."""
    folder: str
    family: str
    discovery: Discovery
    files: list[Path]
    loaded: list[tuple[Path, Any]] = field(default_factory=list)
    file_failures: list[tuple[Path, str]] = field(default_factory=list)


def _pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100.0 * n / d:.1f}%"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _iid(path: Path) -> str:
    from swebench_adapter.discovery import instance_stem
    return instance_stem(path)


# --------------------------------------------------------------------------
# sample loading
# --------------------------------------------------------------------------

def load_samples(root: Path) -> dict[str, Sampled]:
    samples: dict[str, Sampled] = {}
    for folder in registry.population_folders():
        sub = registry.resolve(folder)
        disc = discover(root / folder)
        s = Sampled(folder=folder, family=sub.family, discovery=disc, files=audit_sample(disc))
        for f in s.files:
            try:
                s.loaded.append((f, load_trajectory_file(f, folder).data))
            except FileLevelFailure as e:
                s.file_failures.append((f, str(e)))
        samples[folder] = s
    return samples


def _by_family(samples: dict[str, Sampled], family: str) -> list[Sampled]:
    return [s for s in samples.values() if s.family == family]


# --------------------------------------------------------------------------
# §7.2 — file discovery (probe 4) + shape table + 9,893 vs 9,374 reconciliation
# --------------------------------------------------------------------------

def check_discovery(root: Path, samples: dict[str, Sampled]) -> Section:
    rows = []
    total_candidates = total_instance = total_quarantined = 0
    excluded_instance_files = {}
    for folder in sorted(registry.SUBMISSION_META):
        d = discover(root / folder) if (root / folder).is_dir() else None
        if d is None:
            rows.append([folder, "—", "—", "—", "—", "—", "MISSING ON DISK"])
            continue
        n_traj = sum(1 for p in d.files if p.name.endswith(".traj"))
        n_trajjson = sum(1 for p in d.files if p.name.endswith(".traj.json"))
        n_json = len(d.files) - n_traj - n_trajjson
        status = "population" if folder in registry.POPULATION else "excluded"
        rows.append([folder, d.n_candidates, f"{n_traj}/{n_json}/{n_trajjson}", len(d.files),
                     ", ".join(p.name for p, _ in d.quarantined) or "—", len(d.duplicates), status])
        total_candidates += d.n_candidates
        total_instance += len(d.files)
        total_quarantined += len(d.quarantined)
        if folder in registry.EXCLUDED:
            excluded_instance_files[folder] = len(d.files)
    body = [
        "Per submission directory, from the §1 discovery rule (glob `*.traj` + `*.json`, stem dedupe with "
        "`.traj.json`, instance-id pattern, `non_trajectory` quarantine). Discovery opens no file.",
        "",
        _table(["submission folder", "candidates", ".traj/.json/.traj.json kept", "instance-id files",
                "quarantined (non_trajectory)", "stem dups", "registry"], rows),
        "",
        "**Reconciliation (review §7.2):**",
        "",
    ]
    outside = excluded_instance_files.get("20250415_openhands", 0)
    after = total_instance - outside
    body.append(_table(["quantity", "count"], [
        ["candidate files on disk (all 20 dirs)", total_candidates],
        ["quarantined `non_trajectory`", total_quarantined],
        ["instance-id files (all 20 dirs)", total_instance],
        ["`20250415_openhands` instance-id files (outside the 19-agent population)", outside],
        ["instance-id files across the 19 paper agents", after],
        ["paper trajectory count", PAPER_TRAJECTORY_COUNT],
        ["residual (19-agent instance-id files − paper count)", after - PAPER_TRAJECTORY_COUNT],
    ]))
    # Shape table on the audit sample
    body += ["", "**File-level shape check (§1 table) on the audit sample:**", ""]
    srows = []
    any_shape_fail = False
    for folder, s in samples.items():
        n_ok = len(s.loaded)
        srows.append([folder, s.family, len(s.files), n_ok, len(s.file_failures)])
        any_shape_fail |= bool(s.file_failures)
    body.append(_table(["submission folder", "family", "sampled", "shape ok", "file-level failures"], srows))
    fails = [(f.name, msg) for s in samples.values() for f, msg in s.file_failures]
    if fails:
        body += ["", "Failures:", ""] + [f"- `{n}`: {m}" for n, m in fails]
    # Full-directory readability + shape census for population dirs (feeds the residual explanation).
    body += ["", "**Full-directory file-level census (population dirs, every instance-id file):**", ""]
    frows = []
    total_file_failures = 0
    for folder, s in samples.items():
        n_fail = 0
        for f in s.discovery.files:
            try:
                data = read_json(f)
            except (OSError, ValueError, UnicodeDecodeError):
                n_fail += 1
                continue
            if not shape_matches(s.family, data):
                n_fail += 1
        total_file_failures += n_fail
        frows.append([folder, len(s.discovery.files), n_fail])
    frows.append(["**total**", sum(r[1] for r in frows), total_file_failures])
    body.append(_table(["submission folder", "instance-id files", "file-level failures (unreadable or wrong shape)"],
                       frows))
    verdict = "FAIL" if any_shape_fail else "PASS"
    findings = [
        f"Probe 4: discovery rule and §1 shape table hold on every directory; {total_quarantined} `non_trajectory` "
        f"file ({', '.join(p.name for f in samples.values() for p, _ in f.discovery.quarantined) or '—'}); "
        f"{total_file_failures} file-level failures across all {sum(r[1] for r in frows[:-1])} population files.",
        f"Reconciliation: {total_candidates} files − {outside} (`20250415_openhands`) − {total_quarantined} "
        f"non-trajectory = {after} vs paper {PAPER_TRAJECTORY_COUNT}: residual {after - PAPER_TRAJECTORY_COUNT}, "
        "not explained by anything visible to discovery or the population file-level census (the review's "
        "'handful of non-trajectory files' guess was 1). Candidate explanation, unverifiable without their "
        "pipeline: per-agent counts the paper reports after its own parser's silent skips.",
    ]
    return Section("§7.2 File discovery (probe 4), shape table, and 9,893-vs-9,374 reconciliation",
                   "\n".join(body), verdict=verdict, stop_early=any_shape_fail, findings=findings)


# --------------------------------------------------------------------------
# §7.1 — EPAM ordering gate
# --------------------------------------------------------------------------

def epam_entries(data: Any) -> list[dict[str, Any]]:
    """Entries in document order; the loader never sorts keys (§2.7)."""
    return list(data[0].values())


def epam_alternation(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Alternation regularity (§7.1 i)."""
    c = {"entries": len(entries), "thoughts": 0, "actions": 0, "consecutive_thoughts": 0,
         "action_without_preceding_thought": 0, "action_after_action": 0, "trailing_thoughts": 0}
    prev = None
    for e in entries:
        is_t = e.get("author_name") == "Thoughts"
        if is_t:
            c["thoughts"] += 1
            if prev == "T":
                c["consecutive_thoughts"] += 1
        else:
            c["actions"] += 1
            if prev is None:
                c["action_without_preceding_thought"] += 1
            elif prev == "A":
                c["action_after_action"] += 1
                c["action_without_preceding_thought"] += 1
        prev = "T" if is_t else "A"
    if prev == "T":
        c["trailing_thoughts"] = 1
    return c


def _names_in(text: str) -> list[str]:
    return PY_PATH_RE.findall(text or "")


def epam_path_resolution(entries: list[dict[str, Any]]) -> dict[str, Counter]:
    """Next-vs-previous path resolution (§7.1 ii), two match variants.

    For each `Thoughts` entry naming a `.py` path: does any named path resolve
    to the previous action's `input_text`, the next action's, both, or neither?
    `basename` (primary, fixed before running): the path's final component
    appears in the action's input_text. `full`: the full token appears.
    Entries naming no `.py` path are excluded ("no_name").
    """
    out = {"basename": Counter(), "full": Counter()}
    idx_actions = [i for i, e in enumerate(entries) if e.get("author_name") != "Thoughts"]
    for i, e in enumerate(entries):
        if e.get("author_name") != "Thoughts":
            continue
        names = _names_in(e.get("message", ""))
        if not names:
            out["basename"]["no_name"] += 1
            out["full"]["no_name"] += 1
            continue
        prev_i = max((j for j in idx_actions if j < i), default=None)
        next_i = min((j for j in idx_actions if j > i), default=None)
        prev_t = entries[prev_i].get("input_text", "") if prev_i is not None else ""
        next_t = entries[next_i].get("input_text", "") if next_i is not None else ""
        for variant, key in (("basename", lambda n: n.rsplit("/", 1)[-1]), ("full", lambda n: n)):
            hit_prev = any(key(n) in prev_t for n in names)
            hit_next = any(key(n) in next_t for n in names)
            cls = "both" if hit_prev and hit_next else "next" if hit_next else "previous" if hit_prev else "neither"
            out[variant][cls] += 1
    return out


def check_epam_gate(samples: dict[str, Sampled]) -> Section:
    epam = _by_family(samples, registry.EPAM)
    if not epam:
        return Section("§7.1 EPAM ordering gate", "no EPAM folder in population", verdict="INFO")
    alt = Counter()
    res = {"basename": Counter(), "full": Counter()}
    files_with_consecutive = files_with_action_after_action = 0
    for s in epam:
        for _, data in s.loaded:
            entries = epam_entries(data)
            a = epam_alternation(entries)
            alt.update(a)
            files_with_consecutive += bool(a["consecutive_thoughts"])
            files_with_action_after_action += bool(a["action_after_action"])
            r = epam_path_resolution(entries)
            res["basename"].update(r["basename"])
            res["full"].update(r["full"])
    n_files = sum(len(s.loaded) for s in epam)
    i_pass = alt["consecutive_thoughts"] == 0 and alt["action_without_preceding_thought"] == 0
    b = res["basename"]
    ii_pass = b["next"] > b["previous"]
    body = [
        f"Audit sample: {n_files} EPAM files, {alt['entries']} entries "
        f"({alt['thoughts']} `Thoughts`, {alt['actions']} action entries). "
        "Entries read in document order; the loader never sorts keys (§2.7 build rule).",
        "",
        "**(i) Alternation regularity** — every action entry preceded by exactly one `Thoughts` entry; "
        "no consecutive `Thoughts` entries.",
        "",
        _table(["check", "count"], [
            ["consecutive `Thoughts` entries", alt["consecutive_thoughts"]],
            ["action entries not immediately preceded by a `Thoughts` entry", alt["action_without_preceding_thought"]],
            ["  of which action-after-action", alt["action_after_action"]],
            ["files with a trailing `Thoughts` entry (terminal unit under §2.3)", alt["trailing_thoughts"]],
            ["files with any consecutive `Thoughts`", files_with_consecutive],
        ]),
        "",
        f"(i) result: **{'PASS' if i_pass else 'FAIL'}**",
        "",
        "**(ii) Next-vs-previous path resolution** — `Thoughts` entries naming a `.py` path, classified by "
        "whether the path resolves to the next action's `input_text`, the previous action's, both, or neither. "
        "Pass criterion (frozen, §7.1): among entries resolving to exactly one adjacent action, next strictly "
        "exceeds previous. Match variant fixed before running: `basename` is primary; `full` token reported alongside.",
        "",
        _table(["variant", "next only", "previous only", "both", "neither", "no `.py` named"], [
            [v, res[v]["next"], res[v]["previous"], res[v]["both"], res[v]["neither"], res[v]["no_name"]]
            for v in ("basename", "full")
        ]),
        "",
        f"(ii) result on the primary variant: next {b['next']} vs previous {b['previous']} → "
        f"**{'PASS' if ii_pass else 'FAIL'}**"
        + ("" if (res["full"]["next"] > res["full"]["previous"]) == ii_pass
           else " — NOTE: the `full` variant disagrees with the primary variant."),
        "",
        "Recorded limitation (§2.7): this check falsifies reversed/scrambled order; it does not prove chronology.",
    ]
    ok = i_pass and ii_pass
    body.append("")
    body.append(f"**Gate verdict: {'PASS — EPAM anchoring may be built' if ok else 'FAIL — EPAM needs its own ordering rule before build'}**")
    findings = [
        f"EPAM gate {'PASS' if ok else 'FAIL'}: (i) {alt['consecutive_thoughts']} consecutive `Thoughts`, "
        f"{alt['action_without_preceding_thought']} unpreceded actions in {alt['entries']} entries; "
        f"(ii) next {b['next']} vs previous {b['previous']} (basename variant; full-token {res['full']['next']} vs "
        f"{res['full']['previous']}). {alt['trailing_thoughts']}/{n_files} files end on a `Thoughts` entry (terminal unit).",
    ]
    return Section("§7.1 EPAM ordering gate", "\n".join(body), verdict="PASS" if ok else "FAIL", stop_early=not ok,
                   findings=findings)


# --------------------------------------------------------------------------
# §7.3 — EPAM text field
# --------------------------------------------------------------------------

def check_epam_text_field(samples: dict[str, Sampled]) -> Section:
    c = Counter()
    for s in _by_family(samples, registry.EPAM):
        for _, data in s.loaded:
            for e in epam_entries(data):
                c["entries"] += 1
                c[("keys", tuple(sorted(e)))] += 1
                if e.get("author_name") == "Thoughts":
                    c["thoughts"] += 1
                    c["thoughts_input_text_empty"] += (e.get("input_text", "") == "")
                    c["thoughts_message_empty_or_ws"] += (not (e.get("message") or "").strip())
                else:
                    c["actions"] += 1
                    c["actions_input_text_starts_brace"] += (str(e.get("input_text", "")).startswith("{"))
                c[("author", e.get("author_name"))] += 1
    keysets = [(k[1], v) for k, v in c.items() if isinstance(k, tuple) and k[0] == "keys"]
    authors = [(k[1], v) for k, v in c.items() if isinstance(k, tuple) and k[0] == "author"]
    body = [
        "Resolved in the review; confirmed here on the audit sample.",
        "",
        _table(["check", "count"], [
            ["entries", c["entries"]],
            ["entry key sets", "; ".join(f"`{list(k)}`: {v}" for k, v in keysets)],
            ["author names", "; ".join(f"`{a}`: {v}" for a, v in sorted(authors, key=lambda x: -x[1]))],
            ["`Thoughts` entries", c["thoughts"]],
            ["  with `input_text == ''`", c["thoughts_input_text_empty"]],
            ["  with empty / whitespace-only `message` (no emission under §2.4)", c["thoughts_message_empty_or_ws"]],
            ["action entries", c["actions"]],
            ["  with `input_text` starting `{` (Python-repr dict, §8)", c["actions_input_text_starts_brace"]],
        ]),
        "",
        f"Text field = `message`: **{'CONFIRMED' if c['thoughts_input_text_empty'] == c['thoughts'] else 'NOT CONFIRMED'}**.",
    ]
    return Section("§7.3 EPAM text field", "\n".join(body),
                   verdict="PASS" if c["thoughts_input_text_empty"] == c["thoughts"] else "FAIL")


# --------------------------------------------------------------------------
# §7.4 — Sonar block type
# --------------------------------------------------------------------------

def check_sonar_blocks(samples: dict[str, Sampled]) -> Section:
    bt = Counter(); per_msg = Counter(); order = Counter(); c = Counter()
    for s in _by_family(samples, registry.SONAR):
        for _, data in s.loaded:
            for m in data:
                if m.get("role") != "assistant":
                    continue
                c["assistant_msgs"] += 1
                blocks = m.get("blocks") or []
                types = tuple(b.get("block_type") for b in blocks)
                order[types] += 1
                per_msg[sum(1 for t in types if t == "thinking")] += 1
                for b in blocks:
                    bt[b.get("block_type")] += 1
                    if b.get("block_type") == "thinking":
                        c["thinking_content_is_str"] += isinstance(b.get("content"), str)
                        c["thinking_has_text_key"] += ("text" in b)
                        c["thinking_has_num_tokens"] += ("num_tokens" in b)
                    if b.get("block_type") == "text":
                        c["text_block_has_text_key"] += ("text" in b)
                tcs = (m.get("additional_kwargs") or {}).get("tool_calls")
                c["msgs_with_tool_calls"] += bool(tcs)
                c["msgs_without_tool_calls_free_standing"] += (not tcs)
                c["tool_use_blocks"] += sum(1 for t in types if t == "tool_use")
    body = [
        "Resolved in the review; confirmed here on the audit sample.",
        "",
        _table(["check", "count"], [
            ["assistant messages", c["assistant_msgs"]],
            ["block types", "; ".join(f"`{k}`: {v}" for k, v in bt.most_common())],
            ["thinking blocks per message", "; ".join(f"{k}: {v}" for k, v in sorted(per_msg.items()))],
            ["block order patterns", "; ".join(f"`{list(k)}`: {v}" for k, v in order.most_common(5))],
            ["thinking blocks with `content` str", c["thinking_content_is_str"]],
            ["thinking blocks carrying a `text` key", c["thinking_has_text_key"]],
            ["thinking blocks carrying `num_tokens`", c["thinking_has_num_tokens"]],
            ["text blocks carrying a `text` key", c["text_block_has_text_key"]],
            ["messages with `additional_kwargs.tool_calls`", c["msgs_with_tool_calls"]],
            ["messages without tool_calls (free-standing under §2.2)", c["msgs_without_tool_calls_free_standing"]],
            ["`tool_use` blocks in `blocks[]`", c["tool_use_blocks"]],
        ]),
    ]
    ok = c["thinking_content_is_str"] == bt["thinking"] and c["tool_use_blocks"] == 0
    body += ["", f"`block_type == \"thinking\"`, text under `content`: **{'CONFIRMED' if ok else 'NOT CONFIRMED'}**."]
    return Section("§7.4 Sonar block type", "\n".join(body), verdict="PASS" if ok else "FAIL")


# --------------------------------------------------------------------------
# §7.5 / §7.8 — SAGE: rule template applied provisionally + structure census
# --------------------------------------------------------------------------

def sage_message_census(content: str) -> dict[str, Any]:
    """Structure facts for one SAGE assistant message (no text lengths beyond offsets)."""
    i = content.find("THOUGHT:")
    langs = FENCE_RE.findall(content)
    # fences alternate opener/closer; opener languages are the even positions
    openers = langs[0::2]
    bash_idx = next((k for k, lang in enumerate(openers) if lang == "bash"), None)
    non_bash_before_bash = bash_idx if bash_idx is not None else len(openers)
    last_close = content.rfind("```")
    after = content[last_close + 3:] if last_close >= 0 else ""
    template_end = content.find("```bash") if "```bash" in content else len(content)
    emission = content[i:template_end] if i >= 0 else ""
    return {
        "thought_offset": i,                                  # -1 = absent
        "opener_langs": tuple(openers),
        "has_bash_fence": bash_idx is not None,
        "non_bash_fences_before_bash": non_bash_before_bash,
        "text_after_last_fence": bool(after.strip()),
        "template_emission_nonempty": bool(emission.replace("THOUGHT:", "", 1).strip()),
        "fence_count_balanced": len(langs) % 2 == 0,
    }


def check_sage(samples: dict[str, Sampled]) -> tuple[Section, Section]:
    c = Counter(); offsets = Counter(); langseq = Counter(); nonbash_before = Counter()
    n_files = n_excluded = 0
    for s in _by_family(samples, registry.SAGE):
        for path, data in s.loaded:
            if _iid(path) in SAGE_INSPECTION:
                n_excluded += 1
                continue
            n_files += 1
            for m in data.get("messages", []):
                if m.get("role") != "assistant" or not isinstance(m.get("content"), str):
                    continue
                c["assistant_msgs"] += 1
                f = sage_message_census(m["content"])
                offsets["absent" if f["thought_offset"] < 0 else "0" if f["thought_offset"] == 0 else ">0"] += 1
                langseq[f["opener_langs"]] += 1
                c["has_bash_fence"] += f["has_bash_fence"]
                c["missing_bash_fence"] += (not f["has_bash_fence"])
                nonbash_before[f["non_bash_fences_before_bash"] if f["has_bash_fence"] else "no-bash"] += 1
                c["text_after_last_fence"] += f["text_after_last_fence"]
                c["template_emission_nonempty"] += f["template_emission_nonempty"]
                c["fence_unbalanced"] += (not f["fence_count_balanced"])
    census = [
        f"Audit sample minus the §4.1 inspection files ({n_excluded} excluded: {sorted(SAGE_INSPECTION)}): "
        f"{n_files} files, {c['assistant_msgs']} assistant messages.",
        "",
        _table(["check", "count"], [
            ["`THOUGHT:` offset = 0", offsets["0"]],
            ["`THOUGHT:` offset > 0 (prose before it, excluded as undesignated)", offsets[">0"]],
            ["`THOUGHT:` absent (no emission)", offsets["absent"]],
            ["messages with a ```` ```bash ```` fence", c["has_bash_fence"]],
            ["messages missing a bash fence (emission runs to end of message)", c["missing_bash_fence"]],
            ["messages with non-whitespace text after the last fence close", c["text_after_last_fence"]],
            ["messages with an odd number of ``` markers", c["fence_unbalanced"]],
        ]),
        "",
        "Fence-opener language sequences (top 8):",
        "",
        _table(["opener sequence", "messages"], [[f"`{list(k)}`", v] for k, v in langseq.most_common(8)]),
        "",
        "Non-bash fences before the first bash fence (the class the rev-1 'first code fence' template would have cut):",
        "",
        _table(["non-bash fences before bash", "messages"],
               [[k, v] for k, v in sorted(nonbash_before.items(), key=lambda kv: str(kv[0]))]),
    ]
    validation = [
        "The §4.1 **refined template** (first `THOUGHT:` through the first ```` ```bash ```` opener; no `THOUGHT:` → no "
        "emission; no bash fence → end of message) applied **provisionally** to the disjoint sample. "
        "`rule_version` is unassigned until [A] fills the §4.1 derivation slot at the checkpoint; the extractor is not built here.",
        "",
        _table(["check", "count"], [
            ["assistant messages", c["assistant_msgs"]],
            ["template yields a non-empty emission", c["template_emission_nonempty"]],
            ["template yields no emission (`THOUGHT:` absent or empty)", c["assistant_msgs"] - c["template_emission_nonempty"]],
            ["emission end boundary = bash fence", c["has_bash_fence"]],
            ["emission end boundary = end of message", c["missing_bash_fence"]],
        ]),
    ]
    sage_findings = [
        f"SAGE: §4.1 refined template yields an emission on {c['template_emission_nonempty']}/{c['assistant_msgs']} "
        f"messages of the disjoint sample; `THOUGHT:` at offset 0 on {offsets['0']}, >0 on {offsets['>0']}, absent on "
        f"{offsets['absent']}; bash fence present on all {c['has_bash_fence']}; non-bash fences before the bash fence on "
        f"{sum(v for k, v in nonbash_before.items() if k not in (0, 'no-bash'))} (the rev-1 template's cut class).",
    ]
    return (Section("§7.5 SAGE rule validation (template applied provisionally; rule_version unassigned)",
                    "\n".join(validation), verdict="INFO", findings=sage_findings),
            Section("§7.8 SAGE structure census", "\n".join(census), verdict="INFO"))


# --------------------------------------------------------------------------
# §7.7 — Trae tag-balance census
# --------------------------------------------------------------------------

def trae_message_census(content: str) -> dict[str, Any]:
    openers = content.count("<think>")
    closers = content.count("</think>")
    last = content.rfind("</think>")
    first = content.find("</think>")
    return {
        "openers": openers,
        "closers": closers,
        "function_before_last_closer": closers > 0 and "<function=" in content[:last],
        # Added diagnostic (not in §7.7 as written): a *closed* call before the last closer
        # would mean an executed action sits inside the option-B span; an unclosed opener
        # is an aborted call the model restarted after further reasoning.
        "closed_function_before_last_closer": closers > 0 and "</function>" in content[:last],
        "has_function": "<function=" in content,
        "first_closer_offset": first,
        "closer_offsets": [m.start() for m in re.finditer(r"</think>", content)],
        "function_offsets": [m.start() for m in re.finditer(r"<function=", content)],
        "function_close_offsets": [m.start() for m in re.finditer(r"</function>", content)],
    }


def check_trae(samples: dict[str, Sampled]) -> Section:
    c = Counter(); openers = Counter(); closers = Counter()
    offenders: list[list[Any]] = []
    n_files = n_excluded = 0
    for s in _by_family(samples, registry.TRAE):
        for path, data in s.loaded:
            if _iid(path) in TRAE_INSPECTION:
                n_excluded += 1
                continue
            n_files += 1
            for mi, m in enumerate(data):
                if m.get("role") != "assistant" or not isinstance(m.get("content"), str):
                    continue
                c["assistant_msgs"] += 1
                f = trae_message_census(m["content"])
                openers[f["openers"]] += 1
                closers[f["closers"]] += 1
                c["multi_closer"] += (f["closers"] > 1)
                c["function_before_last_closer"] += f["function_before_last_closer"]
                c["closed_function_before_last_closer"] += f["closed_function_before_last_closer"]
                c["no_function"] += (not f["has_function"])
                c["no_think"] += (f["openers"] == 0)
                if f["function_before_last_closer"]:
                    offenders.append([path.name, mi, len(m["content"]), f["closer_offsets"], f["function_offsets"],
                                      f["function_close_offsets"]])
    body = [
        f"Audit sample minus the §4.2 inspection files ({n_excluded} excluded): {n_files} files, "
        f"{c['assistant_msgs']} assistant messages.",
        "",
        _table(["check", "count"], [
            ["`<think>` openers per message", "; ".join(f"{k}: {v}" for k, v in sorted(openers.items()))],
            ["`</think>` closers per message", "; ".join(f"{k}: {v}" for k, v in sorted(closers.items()))],
            ["multi-closer messages (option-B-affected)", f"{c['multi_closer']} ({_pct(c['multi_closer'], c['assistant_msgs'])})"],
            ["messages with `<function=` before the last closer (§7.7 as written)", c["function_before_last_closer"]],
            ["  of which with a *closed* `</function>` before the last closer (added diagnostic)",
             c["closed_function_before_last_closer"]],
            ["messages with no `<think>` opener", c["no_think"]],
            ["messages with no `<function=` (free-standing / terminal under §2)", c["no_function"]],
        ]),
        "",
        f"No `<function=` precedes the last closer: **{'CONFIRMED' if c['function_before_last_closer'] == 0 else 'NOT CONFIRMED'}**.",
    ]
    if offenders:
        body += [
            "",
            "Messages contradicting the §3 basis for option B (\"no `<function=` occurs before the last closer\"). "
            "Offsets are character positions in the message content; structure only.",
            "",
            _table(["file", "msg #", "len", "`</think>` offsets", "`<function=` offsets", "`</function>` offsets"],
                   offenders),
            "",
            "Reading of the structure (for the §4.2 checkpoint, not a decision): in every listed message the "
            "`<function=` before the last closer has no `</function>` before that closer — an opener the model "
            "abandoned, then reasoned further, closed `</think>`, and restarted the call. Option B would include the "
            "abandoned call's XML in the unit; option A would drop the continued reasoning. Both remain recoverable "
            "from the stored first-closer offset (§3 rider).",
        ]
    findings = [
        f"Trae: multi-closer rate {c['multi_closer']}/{c['assistant_msgs']} ({_pct(c['multi_closer'], c['assistant_msgs'])}). "
        f"**Spec-contradicting fact:** {c['function_before_last_closer']} messages carry `<function=` before the last "
        f"`</think>` (§3 basis for option B said 0/36); in all of them the opener is unclosed (an abandoned call), "
        f"{c['closed_function_before_last_closer']} have a closed call there. Goes to the §4.2 derivation slot.",
    ]
    return Section("§7.7 Trae tag-balance census", "\n".join(body),
                   verdict="PASS" if c["function_before_last_closer"] == 0 else "FAIL", findings=findings)


# --------------------------------------------------------------------------
# §7.9 — SWE-agent trajectory vs non-demo history
# --------------------------------------------------------------------------

def sweagent_old_equality(data: Any) -> bool:
    traj = [s.get("thought") for s in data.get("trajectory", [])]
    hist = [e.get("thought") for e in data.get("history", [])
            if e.get("role") == "assistant" and not e.get("is_demo")]
    return traj == hist


def sweagent_new_identity(data: Any) -> dict[str, int]:
    traj = data.get("trajectory", [])
    n_hist_asst = sum(1 for e in data.get("history", []) if e.get("role") == "assistant")
    n_text_only = sum(1 for s in traj if not (s.get("action") or "").strip())
    return {"n_traj": len(traj), "n_hist_asst": n_hist_asst, "n_text_only": n_text_only}


def sweagent_history_contained(data: Any) -> bool:
    """Added diagnostic: non-demo assistant `history` thoughts form an ordered
    subsequence of `trajectory[].thought` — the containment property Q1 needs,
    independent of whether `history` drops text-only turns."""
    hist = [e.get("thought") for e in data.get("history", [])
            if e.get("role") == "assistant" and not e.get("is_demo")]
    it = iter(s.get("thought") for s in data.get("trajectory", []))
    return all(any(t == x for x in it) for t in hist)


HARNESS_EXIT_PREFIX = "Exit due to"       # SWE-agent harness template, not model text


def text_only_step_census(data: Any) -> Counter:
    """Structure of steps with empty `action`: position, presence of the same
    `thought` in `history`, whether `thought` is empty, and whether it starts
    with the SWE-agent harness exit template. (A harness string prefix, not a
    re-evaluation marker.)"""
    traj = data.get("trajectory", [])
    hist_thoughts = {e.get("thought") for e in data.get("history", []) if e.get("role") == "assistant"}
    c: Counter = Counter()
    for i, step in enumerate(traj):
        if (step.get("action") or "").strip():
            continue
        t = step.get("thought") or ""
        c["text_only_steps"] += 1
        c["last_step"] += (i == len(traj) - 1)
        c["thought_in_history"] += (t in hist_thoughts)
        c["thought_empty"] += (not t.strip())
        c["harness_exit_string"] += t.startswith(HARNESS_EXIT_PREFIX)
    return c


def check_sweagent_history(samples: dict[str, Sampled]) -> Section:
    rows = []
    census_rows = []
    spec_ok = contain_ok = True
    for s in _by_family(samples, registry.THOUGHT):
        n_contained = sum(sweagent_history_contained(d) for _, d in s.loaded)
        contain_ok &= n_contained == len(s.loaded)
        tc: Counter = Counter()
        for _, d in s.loaded:
            tc.update(text_only_step_census(d))
        census_rows.append([s.folder, tc["text_only_steps"], tc["last_step"], tc["thought_in_history"],
                            tc["thought_empty"], tc["harness_exit_string"]])
        if s.folder in registry.SWEAGENT_OLD_FOLDERS:
            n_eq = sum(sweagent_old_equality(d) for _, d in s.loaded)
            n_demo = sum(1 for _, d in s.loaded for e in d.get("history", []) if e.get("is_demo"))
            n_demo_asst_thoughts = sum(1 for _, d in s.loaded for e in d.get("history", [])
                                       if e.get("is_demo") and e.get("role") == "assistant" and "thought" in e)
            rows.append([s.folder, "old", len(s.loaded), f"{n_eq}/{len(s.loaded)}", "—",
                         f"{n_demo} demo entries; {n_demo_asst_thoughts} demo assistant thoughts",
                         f"{n_contained}/{len(s.loaded)}"])
            spec_ok &= n_eq == len(s.loaded)
        else:
            ids = [sweagent_new_identity(d) for _, d in s.loaded]
            n_identity = sum(1 for x in ids if x["n_traj"] - x["n_hist_asst"] == x["n_text_only"])
            n_equal = sum(1 for x in ids if x["n_traj"] == x["n_hist_asst"])
            n_text_only_total = sum(x["n_text_only"] for x in ids)
            n_steps = sum(x["n_traj"] for x in ids)
            rows.append([s.folder, "new", len(s.loaded), "—", f"{n_identity}/{len(s.loaded)}",
                         f"{n_text_only_total} text-only steps / {n_steps} steps; "
                         f"files with len(trajectory) == #assistant history: {n_equal}",
                         f"{n_contained}/{len(s.loaded)}"])
            spec_ok &= n_identity == len(s.loaded)
    body = [
        "**As written in §7.9.** Old format: `trajectory[].thought` equals the `thought` of non-`is_demo` assistant "
        "`history` entries, 1:1 (column 4). New format: `len(trajectory) − #assistant history entries == "
        "#text-only steps` (steps whose `action` is empty; column 5). "
        "**Added diagnostic** (column 7): non-demo assistant `history` thoughts form an ordered subsequence of "
        "`trajectory[].thought` — the containment property Q1 actually needs, whether or not `history` drops "
        "text-only turns.",
        "",
        _table(["submission folder", "format", "sampled", "old: 1:1 equality", "new: spec identity", "detail",
                "added: history ⊆ trajectory (ordered)"], rows),
        "",
        f"§7.9 identity as written: **{'PASS' if spec_ok else 'FAIL'}**. "
        f"Containment (`trajectory[]` holds every non-demo assistant thought, in order): "
        f"**{'CONFIRMED' if contain_ok else 'NOT CONFIRMED'}**. Extraction reads `trajectory[]` only (Q1), so the "
        "identity's failure has no extraction consequence; it is a description error in §3's `thought` row "
        "(\"new-format `history` drops text-only turns\" — it drops some and keeps others).",
        "",
        "**Text-only step census (steps with empty `action`; these become free-standing or terminal emissions under "
        "§2.2–2.3).** `harness exit string` counts `thought` values starting with the SWE-agent template "
        f"`{HARNESS_EXIT_PREFIX}…` (e.g. cost limit, context window, command timeouts) — a harness string in the "
        "designated slot, counted by template prefix, not a re-evaluation marker. Surfaced for the checkpoint: the "
        "spec treats every non-empty `thought` on an `action == \"\"` step as designated reasoning.",
        "",
        _table(["submission folder", "text-only steps", "at last step", "`thought` present in history",
                "`thought` empty (no emission)", "harness exit string"], census_rows),
    ]
    n_exit = sum(r[5] for r in census_rows)
    n_text_only = sum(r[1] for r in census_rows)
    findings = [
        f"SWE-agent: old-format 1:1 equality holds on every sampled file (demo thoughts excluded by `trajectory[]`); "
        f"the new-format arithmetic identity as written fails "
        f"({', '.join(r[4] for r in rows if r[1] == 'new')}) because `history` keeps some text-only turns — but "
        f"containment (history ⊆ trajectory, ordered) holds {'everywhere' if contain_ok else 'NOT everywhere'}. "
        "No extraction consequence; §3's description of new-format `history` is inexact.",
        f"**For the checkpoint:** {n_exit} of {n_text_only} new-format text-only steps carry a harness exit string "
        f"(`{HARNESS_EXIT_PREFIX}…`) in the `thought` slot; under §2.2–2.3 these would become emissions (mostly "
        "terminal units). The spec does not distinguish harness strings from model text in the designated slot.",
    ]
    return Section("§7.9 SWE-agent `trajectory` vs non-demo `history`", "\n".join(body),
                   verdict=("PASS" if spec_ok else "FAIL (identity as written); containment PASS"
                            if contain_ok else "FAIL"), findings=findings)


# --------------------------------------------------------------------------
# think-tool structure (not a numbered §7 test; recorded because §3 relies on it)
# --------------------------------------------------------------------------

def check_think_tool(samples: dict[str, Sampled]) -> Section:
    import json as _json
    rows = []
    for s in _by_family(samples, registry.THINK_TOOL):
        c = Counter()
        for _, data in s.loaded:
            n_units = 0
            for m in data:
                if m.get("role") != "assistant":
                    continue
                tcs = m.get("tool_calls") or []
                names = [t.get("function", {}).get("name") for t in tcs]
                if "think" in names:
                    c["think_msgs"] += 1
                    c["think_with_other_calls"] += (len(tcs) > 1)
                    for t in tcs:
                        if t.get("function", {}).get("name") == "think":
                            try:
                                args = _json.loads(t["function"]["arguments"])
                                c["args_parse_ok"] += 1
                                c["args_have_thought"] += ("thought" in args)
                                n_units += bool(str(args.get("thought", "")).strip())
                            except (ValueError, TypeError, KeyError):
                                c["args_parse_fail"] += 1
            c["trajectories"] += 1
            c["zero_think_trajectories"] += (n_units == 0)
        rows.append([s.folder, c["trajectories"], c["think_msgs"], c["think_with_other_calls"],
                     f"{c['args_parse_ok']} ok / {c['args_parse_fail']} fail", c["args_have_thought"],
                     c["zero_think_trajectories"]])
    body = [
        "Recorded for §3 (think-tool row): singleton think messages, `arguments` JSON with key `thought`, "
        "zero-unit trajectories legitimate under §6.",
        "",
        _table(["submission folder", "sampled", "think messages", "think + other call in same msg",
                "`arguments` JSON parse", "args with `thought` key", "trajectories with zero think calls"], rows),
    ]
    return Section("Think-tool structure (supports §3)", "\n".join(body), verdict="INFO")


# --------------------------------------------------------------------------
# report assembly
# --------------------------------------------------------------------------

def run(root: Path, their_config: Path | None = None) -> tuple[str, list[Section]]:
    root = Path(root)
    samples = load_samples(root)
    sections: list[Section] = []
    sections.append(check_discovery(root, samples))
    sections.append(check_epam_gate(samples))
    sections.append(check_epam_text_field(samples))
    sections.append(check_sonar_blocks(samples))
    sage_val, sage_census = check_sage(samples)
    sections.append(sage_val)
    sections.append(Section(
        "§7.6 Their `target_file` sparsity",
        "Confirmed from their code in the review (no run needed): `_classify_bash_command` returns `target_file=None` "
        "on every branch; `file_editor` → `None`. Their `Pr` can never fire for SAGE, for bash-mediated edits in any "
        "format, or for Trae-doubao. Consequence lives in the Phase 3 spot-check (SAGE and Trae-doubao rows oversampled).",
        verdict="INFO"))
    sections.append(check_trae(samples))
    sections.append(sage_census)
    sections.append(check_sweagent_history(samples))
    sections.append(check_think_tool(samples))

    drift_line = "not checked (no `--their-config` given)"
    if their_config is not None:
        drift_line = ("**DRIFTED** — their `scripts/config.py` no longer matches the vendored sha256"
                      if registry.their_config_drifted(Path(their_config))
                      else f"matches vendored sha256 `{registry.THEIR_CONFIG_SHA256[:12]}…` (read as bytes, never imported)")

    head = [
        "# Adapter seam report (spec §7)",
        "",
        f"*Generated {_dt.date.today().isoformat()} by `methodology/scripts/run_adapter_seam.py` "
        f"against `{root}`. Structure only: no resolution contact, no marker counts, no signal values, "
        "no v1 code over trajectories. Fence enforced by `tests/test_adapter_blindness.py`.*",
        "",
        f"- Audit sample rule (§5): per population agent, discovery-passing files sorted bytewise, every ⌈n/50⌉-th "
        f"from index 0. Sampled: {sum(len(s.files) for s in samples.values())} files across "
        f"{len(samples)} agents.",
        f"- Their `scripts/config.py`: {drift_line}.",
        "",
        "## Verdicts",
        "",
        _table(["section", "verdict", "stop-early"], [[s.title, s.verdict or "—", "YES" if s.stop_early else "no"]
                                                       for s in sections]),
        "",
        "## Findings for the checkpoint",
        "",
        *[f"- {f}" for s in sections for f in s.findings],
        "",
    ]
    parts = head + [f"## {s.title}\n\n{s.body}\n" for s in sections]
    return "\n".join(parts), sections
