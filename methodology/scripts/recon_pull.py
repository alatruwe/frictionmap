"""Recon pull: 2 trajectory files per agent from the SWE-bench submissions bucket."""
import boto3
from pathlib import Path
from botocore import UNSIGNED
from botocore.config import Config

s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))
BUCKET = "swe-bench-submissions"

FOLDERS = [
    "20251205_sonar-foundation-agent_claude-opus-4-5",
    "20250928_trae_doubao_seed_code",
    "20251127_openhands_claude-opus-4-5",
    "20250804_epam-ai-run-claude-4-sonnet",
    "20250612_trae",
    "20251021_SalesforceAIResearch_SAGE_bash_only",
    "20250807_openhands_gpt5",
    "20250524_openhands_claude_4_sonnet",
    "20250522_sweagent_claude-4-sonnet-20250514",
    "20250716_openhands_kimi_k2",
    "20250804_codesweep_sweagent_kimi_k2_instruct",
    "20241029_OpenHands-CodeAct-2.1-sonnet-20241022",
    "20250520_openhands_devstral_small",
    "20250511_sweagent_lm_32b",
    "20250616_Skywork-SWE-32B",
    "20240620_sweagent_claude3.5sonnet",
    "20240728_sweagent_gpt4o",
    "20240402_sweagent_gpt4",
    "20240402_sweagent_claude3opus",
]

out_root = Path("recon_samples")
for folder in FOLDERS:
    prefix = f"verified/{folder}/trajs/"
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=5)
    keys = [o["Key"] for o in resp.get("Contents", []) if o["Size"] > 0][:2]
    if not keys:
        print(f"!! NO TRAJS FOUND: {folder}")
        continue
    dest = out_root / folder
    dest.mkdir(parents=True, exist_ok=True)
    for k in keys:
        fname = dest / Path(k).name
        s3.download_file(BUCKET, k, str(fname))
        print(f"{folder}: {Path(k).name} ({fname.stat().st_size / 1024:.0f} KB)")
print("done")
