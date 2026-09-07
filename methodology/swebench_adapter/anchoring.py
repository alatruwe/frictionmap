"""Family-agnostic anchoring engine (spec §2, §9.3).

Input: an ordered sequence of events — designated `Emission`s and `ActionStep`s
— produced by a family extractor. Output: step-anchored units per §2.

Rules implemented:
  1. Decision point = action step. A unit's anchor is always an action step.
  2. Free-standing emissions (container carries no action) forward-attach to
     the next action step. In-step emissions (same container as the action)
     attach to that step's action set.
  3. Terminal unit: reasoning after the last action step forms a unit with no
     anchored action, flagged `terminal=True`.
  4. Empty anchors: an action step with no preceding reasoning produces no
     unit. Empty or whitespace-only designated text is *no emission* — it is
     counted (`n_empty_emissions`) and dropped; zero-length units never exist.
  5. Joiner is "\\n\\n"; `Unit.text` is the judge input.
  6. Reversibility: every unit stores `fragment_count` and per-fragment
     (start, end) offsets into `text`, so the native-emission unit is fully
     recoverable from stored metadata.

The engine does not know families. Family-specific per-fragment metadata (Trae
first-closer offset, Sonar `num_tokens`, ...) travels in `Emission.meta` and is
copied onto the `Fragment` untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JOINER = "\n\n"

IN_STEP = "in-step"
FREE_STANDING = "free-standing"
TERMINAL = "terminal"


@dataclass(frozen=True)
class Emission:
    """One designated-reasoning slot as emitted by the harness."""
    text: str
    container: int                          # index of the message / step / entry carrying it
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionStep:
    """One action step: a container whose action set is non-empty."""
    container: int
    actions: tuple[Any, ...] = ()           # opaque to the engine; consumed by the path layer (§8)


Event = Emission | ActionStep


@dataclass(frozen=True)
class Fragment:
    text: str
    start: int                              # offsets into Unit.text
    end: int
    container: int
    kind: str                               # IN_STEP | FREE_STANDING
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Unit:
    text: str
    fragments: tuple[Fragment, ...]
    anchor_step: int | None                 # ordinal of the anchoring action step (0-based); None if terminal
    anchor_container: int | None
    actions: tuple[Any, ...]
    terminal: bool
    emission_kind: str                      # IN_STEP | FREE_STANDING | TERMINAL

    @property
    def fragment_count(self) -> int:
        return len(self.fragments)


@dataclass
class AnchoringResult:
    units: list[Unit]
    n_action_steps: int
    n_empty_anchors: int                    # action steps with no preceding reasoning (rule 4)
    n_empty_emissions: int                  # designated slots empty / whitespace-only (rule 4, Q3)
    n_emissions: int                        # non-empty emissions seen

    @property
    def n_terminal_units(self) -> int:
        return sum(1 for u in self.units if u.terminal)


def _is_empty(text: str) -> bool:
    return not text or not text.strip()


def _build_unit(pending: list[Emission], step: ActionStep | None, step_ordinal: int | None) -> Unit:
    fragments: list[Fragment] = []
    pos = 0
    for i, em in enumerate(pending):
        if i:
            pos += len(JOINER)
        kind = IN_STEP if step is not None and em.container == step.container else FREE_STANDING
        fragments.append(Fragment(text=em.text, start=pos, end=pos + len(em.text),
                                  container=em.container, kind=kind, meta=dict(em.meta)))
        pos += len(em.text)
    text = JOINER.join(em.text for em in pending)
    if step is None:
        emission_kind = TERMINAL
    elif all(f.kind == IN_STEP for f in fragments):
        emission_kind = IN_STEP
    else:
        # Any free-standing fragment makes the unit free-standing; per-fragment
        # kinds are stored so the mix is recoverable.
        emission_kind = FREE_STANDING
    return Unit(text=text, fragments=tuple(fragments), anchor_step=step_ordinal,
                anchor_container=None if step is None else step.container,
                actions=() if step is None else tuple(step.actions),
                terminal=step is None, emission_kind=emission_kind)


def anchor(events: list[Event]) -> AnchoringResult:
    """Turn an ordered event sequence into step-anchored units (spec §2)."""
    units: list[Unit] = []
    pending: list[Emission] = []
    n_steps = n_empty_anchors = n_empty_emissions = n_emissions = 0
    for ev in events:
        if isinstance(ev, Emission):
            if _is_empty(ev.text):
                n_empty_emissions += 1
                continue
            n_emissions += 1
            pending.append(ev)
        elif isinstance(ev, ActionStep):
            if pending:
                units.append(_build_unit(pending, ev, n_steps))
                pending = []
            else:
                n_empty_anchors += 1
            n_steps += 1
        else:
            raise TypeError(f"unknown event {ev!r}")
    if pending:
        units.append(_build_unit(pending, None, None))
    return AnchoringResult(units=units, n_action_steps=n_steps, n_empty_anchors=n_empty_anchors,
                           n_empty_emissions=n_empty_emissions, n_emissions=n_emissions)


def recover_fragments(unit: Unit) -> list[str]:
    """Option A (native-emission unit) recovered from stored offsets."""
    return [unit.text[f.start:f.end] for f in unit.fragments]
