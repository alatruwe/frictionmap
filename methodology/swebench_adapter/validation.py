"""Parse-validation harness (spec §6, §9.5): per-agent file-level and
unit-level failure rates over the §1 denominator, strict >10%, quarantine
listing with failure class, nothing silently skipped.

The >10% disposition is [A]'s (pre-reg §6, measure-then-dispose); this
module only measures and reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from swebench_adapter import registry
from swebench_adapter.discovery import NON_TRAJECTORY, discover
from swebench_adapter.extractors import extract
from swebench_adapter.loaders import FILE_FAILURE, UNIT_FAILURE, FileLevelFailure, load_trajectory_file

THRESHOLD = 0.10


@dataclass
class AgentValidation:
    folder: str
    family: str
    n_files: int                                    # denominator: instance-id-stem files
    n_file_failures: int = 0
    n_unit_failures: int = 0
    n_units: int = 0
    n_trajectories_with_units: int = 0
    n_zero_action_trajectories: int = 0             # parses, zero action steps — not a failure (§6)
    quarantine: list[tuple[str, str, str]] = field(default_factory=list)   # (filename, class, detail)

    @property
    def n_failures(self) -> int:
        return self.n_file_failures + self.n_unit_failures

    @property
    def rate(self) -> float:
        return 0.0 if self.n_files == 0 else self.n_failures / self.n_files

    @property
    def over_threshold(self) -> bool:
        return self.rate > THRESHOLD                # strict: 10.0% does not drop


def validate_agent(root: Path, folder: str) -> AgentValidation:
    sub = registry.resolve(folder)
    disc = discover(root / folder)
    v = AgentValidation(folder=folder, family=sub.family, n_files=len(disc.files))
    for path, cls in disc.quarantined:
        v.quarantine.append((path.name, NON_TRAJECTORY, "stem does not match <owner>__<repo>-<n>"))
    for path in disc.files:
        try:
            loaded = load_trajectory_file(path, folder)
        except FileLevelFailure as e:
            v.n_file_failures += 1
            v.quarantine.append((path.name, FILE_FAILURE, str(e)))
            continue
        r = extract(loaded)
        if not r.structure_present:
            v.n_unit_failures += 1
            v.quarantine.append((path.name, UNIT_FAILURE, f"designated structure absent for family {sub.family}"))
            continue
        v.n_units += len(r.units)
        v.n_trajectories_with_units += bool(r.units)
        v.n_zero_action_trajectories += r.anchoring.n_action_steps == 0
    return v


def validate(root: Path, quarantine_dir: Path | None = None) -> list[AgentValidation]:
    out = []
    for folder in registry.population_folders():
        v = validate_agent(root, folder)
        out.append(v)
        if quarantine_dir is not None:
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            lines = [f"{name}\t{cls}\t{detail}" for name, cls, detail in v.quarantine]
            (quarantine_dir / f"{folder}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    return out


def render(results: list[AgentValidation], root: Path, date: str) -> str:
    rows = []
    for v in results:
        rows.append([v.folder, v.family, v.n_files, v.n_file_failures, v.n_unit_failures,
                     f"{100 * v.rate:.2f}%", "**>10% — [A] decides**" if v.over_threshold else "no",
                     v.n_units, f"{v.n_trajectories_with_units}/{v.n_files}", v.n_zero_action_trajectories,
                     sum(1 for _, c, _ in v.quarantine if c == NON_TRAJECTORY)])
    head = "| " + " | ".join(["submission folder", "family", "instance-id files", "file-level failures",
                              "unit-level failures", "rate", "over 10% (strict)", "units", "trajectories with ≥1 unit",
                              "zero-action trajectories", "non_trajectory quarantined"]) + " |"
    table = [head, "|" + "---|" * 11] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    q = [(v.folder, name, cls, detail) for v in results for name, cls, detail in v.quarantine]
    qtable = ["| submission folder | file | class | detail |", "|---|---|---|---|"] + [
        f"| {f} | `{n}` | `{c}` | {d} |" for f, n, c, d in q] if q else ["(empty)"]
    return "\n".join([
        "# Adapter parse-validation report (spec §6)",
        "",
        f"*Generated {date} by `methodology/scripts/run_adapter_validation.py` against `{root}`. "
        "Every instance-id file of every population agent was loaded and extracted; nothing was skipped silently. "
        "Rates go back to [A] verbatim; the >10% disposition is not made here (pre-reg §6).*",
        "",
        "- **File-level failure:** JSON unreadable, or top-level shape does not match the family's §1 expectation.",
        "- **Unit-level failure:** file parses but the family's designated structure is absent "
        "(no `thought` keys / no `Thoughts` entries / no thinking block / no `THOUGHT:` / no `<think>`; n/a for think-tool).",
        "- **Denominator:** deduped instance-id-stem files; `non_trajectory` files sit outside both numerator and denominator.",
        "- **Rate:** (file + unit) / denominator; `>10%` strict. Zero units with structure present, and zero action steps, "
        "are agent behaviour, not failures (reported descriptively; see the audit report).",
        "",
        "## Per-agent rates",
        "",
        *table,
        "",
        "## Quarantine listing",
        "",
        f"Also written per agent under `methodology/adapter-quarantine/<folder>.txt` (class ∈ `file`, `unit`, `non_trajectory`).",
        "",
        *qtable,
        "",
    ])
