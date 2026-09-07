"""Path-extraction layer (spec §8, §9.7): per-format fixtures + table-driven bash rules."""
from __future__ import annotations

import pytest

from swebench_adapter.paths import (OldSweAgentState, action_from_args, bash_paths, parse_epam_input_text,
                                    strip_cd_prefix, sweagent_new_action, sweagent_old_action, trae_actions)

BASH_RULE_TABLE = [
    # R1 cd prefix stripping
    ("cd /repos/x && python reproduce_issue.py", ["reproduce_issue.py"]),
    ("cd /testbed && cd sub && cat a/b.py", ["a/b.py"]),
    ("cd /testbed; grep -rn foo astropy/", ["astropy/"]),
    # R2 read commands
    ("cat astropy/io/ascii/qdp.py", ["astropy/io/ascii/qdp.py"]),
    ("head -n 20 setup.py", ["setup.py"]),
    ("tail -50 /tmp/log.txt", ["/tmp/log.txt"]),
    ("less README.md", ["README.md"]),
    ("cat a.py b.py", ["a.py", "b.py"]),
    # R3 pattern commands: first positional is the script/pattern
    ("sed -n '20,90p' astropy/io/ascii/qdp.py", ["astropy/io/ascii/qdp.py"]),
    ("sed -i 's/a/b/' x.py", ["x.py"]),
    ("sed -i -e 's/a/b/' x.py", ["x.py"]),
    ("grep -rn 'def separability_matrix' astropy/modeling/", ["astropy/modeling/"]),
    ("grep -n foo a.py b.py", ["a.py", "b.py"]),
    ("grep -r --include=*.py foo src/", ["src/"]),
    ("grep -e pattern file.txt", ["file.txt"]),
    ("rg -n 'class Foo' sympy/core", ["sympy/core"]),
    ("awk '{print $1}' data.csv", ["data.csv"]),
    ("grep foo", []),                                     # pattern only, no path
    # R4 python script
    ("python reproduce.py", ["reproduce.py"]),
    ("python3 test_edge.py --flag", ["test_edge.py"]),
    ("python -m pytest astropy/modeling/tests/test_x.py", []),   # -m is out of scope
    ("python -c 'print(1)'", []),
    ("python", []),
    # R5 redirects
    ("echo hi > out.txt", ["out.txt"]),
    ("python run.py >> log.txt", ["run.py", "log.txt"]),
    ("ls > listing.txt 2>&1", ["listing.txt"]),
    # compound
    ("cat a.py | grep foo", ["a.py"]),
    ("cat a.py && python b.py", ["a.py", "b.py"]),
    ("find . -name '*.py' | head -20", []),               # find is out of scope; head has no path
    # out of scope / no path
    ("ls -la", []),
    ("git status", []),
    ("pip install -e .", []),
    ("DJANGO_SETTINGS_MODULE=x python manage.py test", ["manage.py"]),
]


@pytest.mark.parametrize("cmd,expected", BASH_RULE_TABLE)
def test_bash_rule_table(cmd, expected):
    assert bash_paths(cmd) == expected


def test_strip_cd_prefix_is_repeated_and_prefix_only():
    assert strip_cd_prefix("cd a && cd b && ls") == "ls"
    assert strip_cd_prefix("ls && cd a") == "ls && cd a"


def test_bash_paths_survive_unbalanced_quotes():
    assert bash_paths("cat it's.py") == ["it's.py"] or bash_paths("cat it's.py") == ["its.py"]


# ---- structured args per format ---------------------------------------------

def test_epam_input_text_literal_eval_never_json():
    d = parse_epam_input_text("{'command': 'view', 'path': 'django/contrib/auth/forms.py'}")
    assert d == {"command": "view", "path": "django/contrib/auth/forms.py"}
    # apostrophes inside commands — the case their quote-swap fallback breaks on
    d = parse_epam_input_text("{'command': \"cd /repos && python -c 'print(1)' > it's.txt\"}")
    assert d["command"].endswith("it's.txt")
    assert parse_epam_input_text("not a dict") is None and parse_epam_input_text("[1, 2]") is None
    a = action_from_args("Str Replace Editor", {"command": "view", "path": "x/y.py"})
    assert a.paths == ("x/y.py",) and a.command is None
    a = action_from_args("Run Command Line Tool", {"command": "cd /r && python t.py"})
    assert a.paths == ("t.py",) and a.command == "cd /r && python t.py"


def test_openhands_and_sonar_structured_args():
    assert action_from_args("str_replace_editor", {"command": "view", "path": "/testbed/a.py"}).paths == ("/testbed/a.py",)
    assert action_from_args("str_replace_based_edit_tool", {"command": "create", "path": "/t/b.py",
                                                            "file_text": "x"}).paths == ("/t/b.py",)
    assert action_from_args("execute_bash", {"command": "cat /testbed/c.py"}).paths == ("/testbed/c.py",)
    assert action_from_args("bash", {"command": "sed -n '1,5p' d.py"}).paths == ("d.py",)
    assert action_from_args("bash", {"restart": True}).paths == ()
    assert action_from_args("find_symbols", {"class_name": "Foo"}).paths == ()
    assert action_from_args("think", {"thought": "..."}).paths == ()


def test_sweagent_new_action_string():
    a = sweagent_new_action("str_replace_editor view /testbed/astropy/modeling/core.py  --view_range 1 50")
    assert a.tool == "str_replace_editor" and a.paths == ("/testbed/astropy/modeling/core.py",)
    a = sweagent_new_action("str_replace_editor create /testbed/reproduce.py --file_text 'from x import y'")
    assert a.paths == ("/testbed/reproduce.py",) and a.args["command"] == "create"
    a = sweagent_new_action("cd /testbed && str_replace_editor view /testbed")
    assert a.paths == ("/testbed",)
    a = sweagent_new_action("cd /testbed && python reproduce.py")
    assert a.tool == "bash" and a.paths == ("reproduce.py",)
    assert sweagent_new_action("submit").paths == ()


def test_sweagent_old_action_verbs_and_edit_state():
    st = OldSweAgentState()
    assert sweagent_old_action("create reproduce.py\n", st).paths == ("reproduce.py",)
    a = sweagent_old_action("edit 1:1\nfrom astropy import x\nend_of_edit", st)
    assert a.tool == "edit" and a.paths == ("reproduce.py",)
    assert sweagent_old_action("open astropy/modeling/separable.py 100\n", st).paths == ("astropy/modeling/separable.py",)
    assert sweagent_old_action("edit 10:20\nfoo\nend_of_edit", st).paths == ("astropy/modeling/separable.py",)
    assert sweagent_old_action('search_dir "def separability_matrix"', st).paths == ()
    assert sweagent_old_action('search_dir "x" astropy/modeling', st).paths == ("astropy/modeling",)
    assert sweagent_old_action('search_file "x" other.py', st).paths == ("other.py",)
    assert sweagent_old_action('search_file "x"', st).paths == ("astropy/modeling/separable.py",)
    assert sweagent_old_action("python reproduce.py\n", st).paths == ("reproduce.py",)
    assert sweagent_old_action("scroll_down\n", st).paths == () and sweagent_old_action("submit", st).paths == ()
    fresh = OldSweAgentState()
    assert sweagent_old_action("edit 1:1\nx\nend_of_edit", fresh).paths == () and fresh.edits_without_open_file == 1


def test_trae_function_xml_closed_calls_only():
    content = ("<think>t</think>\n<function=str_replace_editor>\n<parameter=command>view</parameter>\n"
               "<parameter=path>/testbed/a.py</parameter>\n</function>")
    (a,) = trae_actions(content)
    assert a.tool == "str_replace_editor" and a.paths == ("/testbed/a.py",) and a.args["command"] == "view"
    (b,) = trae_actions("<function=execute_bash>\n<parameter=command>cd /t && cat b.py</parameter>\n</function>")
    assert b.paths == ("b.py",) and b.command == "cd /t && cat b.py"
    assert trae_actions("<function=finish>\n</function>")[0].paths == ()
    # abandoned opener (D1) is not an action; the closed restart is
    aborted = ("<think>a</think>\n<function=str_replace_editor>\n<parameter=path>/x.py</parameter>\n#hm\n</think>\n"
               "<function=str_replace_editor>\n<parameter=command>create</parameter>\n<parameter=path>/y.py</parameter>\n"
               "</function>")
    acts = trae_actions(aborted)
    assert len(acts) == 1 and acts[0].paths == ("/y.py",)
