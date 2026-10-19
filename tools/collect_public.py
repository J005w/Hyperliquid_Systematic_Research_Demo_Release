"""Optional, finite read-only smoke collection. Never used by offline reports."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hl_demo.public_data import collect_once

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=("BTC", "ETH"), default="BTC")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new private directory; never overwritten",
    )
    args = parser.parse_args()
    result = collect_once(args.output, args.asset)
    received = sum(record["status"] == "received" for record in result["requests"])
    print(
        f"Completed one bounded run: {received}/2 public responses persisted. No research performance result."
    )
    raise SystemExit(0 if received == 2 else 1)
