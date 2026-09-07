"""Registry and discovery acceptance checks (spec §1, §9.1)."""
from __future__ import annotations

import pathlib

import pytest

from swebench_adapter import registry
from swebench_adapter.discovery import INSTANCE_ID_RE, discover, instance_stem
from swebench_adapter.loaders import FileLevelFailure, load_trajectory_file, shape_matches
from swebench_adapter.sample import audit_sample
from tests._adapter_fakes import (EPAM, OPENHANDS, SAGE, SONAR, SWEAGENT_OLD, TRAE, fence,
                                  make_replication_tree)

POPULATION_13 = [
    "20240402_sweagent_claude3opus", "20240402_sweagent_gpt4", "20240620_sweagent_claude3.5sonnet",
    "20240728_sweagent_gpt4o", "20250511_sweagent_lm_32b", "20250522_sweagent_claude-4-sonnet-20250514",
    "20250804_codesweep_sweagent_kimi_k2_instruct", "20250804_epam-ai-run-claude-4-sonnet",
    "20251021_SalesforceAIResearch_SAGE_bash_only", "20251205_sonar-foundation-agent_claude-opus-4-5",
    "20250928_trae_doubao_seed_code", "20250524_openhands_claude_4_sonnet", "20250716_openhands_kimi_k2",
]
EXCLUDED_7 = [
    "20241029_OpenHands-CodeAct-2.1-sonnet-20241022", "20250612_trae", "20250616_Skywork-SWE-32B",
    "20250520_openhands_devstral_small", "20250807_openhands_gpt5", "20251127_openhands_claude-opus-4-5",
    "20250415_openhands",
]


def test_all_13_population_folders_resolve_to_a_family():
    assert sorted(registry.population_folders()) == sorted(POPULATION_13)
    for folder in POPULATION_13:
        sub = registry.resolve(folder)
        assert sub.family in {registry.THOUGHT, registry.EPAM, registry.SAGE, registry.SONAR,
                              registry.TRAE, registry.THINK_TOOL}
        assert sub.their_format != "openhands-lossy"


def test_family_assignment_matches_spec_table():
    assert registry.resolve("20250804_epam-ai-run-claude-4-sonnet").family == registry.EPAM
    assert registry.resolve("20251021_SalesforceAIResearch_SAGE_bash_only").family == registry.SAGE
    assert registry.resolve("20251205_sonar-foundation-agent_claude-opus-4-5").family == registry.SONAR
    assert registry.resolve("20250928_trae_doubao_seed_code").family == registry.TRAE
    assert registry.resolve("20250524_openhands_claude_4_sonnet").family == registry.THINK_TOOL
    assert registry.resolve("20250716_openhands_kimi_k2").family == registry.THINK_TOOL
    for f in POPULATION_13[:7]:
        assert registry.resolve(f).family == registry.THOUGHT
    assert registry.resolve("20240402_sweagent_gpt4").folder in registry.SWEAGENT_OLD_FOLDERS
    assert registry.resolve("20250511_sweagent_lm_32b").folder in registry.SWEAGENT_NEW_FOLDERS


@pytest.mark.parametrize("folder", EXCLUDED_7)
def test_each_excluded_folder_is_refused_even_when_present_on_disk(tmp_path, fence, folder):
    root = make_replication_tree(tmp_path, submissions={folder: {"a__b-1.json": OPENHANDS}})
    assert (root / folder / "a__b-1.json").exists()
    with pytest.raises(registry.ExcludedSubmission):
        registry.resolve(folder)
    with pytest.raises(registry.ExcludedSubmission):
        load_trajectory_file(root / folder / "a__b-1.json", folder)
    assert not any("a__b-1.json" in p for p in fence), "refused folder must not be read"


def test_dispatch_keys_on_folder_not_format_string():
    # `openhands` serves population (claude_4_sonnet) and excluded (devstral); `trae` likewise.
    assert registry.SUBMISSION_META["20250524_openhands_claude_4_sonnet"]["format"] == "openhands"
    assert registry.SUBMISSION_META["20250520_openhands_devstral_small"]["format"] == "openhands"
    assert registry.SUBMISSION_META["20250612_trae"]["format"] == registry.SUBMISSION_META[
        "20250928_trae_doubao_seed_code"]["format"] == "trae"
    registry.resolve("20250524_openhands_claude_4_sonnet")
    with pytest.raises(registry.ExcludedSubmission):
        registry.resolve("20250520_openhands_devstral_small")


def test_unknown_folder_is_refused_and_globbing_is_not_the_filter(tmp_path, fence):
    root = make_replication_tree(tmp_path, submissions={"20991231_unknown_agent": {"a__b-1.json": OPENHANDS}})
    with pytest.raises(registry.UnknownSubmission):
        registry.resolve("20991231_unknown_agent")
    # discovery on disk still works (it is not the population filter) ...
    assert len(discover(root / "20991231_unknown_agent").files) == 1
    # ... but loading refuses.
    with pytest.raises(registry.UnknownSubmission):
        load_trajectory_file(root / "20991231_unknown_agent" / "a__b-1.json", "20991231_unknown_agent")


def test_vendored_table_matches_recorded_hash_of_their_config(tmp_path):
    fake = tmp_path / "config.py"
    fake.write_text("SUBMISSION_META = {}\n")
    assert registry.their_config_drifted(fake)
    assert len(registry.THEIR_CONFIG_SHA256) == 64


# ---- discovery (spec §1 rule, Q7) ------------------------------------------

def test_instance_id_pattern():
    assert INSTANCE_ID_RE.match("astropy__astropy-12907")
    assert INSTANCE_ID_RE.match("scikit-learn__scikit-learn-10297")
    assert INSTANCE_ID_RE.match("psf__requests-1963")
    assert not INSTANCE_ID_RE.match("preds")
    assert not INSTANCE_ID_RE.match("astropy__astropy")
    assert not INSTANCE_ID_RE.match("astropy-12907")


def test_instance_stem_handles_double_extension():
    assert instance_stem(pathlib.Path("x__y-1.traj.json")) == "x__y-1"
    assert instance_stem(pathlib.Path("x__y-1.traj")) == "x__y-1"
    assert instance_stem(pathlib.Path("x__y-1.json")) == "x__y-1"


def test_discovery_dedupes_quarantines_and_sorts(tmp_path, fence):
    root = make_replication_tree(tmp_path, submissions={"20240402_sweagent_gpt4": {
        "b__b-2.traj": SWEAGENT_OLD,
        "a__a-1.traj": SWEAGENT_OLD,
        "a__a-1.json": {"dup": True},            # same stem — .traj wins
        "c__c-3.traj.json": SWEAGENT_OLD,        # double extension, one stem
        "preds.json": {"x": 1},                  # non_trajectory
        "notes.txt": "ignored — not a candidate extension",
    }})
    d = discover(root / "20240402_sweagent_gpt4")
    assert d.n_candidates == 5
    assert [p.name for p in d.files] == ["a__a-1.traj", "b__b-2.traj", "c__c-3.traj.json"]
    assert d.instance_ids == ["a__a-1", "b__b-2", "c__c-3"]
    assert [(p.name, c) for p, c in d.quarantined] == [("preds.json", "non_trajectory")]
    assert [p.name for p in d.duplicates] == ["a__a-1.json"]
    assert fence == [], "discovery must not open any file"


def test_audit_sample_takes_every_ceil_n_over_50th_from_index_0(tmp_path, fence):
    files = {f"a__a-{i:04d}.traj": SWEAGENT_OLD for i in range(443)}
    root = make_replication_tree(tmp_path, submissions={"20240402_sweagent_gpt4": files})
    d = discover(root / "20240402_sweagent_gpt4")
    s = audit_sample(d)
    assert len(s) == 50                      # ceil(443/50) = 9 → indices 0, 9, ..., 441
    assert s[0].name == "a__a-0000.traj" and s[1].name == "a__a-0009.traj" and s[-1].name == "a__a-0441.traj"
    d500 = discover(root / "20240402_sweagent_gpt4")
    d500.files = d500.files[:500] if len(d500.files) >= 500 else d500.files
    assert audit_sample(d, target=1) == [s[0]]


# ---- file-level shape (spec §1 table, §6) ----------------------------------

@pytest.mark.parametrize("family,good", [
    (registry.THOUGHT, SWEAGENT_OLD), (registry.EPAM, EPAM), (registry.SONAR, SONAR),
    (registry.SAGE, SAGE), (registry.TRAE, TRAE), (registry.THINK_TOOL, OPENHANDS),
])
def test_shape_table_accepts_its_own_family_and_rejects_the_others(family, good):
    assert shape_matches(family, good)
    others = [SWEAGENT_OLD, EPAM, SONAR, SAGE, TRAE, OPENHANDS]
    rejected = [not shape_matches(family, o) for o in others if o is not good]
    # Trae and think-tool share a shape (list of role dicts), and Sonar's shape is a
    # superset of it; everything else is distinct.
    if family in (registry.TRAE, registry.THINK_TOOL):
        assert sum(rejected) == 3
    else:
        assert all(rejected)


def test_load_classifies_unreadable_and_wrong_shape_as_file_level(tmp_path, fence):
    folder = "20240402_sweagent_gpt4"
    root = make_replication_tree(tmp_path, submissions={folder: {
        "a__a-1.traj": "not json {",
        "a__a-2.traj": EPAM,                   # readable but wrong family shape
        "a__a-3.traj": SWEAGENT_OLD,
    }})
    with pytest.raises(FileLevelFailure, match="unreadable"):
        load_trajectory_file(root / folder / "a__a-1.traj", folder)
    with pytest.raises(FileLevelFailure, match="shape"):
        load_trajectory_file(root / folder / "a__a-2.traj", folder)
    loaded = load_trajectory_file(root / folder / "a__a-3.traj", folder)
    assert loaded.submission.family == registry.THOUGHT and loaded.data["trajectory"] == []


def test_epam_loader_preserves_document_order(tmp_path, fence):
    folder = "20250804_epam-ai-run-claude-4-sonnet"
    body = '[{"zzz": {"author_name": "Thoughts", "message": "1", "input_text": ""}, ' \
           '"aaa": {"author_name": "Run Command Line Tool", "message": "2", "input_text": "{}"}}]'
    root = make_replication_tree(tmp_path, submissions={folder: {"a__a-1.traj": body}})
    loaded = load_trajectory_file(root / folder / "a__a-1.traj", folder)
    assert list(loaded.data[0]) == ["zzz", "aaa"]
