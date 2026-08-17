"""Verify 3 discrepancies found in raw examples. Structure checks only."""
import json
from pathlib import Path

ROOT = Path("recon_samples")

def files(agent):
    return sorted(x for x in (ROOT/agent).iterdir()
                  if "config" not in x.name and x.suffix != ".patch")

# 1. sweagent family: is thought ever DIFFERENT from content?
print("## 1. thought==content duplication (SWE-agent formats)")
for agent in ["20250522_sweagent_claude-4-sonnet-20250514",
              "20240620_sweagent_claude3.5sonnet",
              "20240402_sweagent_gpt4",
              "20250804_codesweep_sweagent_kimi_k2_instruct",
              "20250511_sweagent_lm_32b"]:
    for f in files(agent):
        data = json.loads(f.read_text(errors="replace"))
        evs = [e for e in data["history"] if "thought" in e]
        same = sum(1 for e in evs if e["thought"] == e.get("content"))
        diff = len(evs) - same
        print(f"  {agent} / {f.name}: {len(evs)} thought events, {same} identical to content, {diff} different")

# 2. trae-claude: any non-null reasoning in either file?
print("\n## 2. trae-claude 'reasoning' population")
for f in files("20250612_trae"):
    data = json.loads(f.read_text(errors="replace"))
    has_key = [e for e in data if "reasoning" in e]
    filled = [e for e in has_key if e.get("reasoning")]
    print(f"  {f.name}: {len(has_key)} events with key, {len(filled)} non-null")
    if filled:
        s = filled[0]["reasoning"]
        print(f"    sample: {s[:200]!r}")

# 3. think-tool usage across ALL agents with tool_calls
print("\n## 3. 'think' tool-call census (all agents)")
for d in sorted(ROOT.iterdir()):
    for f in files(d.name):
        try:
            data = json.loads(f.read_text(errors="replace"))
        except Exception:
            continue
        evs = data if isinstance(data, list) else data.get("messages") or data.get("history") or []
        if not isinstance(evs, list): continue
        n_think, n_tc = 0, 0
        for e in evs:
            if not isinstance(e, dict): continue
            for tc in (e.get("tool_calls") or []):
                if not isinstance(tc, dict): continue
                n_tc += 1
                if (tc.get("function") or {}).get("name") == "think":
                    n_think += 1
        if n_tc:
            flag = "  <-- THINK TOOL" if n_think else ""
            print(f"  {d.name} / {f.name}: {n_tc} tool_calls, {n_think} think{flag}")
        break  # file 1 per agent is enough for census; file 2 via loop below if needed
