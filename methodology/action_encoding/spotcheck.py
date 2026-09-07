"""Seeded sample and symbol-distribution helpers for the reproducibility spot-check (Task 2).

Sampling rule (handoff, amended 2026-09-07): 5 × SAGE, 5 × Trae-doubao, 10 × uniform
across the remaining 11 agents — all drawn from the *joined* population only, since an
unjoined trajectory has no CSV row to compare against (Trae-doubao: 483 of 500).
"Uniform across the remaining 11 agents" is implemented as: 10 distinct agents drawn
uniformly from the 11, one trajectory drawn uniformly from each agent's joined set, so
the check covers 10 of their 11 remaining per-format parsers rather than clustering.
"""
from __future__ import annotations

import random
from collections import Counter

from swebench_adapter import registry

from .join import JoinedRow

SEED = 20260907
SAGE_FOLDER = "20251021_SalesforceAIResearch_SAGE_bash_only"
DOUBAO_FOLDER = "20250928_trae_doubao_seed_code"
N_SAGE, N_DOUBAO, N_REST = 5, 5, 10

# Their docstring's symbol inventory (extract_enriched_encoding_all.py header). `L` is
# the undifferentiated localization symbol used where Lb/Lt cannot be told apart.
SYMBOL_INVENTORY = ("Lb", "Lt", "Ls", "L", "P", "Ps", "Pi", "Pr", "Vp", "Vf", "Ve", "Vr", "E", "G")


def draw_sample(rows: list[JoinedRow], seed: int = SEED) -> list[JoinedRow]:
    rng = random.Random(seed)
    joined = sorted((r for r in rows if r.joined), key=lambda r: (r.submission_folder, r.instance_id))
    by_folder: dict[str, list[JoinedRow]] = {}
    for r in joined:
        by_folder.setdefault(r.submission_folder, []).append(r)
    sample = rng.sample(by_folder[SAGE_FOLDER], N_SAGE)
    sample += rng.sample(by_folder[DOUBAO_FOLDER], N_DOUBAO)
    rest = [f for f in registry.population_folders() if f not in (SAGE_FOLDER, DOUBAO_FOLDER)]
    assert len(rest) == 11
    for folder in sorted(rng.sample(rest, N_REST)):
        sample.append(rng.choice(by_folder[folder]))
    return sample


def symbol_distribution(encodings: list[str]) -> Counter[str]:
    c: Counter[str] = Counter()
    for e in encodings:
        c.update(e.split())
    return c


def never_fired(counts: Counter[str]) -> tuple[str, ...]:
    return tuple(s for s in SYMBOL_INVENTORY if counts[s] == 0)
