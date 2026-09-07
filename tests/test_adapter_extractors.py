"""Family extractors (spec §3, §9.4) on synthetic files shaped like the real ones."""
from __future__ import annotations

import json

from swebench_adapter import registry
from swebench_adapter.anchoring import FREE_STANDING, IN_STEP, TERMINAL
from swebench_adapter.extractors import (SAGE_RULE_VERSION, TRAE_RULE_VERSION, extract, sage_emission,
                                         trae_emission)
from swebench_adapter.loaders import load_trajectory_file
from tests._adapter_fakes import make_replication_tree


def _extract(tmp_path, folder, fname, content):
    root = make_replication_tree(tmp_path, submissions={folder: {fname: content}})
    return extract(load_trajectory_file(root / folder / fname, folder))


def test_thought_old_format_reads_trajectory_only_and_tracks_edit_target(tmp_path, fence):
    data = {"trajectory": [
        {"thought": "open the file", "action": "open a/b.py\n"},
        {"thought": "edit it", "action": "edit 1:2\nx\nend_of_edit"},
        {"thought": "", "action": "python a/b.py"},
        {"thought": "Exit due to cost limit", "action": ""},
    ], "history": [{"role": "assistant", "thought": "DEMO", "is_demo": True, "content": "x"}]}
    r = _extract(tmp_path, "20240402_sweagent_gpt4", "x__y-1.traj", data)
    assert r.structure_present and r.family == registry.THOUGHT and r.rule_version is None
    assert [u.text for u in r.units] == ["open the file", "edit it"]
    assert [u.emission_kind for u in r.units] == [IN_STEP, IN_STEP]
    assert r.units[0].anchor_files == ("a/b.py",) and r.units[1].anchor_files == ("a/b.py",)
    assert r.anchoring.n_action_steps == 3 and r.anchoring.n_empty_anchors == 1 and r.anchoring.n_empty_emissions == 1
    assert r.anchoring.n_harness_strings == 1 and not any(u.unit.terminal for u in r.units)
    assert r.free_standing_texts == ["Exit due to cost limit"] and r.notes["text_only_steps"] == 1
    assert "DEMO" not in json.dumps([u.to_dict() for u in r.units])
    assert r.units[0].container == "trajectory[].thought" and r.units[0].instance_id == "x__y-1"


def test_thought_new_format_text_only_turn_forward_attaches_and_summary_is_terminal(tmp_path, fence):
    data = {"trajectory": [
        {"thought": "plan", "action": ""},
        {"thought": "look", "action": "str_replace_editor view /testbed/a.py"},
        {"thought": "Perfect! Summary…", "action": ""},
    ], "history": []}
    r = _extract(tmp_path, "20250511_sweagent_lm_32b", "x__y-1.traj", data)
    u0, u1 = r.units
    assert u0.text == "plan\n\nlook" and u0.unit.fragment_count == 2 and u0.emission_kind == FREE_STANDING
    assert [f.kind for f in u0.unit.fragments] == [FREE_STANDING, IN_STEP]
    assert u0.anchor_files == ("/testbed/a.py",)
    assert u1.unit.terminal and u1.emission_kind == TERMINAL and u1.anchor_files == ()


def test_thought_structure_absent_is_unit_level_failure(tmp_path, fence):
    r = _extract(tmp_path, "20240402_sweagent_gpt4", "x__y-1.traj",
                 {"trajectory": [{"action": "ls", "observation": ""}], "history": []})
    assert not r.structure_present and r.units == [] and r.anchoring.n_action_steps == 1


def test_epam_free_standing_thoughts_attach_to_next_action_in_document_order(tmp_path, fence):
    body = json.dumps([{
        "zz": {"author_name": "Thoughts", "message": "first", "input_text": ""},
        "aa": {"author_name": "Str Replace Editor", "message": "obs",
               "input_text": "{'command': 'view', 'path': 'x/a.py'}"},
        "mm": {"author_name": "Thoughts", "message": "  ", "input_text": ""},
        "bb": {"author_name": "Run Command Line Tool", "message": "obs",
               "input_text": "{'command': 'cd /r && python t.py'}"},
        "cc": {"author_name": "Thoughts", "message": "wrap", "input_text": ""},
    }])
    r = _extract(tmp_path, "20250804_epam-ai-run-claude-4-sonnet", "x__y-1.traj", body)
    assert r.structure_present and r.family == registry.EPAM
    assert [(u.text, u.emission_kind, u.anchor_files) for u in r.units] == [
        ("first", FREE_STANDING, ("x/a.py",)), ("wrap", TERMINAL, ())]
    assert r.anchoring.n_empty_emissions == 1 and r.anchoring.n_empty_anchors == 1
    assert [a.paths for a in r.actions] == [("x/a.py",), ("t.py",)]
    assert r.anchoring.n_harness_strings == 0      # D3 prefixes are SWE-agent only
    r2 = _extract(tmp_path, "20250804_epam-ai-run-claude-4-sonnet", "x__y-2.traj",
                  json.dumps([{"a": {"author_name": "Thoughts", "message": "Exit due to X", "input_text": ""}}]))
    assert r2.units[0].text == "Exit due to X"


def test_sage_rule_sage_1_label_excluded_bash_fence_is_action(tmp_path, fence):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
            {"role": "assistant", "content": "THOUGHT: Look at it.\n```python\nx\n```\n```bash\ncat a/b.py\n```"},
            {"role": "user", "content": "[{'type': 'text', 'text': 'obs'}]"},
            {"role": "assistant", "content": "prose\nTHOUGHT: no fence here"},
            {"role": "assistant", "content": "no designated text\n```bash\nls\n```"}]
    r = _extract(tmp_path, "20251021_SalesforceAIResearch_SAGE_bash_only", "x__y-1.traj.json",
                 {"messages": msgs, "info": {}, "instance_id": "x", "trajectory_format": "f"})
    assert r.structure_present and r.rule_version == SAGE_RULE_VERSION
    assert [u.text for u in r.units] == [" Look at it.\n```python\nx\n```\n", " no fence here"]
    assert r.units[0].emission_kind == IN_STEP and r.units[0].anchor_files == ("a/b.py",)
    assert r.units[1].emission_kind == FREE_STANDING and r.units[1].anchor_files == ()
    assert r.notes["thought_offset_nonzero"] == 1 and r.notes["thought_absent"] == 1
    assert r.notes["non_bash_fences_before_bash_msgs"] == 1 and r.notes["missing_bash_fence"] == 1
    assert r.units[0].unit.fragments[0].meta == {"span_start": 8, "span_end": 37}


def test_sage_emission_boundaries():
    assert sage_emission("THOUGHT: a\n```bash\nls\n```")[0] == " a\n"
    assert sage_emission("no label")[0] is None
    assert sage_emission("THOUGHT: to end")[0] == " to end"


def test_sonar_thinking_block_attaches_to_tool_calls_free_standing_without(tmp_path, fence):
    def msg(think, calls):
        return {"role": "assistant", "blocks": [{"block_type": "thinking", "content": think, "num_tokens": 7},
                                                {"block_type": "text", "text": "t"}],
                "additional_kwargs": {"tool_calls": calls}}
    call = {"function": {"name": "str_replace_based_edit_tool",
                         "arguments": json.dumps({"command": "view", "path": "/t/a.py"})}}
    data = [{"role": "system", "blocks": []}, msg("free", []), msg("in", [call]), {"role": "tool", "blocks": []},
            msg("bye", [])]
    r = _extract(tmp_path, "20251205_sonar-foundation-agent_claude-opus-4-5", "x__y-1.json", data)
    assert r.structure_present
    u0, u1 = r.units
    assert u0.text == "free\n\nin" and u0.emission_kind == FREE_STANDING and u0.anchor_files == ("/t/a.py",)
    assert u0.unit.fragments[0].meta == {"num_tokens": 7}
    assert u1.unit.terminal and r.free_standing_texts == ["free", "bye"]


def test_trae_rule_trae_b_1_last_closer_first_closer_offset_abandoned_call_kept(tmp_path, fence):
    aborted = ("<think>a</think>\n<function=str_replace_editor>\n<parameter=path>/x.py</parameter>\n#hm\n</think>\n"
               "<function=execute_bash>\n<parameter=command>cat /y.py</parameter>\n</function>")
    data = [{"role": "user", "content": "u"},
            {"role": "assistant", "content": "<think>one</think>\n<function=finish>\n</function>"},
            {"role": "assistant", "content": aborted},
            {"role": "assistant", "content": "<think>bye</think>\nDone."}]
    r = _extract(tmp_path, "20250928_trae_doubao_seed_code", "x__y-1.json", data)
    assert r.structure_present and r.rule_version == TRAE_RULE_VERSION
    assert [u.text for u in r.units][0] == "one"
    u1 = r.units[1]
    assert u1.text == "a</think>\n<function=str_replace_editor>\n<parameter=path>/x.py</parameter>\n#hm\n"
    assert u1.anchor_files == ("/y.py",) and u1.emission_kind == IN_STEP
    meta = u1.unit.fragments[0].meta
    assert meta["closers"] == 2 and meta["first_closer_offset"] == 8 and meta["span_start"] == 7
    assert r.notes["multi_closer_messages"] == 1
    assert r.units[2].unit.terminal and r.units[2].text == "bye"


def test_trae_emission_edge_cases():
    assert trae_emission("no tags")[0] is None
    t, f = trae_emission("<think>unclosed")
    assert t == "unclosed" and f["unclosed"] and f["closers"] == 0
    t, f = trae_emission("<think></think>")
    assert t == "" and f["closers"] == 1


def test_think_tool_think_calls_are_free_standing_and_other_calls_anchor(tmp_path, fence):
    def call(name, args, cid="c"):
        return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    data = [{"role": "system", "content": "s"},
            {"role": "assistant", "content": [{"type": "text", "text": "narration is not designated"}],
             "tool_calls": [call("execute_bash", {"command": "ls"})]},
            {"role": "assistant", "content": [], "tool_calls": [call("think", {"thought": "plan"})]},
            {"role": "tool", "content": "ok"},
            {"role": "assistant", "content": [],
             "tool_calls": [call("str_replace_editor", {"command": "view", "path": "/t/a.py"})]},
            {"role": "assistant", "content": [], "tool_calls": [call("think", {"thought": "   "})]}]
    r = _extract(tmp_path, "20250524_openhands_claude_4_sonnet", "x__y-1.json", data)
    assert r.structure_present                        # n/a → True
    (u,) = r.units
    assert u.text == "plan" and u.emission_kind == FREE_STANDING and u.anchor_files == ("/t/a.py",)
    assert r.anchoring.n_action_steps == 2 and r.anchoring.n_empty_anchors == 1 and r.anchoring.n_empty_emissions == 1
    assert u.container.startswith("tool_calls")
    zero = _extract(tmp_path, "20250716_openhands_kimi_k2", "x__y-2.json",
                    [{"role": "assistant", "content": [], "tool_calls": [call("execute_bash", {"command": "ls"})]}])
    assert zero.structure_present and zero.units == []


def test_unit_record_to_dict_carries_provenance(tmp_path, fence):
    r = _extract(tmp_path, "20250928_trae_doubao_seed_code", "x__y-1.json",
                 [{"role": "assistant", "content": "<think>t</think><function=execute_bash>"
                                                   "<parameter=command>cat a.py</parameter></function>"}])
    d = r.units[0].to_dict()
    assert d["submission"] == "20250928_trae_doubao_seed_code" and d["file"] == "x__y-1.json"
    assert d["rule_version"] == "trae-b-1" and d["anchor_step"] == 0 and d["anchor_files"] == ["a.py"]
    assert d["fragments"][0]["kind"] == IN_STEP and d["fragment_count"] == 1 and d["text"] == "t"
