"""Synthetic-sequence tests for the anchoring engine, spec §2 rules 2–4 (§9.3)."""
from __future__ import annotations

from swebench_adapter.anchoring import (FREE_STANDING, IN_STEP, JOINER, TERMINAL, ActionStep, Emission,
                                        anchor, recover_fragments)

E, A = Emission, ActionStep


def test_rule1_in_step_emission_attaches_to_its_own_containers_action_set():
    r = anchor([E("think a", 0), A(0, actions=("edit x.py",)), E("think b", 1), A(1, actions=("run",))])
    assert [u.text for u in r.units] == ["think a", "think b"]
    assert [u.anchor_step for u in r.units] == [0, 1]
    assert [u.anchor_container for u in r.units] == [0, 1]
    assert r.units[0].actions == ("edit x.py",)
    assert all(u.emission_kind == IN_STEP and not u.terminal for u in r.units)
    assert r.n_action_steps == 2 and r.n_empty_anchors == 0


def test_rule2_free_standing_emission_forward_attaches_to_next_action_step():
    # EPAM / think-tool shape: reasoning lives in its own container, action in the next.
    r = anchor([E("plan", 0), A(1, actions=("view",)), E("more", 2), A(3, actions=("edit",))])
    assert [(u.text, u.anchor_step, u.anchor_container) for u in r.units] == [("plan", 0, 1), ("more", 1, 3)]
    assert all(u.emission_kind == FREE_STANDING for u in r.units)


def test_rule2_several_free_standing_emissions_before_one_action_concatenate_in_order():
    r = anchor([E("one", 0), E("two", 1), E("three", 2), A(3)])
    (u,) = r.units
    assert u.text == "one" + JOINER + "two" + JOINER + "three"
    assert u.fragment_count == 3
    assert recover_fragments(u) == ["one", "two", "three"]
    assert [f.container for f in u.fragments] == [0, 1, 2]


def test_rule2_free_standing_then_in_step_mix_is_free_standing_with_fragment_kinds_stored():
    # Sonar-like: an assistant message with thinking but no tool_calls, then one with both.
    r = anchor([E("free", 0), E("in", 1), A(1)])
    (u,) = r.units
    assert u.emission_kind == FREE_STANDING
    assert [f.kind for f in u.fragments] == [FREE_STANDING, IN_STEP]


def test_rule3_reasoning_after_last_action_forms_terminal_unit():
    r = anchor([E("a", 0), A(0), E("wrap-up", 1), E("more wrap-up", 2)])
    assert len(r.units) == 2
    t = r.units[-1]
    assert t.terminal and t.emission_kind == TERMINAL
    assert t.anchor_step is None and t.anchor_container is None and t.actions == ()
    assert t.text == "wrap-up" + JOINER + "more wrap-up" and t.fragment_count == 2
    assert r.n_terminal_units == 1


def test_rule3_reasoning_only_trajectory_is_a_single_terminal_unit():
    r = anchor([E("only thinking", 0)])
    assert r.n_action_steps == 0 and len(r.units) == 1 and r.units[0].terminal


def test_rule4_action_steps_with_no_preceding_reasoning_produce_no_unit():
    r = anchor([A(0), A(1), E("t", 2), A(2), A(3)])
    assert [u.anchor_step for u in r.units] == [2]
    assert r.n_action_steps == 4 and r.n_empty_anchors == 3


def test_rule4_empty_or_whitespace_text_is_no_emission_and_never_a_zero_length_unit():
    r = anchor([E("", 0), A(0), E("   \n\t", 1), A(1), E(" ", 2)])
    assert r.units == []
    assert r.n_empty_emissions == 3 and r.n_emissions == 0
    assert r.n_empty_anchors == 2         # both anchors empty: the blank slots do not count as reasoning
    # whitespace-only followed by real text: only the real text forms the unit
    r2 = anchor([E("  ", 0), E("real", 1), A(1)])
    assert [u.text for u in r2.units] == ["real"] and r2.units[0].fragment_count == 1


def test_rule5_joiner_and_rule6_offsets_are_exact_and_reversible():
    r = anchor([E("αβ\nγ", 0), E("", 1), E("δ", 2), A(2)])
    (u,) = r.units
    assert u.text == "αβ\nγ\n\nδ"
    assert [(f.start, f.end) for f in u.fragments] == [(0, 4), (6, 7)]
    assert recover_fragments(u) == ["αβ\nγ", "δ"]
    assert u.fragment_count == 2


def test_per_emission_meta_travels_onto_the_fragment_untouched():
    r = anchor([E("x", 0, meta={"first_closer_offset": 12, "num_tokens": 3}), A(0)])
    assert r.units[0].fragments[0].meta == {"first_closer_offset": 12, "num_tokens": 3}


def test_single_fragment_unit_degrades_to_the_native_emission():
    # Option B equals option A when multiplicity is 1 (spec §2.6).
    r = anchor([E("solo", 0), A(0)])
    (u,) = r.units
    assert u.fragment_count == 1 and recover_fragments(u) == [u.text]
