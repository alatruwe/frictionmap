"""Join their `enriched_encodings_all.csv` to our parsed population.

Their CSV has no submission-folder column. Its identity columns are
(`agent_name`, `llm_name`), written by their main() straight from
`SUBMISSION_META[folder]["agent"]` / `["llm"]`, and `instance_id`, which is
the file stem with `.traj` / `.json` / `.traj.json` removed. So the join key is
(agent, llm, instance_id): (agent, llm) comes from the vendored registry entry
for each population folder, instance_id from the discovery stem. No string
normalization of any kind is applied on either side.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from swebench_adapter import discovery, registry

Key = tuple[str, str, str]  # (agent_name, llm_name, instance_id)

TABLE_COLUMNS = ("submission_folder", "agent_name", "llm_name", "instance_id", "joined",
                 "enriched_encoding", "is_failed")


class DuplicateEncodingKey(ValueError):
    """Their CSV carried two rows for one (agent, llm, instance_id)."""


@dataclass(frozen=True)
class JoinedRow:
    submission_folder: str
    agent_name: str
    llm_name: str
    instance_id: str
    joined: bool
    enriched_encoding: str | None      # None when unjoined
    is_failed: int | None              # their column verbatim (0 resolved / 1 failed / -1 unknown); None when unjoined


@dataclass(frozen=True)
class AgentCoverage:
    submission_folder: str
    n_population: int
    n_joined: int
    unjoined_ids: tuple[str, ...]

    @property
    def n_unjoined(self) -> int:
        return self.n_population - self.n_joined

    @property
    def coverage(self) -> float:
        return self.n_joined / self.n_population if self.n_population else 0.0

    @property
    def complete(self) -> bool:
        return self.n_unjoined == 0


def load_encodings(csv_path: Path) -> dict[Key, dict[str, str]]:
    """Index their CSV by (agent_name, llm_name, instance_id); refuse duplicates."""
    rows: dict[Key, dict[str, str]] = {}
    with Path(csv_path).open(newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["agent_name"], row["llm_name"], row["instance_id"])
            if key in rows:
                raise DuplicateEncodingKey(str(key))
            rows[key] = row
    return rows


def join_folder(root: Path, folder: str, encodings: dict[Key, dict[str, str]]) -> list[JoinedRow]:
    """One row per population file of `folder` (discovery rule, spec §1), in discovery order."""
    sub = registry.resolve(folder)
    out: list[JoinedRow] = []
    for instance_id in discovery.discover(Path(root) / folder).instance_ids:
        row = encodings.get((sub.agent, sub.llm, instance_id))
        if row is None:
            out.append(JoinedRow(folder, sub.agent, sub.llm, instance_id, False, None, None))
        else:
            out.append(JoinedRow(folder, sub.agent, sub.llm, instance_id, True,
                                 row["enriched_encoding"], int(row["is_failed"])))
    return out


def join_population(root: Path, encodings: dict[Key, dict[str, str]]) -> list[JoinedRow]:
    rows: list[JoinedRow] = []
    for folder in registry.population_folders():
        rows.extend(join_folder(root, folder, encodings))
    return rows


def coverage(rows: list[JoinedRow]) -> list[AgentCoverage]:
    """Per-agent coverage in registry order; unjoined ids listed, never dropped."""
    out = []
    for folder in registry.population_folders():
        mine = [r for r in rows if r.submission_folder == folder]
        out.append(AgentCoverage(
            submission_folder=folder,
            n_population=len(mine),
            n_joined=sum(1 for r in mine if r.joined),
            unjoined_ids=tuple(r.instance_id for r in mine if not r.joined),
        ))
    return out


def csv_rows_for_population_not_on_disk(rows: list[JoinedRow], encodings: dict[Key, dict[str, str]]) -> list[Key]:
    """CSV rows carrying a population (agent, llm) whose instance_id has no file — the reverse gap."""
    on_disk = {(r.agent_name, r.llm_name, r.instance_id) for r in rows}
    pop_keys = {(r.agent_name, r.llm_name) for r in rows}
    return sorted(k for k in encodings if (k[0], k[1]) in pop_keys and k not in on_disk)


def write_table(rows: list[JoinedRow], path: Path) -> None:
    with Path(path).open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(TABLE_COLUMNS)
        for r in rows:
            w.writerow([r.submission_folder, r.agent_name, r.llm_name, r.instance_id,
                        "1" if r.joined else "0",
                        r.enriched_encoding if r.joined else "",
                        "" if r.is_failed is None else str(r.is_failed)])


def render_coverage(cov: list[AgentCoverage]) -> str:
    lines = ["| submission folder | n population | n joined | n unjoined | coverage |", "|---|---|---|---|---|"]
    for c in cov:
        lines.append(f"| {c.submission_folder} | {c.n_population} | {c.n_joined} | {c.n_unjoined} "
                     f"| {100 * c.coverage:.2f}% |")
    return "\n".join(lines)
