"""Check the release boundary, including reachable history when requested."""

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "fixtures/market_panel.json",
    "src/hl_demo/report.py",
    "reports/source_history_audit.json",
}


def verify(history: bool = False) -> None:
    for path in FORBIDDEN:
        if (ROOT / path).exists():
            raise ValueError("Private empirical artifact is present: " + path)
    fixture = json.loads((ROOT / "fixtures/synthetic_panel.json").read_text())
    results = json.loads((ROOT / "reports/results.json").read_text())
    if (
        fixture["evidence_kind"] != "synthetic_implementation_only"
        or results["evidence_kind"] != "synthetic_implementation_only"
    ):
        raise ValueError("Report/fixture must be synthetic-only")
    if history:
        git = ["git", "--git-dir=" + str(ROOT / ".git"), "--work-tree=" + str(ROOT)]
        names = subprocess.check_output(
            git + ["log", "--all", "--name-only", "--format="], text=True
        ).splitlines()
        found = FORBIDDEN.intersection(names)
        if found:
            raise ValueError(
                "Private artifact occurs in reachable history: "
                + ", ".join(sorted(found))
            )
        roots = subprocess.check_output(
            git + ["rev-list", "--all", "--max-parents=0"], text=True
        ).splitlines()
        if len(set(roots)) != 1:
            raise ValueError("Expected one fresh root, with no imported history")
    print(
        "Release data boundary verified"
        + (" across all reachable history." if history else " for archive contents.")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    verify(parser.parse_args().history)
