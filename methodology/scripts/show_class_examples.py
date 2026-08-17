"""Write one RAW event per substrate class (A-E) to markdown.
Full JSON structure preserved; only long string values truncated (marked).
Display/verification, not signal computation."""
import json
from pathlib import Path

ROOT = Path("recon_samples")
OUT = Path("substrate_class_examples.md")
VMAX = 500  # max chars per string value

def trunc(o):
    if isinstance(o, str):
        return o if len(o) <= VMAX else o[:VMAX] + f" [...{len(o)-VMAX} more chars]"
    if isinstance(o, dict):
        return {k: trunc(v) for k, v in o.items()}
    if isinstance(o, list):
        return [trunc(x) for x in o]
    return o

out = []
def w(line=""): out.append(line)

def dump(label, obj):
    w(f"**{label}**")
    w()
    w("```json")
    w(json.dumps(trunc(obj), indent=2, ensure_ascii=False))
    w("```")
    w()

def load(agent, pattern="*"):
    f = sorted((ROOT / agent).glob(pattern))
    f = [x for x in f if "config" not in x.name and x.suffix != ".patch"]
    return json.loads(f[0].read_text(errors="replace")), f[0].name

w("# Substrate class examples — RAW events from recon_samples")
w()
w("*Each excerpt is one complete event object, verbatim JSON. Only string values")
w(f"longer than {VMAX} chars are truncated, with a `[...N more chars]` marker.")
w("Keys and structure are untouched.*")
w()

w("## Class A — dedicated `thought` field (SWE-agent format)")
w()
data, fname = load("20250522_sweagent_claude-4-sonnet-20250514", "*.traj")
e = [x for x in data["history"] if x.get("thought")][2]
dump(f"sweagent / claude-4-sonnet — `{fname}`, one `history` event, raw", e)

w("### Class A variant — EPAM author-typed entry")
w()
data, fname = load("20250804_epam-ai-run-claude-4-sonnet", "*.traj")
entries = list(data[0].items())
uuid, th = [(k, v) for k, v in entries
            if isinstance(v, dict) and v.get("author_name") == "Thoughts"][1]
dump(f"epam / claude-4-sonnet — `{fname}`, one UUID-keyed entry, raw", {uuid: th})
# and one action-typed entry for contrast
uuid2, act = [(k, v) for k, v in entries
              if isinstance(v, dict) and v.get("author_name") != "Thoughts"][0]
dump("same file, an action-typed entry for contrast, raw", {uuid2: act})

w("## Class B — true thinking-channel blocks")
w()
data, fname = load("20251205_sonar-foundation-agent_claude-opus-4-5")
e = next(ev for ev in data
         if any(b.get("block_type") == "thinking" for b in ev.get("blocks", [])))
dump(f"sonar / claude-opus-4.5 — `{fname}`, one event, raw", e)

w("## Class C — inline-tagged reasoning")
w()
data, fname = load("20250928_trae_doubao_seed_code")
e = next(ev for ev in data if ev.get("role") == "assistant"
         and isinstance(ev.get("content"), str) and "<think>" in ev["content"])
dump(f"trae / doubao-seed-code — `{fname}`, one event, raw (note `<think>` INSIDE the content string)", e)

data, fname = load("20250612_trae")
cands = [ev for ev in data if "reasoning" in ev]
nonempty = [ev for ev in cands if ev.get("reasoning")]
e = (nonempty or cands)[0]
dump(f"trae / claude-4-sonnet+opus — `{fname}`, one event, raw (note separate `reasoning` key)", e)

data, fname = load("20251021_SalesforceAIResearch_SAGE_bash_only")
e = [ev for ev in data["messages"] if ev.get("role") == "assistant"
     and isinstance(ev.get("content"), str) and ev["content"].startswith("THOUGHT")][1]
dump(f"SAGE — `{fname}`, one event, raw (note `THOUGHT:` prefix INSIDE content)", e)

w("## Class D — narration only (no designated reasoning channel)")
w()
data, fname = load("20250524_openhands_claude_4_sonnet")
e = next(ev for ev in data if ev.get("role") == "assistant"
         and isinstance(ev.get("content"), list)
         and any(isinstance(b, dict) and b.get("text") for b in ev["content"])
         and ev.get("tool_calls"))
dump(f"openhands / claude-4-sonnet — `{fname}`, one event, raw (text block + tool_calls, NO reasoning key anywhere)", e)

w("## Class E — no reasoning text in the release")
w()
data, fname = load("20250807_openhands_gpt5")
asst = [ev for ev in data if ev.get("role") == "assistant"]
e = next(ev for ev in asst if ev.get("tool_calls"))
dump(f"openhands / gpt-5 — `{fname}`, one event, raw (note `content` is EMPTY)", e)

data, fname = load("20251127_openhands_claude-opus-4-5")
dump(f"openhands / claude-opus-4.5 — `{fname}`, events 2–4, raw (lossy export)",
     data[2:5])

OUT.write_text("\n".join(out))
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
