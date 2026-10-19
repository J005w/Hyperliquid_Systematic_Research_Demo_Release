"""Rebuild a forward-study feature from exact saved public inputs, offline."""

from hashlib import sha256
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hl_demo.public_data import reconstruct_lvn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--decision-ms", type=int, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["requests"][0]
    if (
        record["request"]["type"] != "candleSnapshot"
        or record["status"] != "received"
        or record["quality_issues"]
    ):
        raise SystemExit("Run has no clean candle input")
    # Fixed acquisition filenames prevent a modified manifest from reading
    # unrelated local files through a path traversal.
    if record["response_file"] != "00_response.json":
        raise SystemExit("Unexpected response path")
    raw = (args.run / "00_response.json").read_bytes()
    if sha256(raw).hexdigest() != record["response_sha256"]:
        raise SystemExit("Saved response hash differs from manifest")
    feature = reconstruct_lvn(json.loads(raw), record["available_ms"], args.decision_ms)
    print(json.dumps(feature, sort_keys=True, indent=2))
