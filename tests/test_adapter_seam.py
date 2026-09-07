"""Seam-suite helpers with real logic (spec §7): EPAM alternation and path
resolution classifiers, Trae tag census, SAGE message census, SWE-agent
containment. Synthetic inputs; the suite itself runs against the download."""
from __future__ import annotations

from swebench_adapter.seam import (epam_alternation, epam_path_resolution, sage_message_census,
                                   sweagent_history_contained, sweagent_old_equality, text_only_step_census,
                                   trae_message_census)


def T(msg):
    return {"author_name": "Thoughts", "message": msg, "input_text": ""}


def A(input_text):
    return {"author_name": "Str Replace Editor", "message": "obs", "input_text": input_text}


def test_epam_alternation_counts_consecutive_and_unpreceded():
    clean = epam_alternation([T("a"), A("{}"), T("b"), A("{}"), T("wrap")])
    assert clean["consecutive_thoughts"] == 0 and clean["action_without_preceding_thought"] == 0
    assert clean["trailing_thoughts"] == 1 and clean["thoughts"] == 3 and clean["actions"] == 2
    bad = epam_alternation([A("{}"), T("a"), T("b"), A("{}"), A("{}")])
    assert bad["consecutive_thoughts"] == 1
    assert bad["action_without_preceding_thought"] == 2 and bad["action_after_action"] == 1


def test_epam_path_resolution_classifies_next_previous_both_neither():
    entries = [
        T("look at astropy/modeling/separable.py"), A("{'command': 'view', 'path': 'astropy/modeling/separable.py'}"),
        T("now core.py"), A("{'path': 'x/core.py'}"),                       # basename hits next only
        T("still core.py"), A("{'path': 'y/other.py'}"),                    # basename hits previous only
        T("edit other.py and core.py"), A("{'path': 'y/other.py'}"),        # both
        T("no file here"), A("{}"),                                         # no name
        T("ghost.py?"), A("{}"),                                            # neither
    ]
    r = epam_path_resolution(entries)
    assert r["basename"] == {"next": 2, "previous": 1, "both": 1, "no_name": 1, "neither": 1}
    # full-token variant: "core.py" is not a substring of "x/core.py"? it is — but "astropy/modeling/separable.py" is
    # exact; the difference shows on the previous-only case which needs the full token "core.py" in 'x/core.py'.
    assert r["full"]["next"] >= 1 and r["full"]["no_name"] == 1


def test_trae_message_census_flags_multi_closer_and_function_placement():
    clean = trae_message_census("<think>a</think>\n<function=bash>\n<parameter=command>ls</parameter>\n</function>")
    assert clean["openers"] == 1 and clean["closers"] == 1 and not clean["function_before_last_closer"]
    multi = trae_message_census("<think>a</think> more </think> and more</think>\n<function=x></function>")
    assert multi["closers"] == 3 and not multi["function_before_last_closer"] and multi["first_closer_offset"] == 8
    aborted = trae_message_census(
        "<think>a</think>\n<function=e>\n<parameter=file_text>#hm\n</think>\n<function=e>\n</function>")
    assert aborted["function_before_last_closer"] and not aborted["closed_function_before_last_closer"]
    closed = trae_message_census("<think>a</think><function=e></function> hmm </think><function=f></function>")
    assert closed["closed_function_before_last_closer"]
    assert closed["function_offsets"] == [16, 52] and closed["closer_offsets"] == [8, 44]


def test_sage_message_census_offsets_fences_and_template_boundary():
    m = "THOUGHT: look\n```python\nprint(1)\n```\n```bash\ncat x.py\n```"
    f = sage_message_census(m)
    assert f["thought_offset"] == 0 and f["has_bash_fence"] and f["opener_langs"] == ("python", "bash")
    assert f["non_bash_fences_before_bash"] == 1 and not f["text_after_last_fence"] and f["template_emission_nonempty"]
    absent = sage_message_census("no designated text\n```bash\nls\n```\ntrailing")
    assert absent["thought_offset"] == -1 and not absent["template_emission_nonempty"]
    assert absent["text_after_last_fence"]
    prose = sage_message_census("Sure.\nTHOUGHT: x\n```bash\nls\n```")
    assert prose["thought_offset"] == 6
    nobash = sage_message_census("THOUGHT: only text")
    assert not nobash["has_bash_fence"] and nobash["template_emission_nonempty"]
    empty = sage_message_census("THOUGHT:   \n```bash\nls\n```")
    assert not empty["template_emission_nonempty"]


def test_sweagent_old_equality_ignores_demo_entries():
    data = {"trajectory": [{"thought": "a", "action": "ls"}, {"thought": "b", "action": "cat"}],
            "history": [{"role": "system", "content": ""},
                        {"role": "assistant", "thought": "demo", "is_demo": True},
                        {"role": "assistant", "thought": "a"}, {"role": "user", "content": "obs"},
                        {"role": "assistant", "thought": "b"}]}
    assert sweagent_old_equality(data) and sweagent_history_contained(data)
    data["history"].append({"role": "assistant", "thought": "extra"})
    assert not sweagent_old_equality(data) and not sweagent_history_contained(data)


def test_text_only_step_census_and_containment_when_history_drops_a_turn():
    data = {"trajectory": [{"thought": "a", "action": "ls"}, {"thought": "summary", "action": ""},
                           {"thought": "b", "action": "cat"}, {"thought": "Exit due to cost limit", "action": ""}],
            "history": [{"role": "assistant", "thought": "a"}, {"role": "assistant", "thought": "b"},
                        {"role": "assistant", "thought": "Exit due to cost limit"}]}
    assert sweagent_history_contained(data)
    c = text_only_step_census(data)
    assert c["text_only_steps"] == 2 and c["last_step"] == 1 and c["thought_in_history"] == 1
    assert c["harness_exit_string"] == 1 and c["thought_empty"] == 0
