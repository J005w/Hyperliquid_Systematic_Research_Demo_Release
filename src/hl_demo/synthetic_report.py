"""Deterministic synthetic reports, explicitly separate from the private study."""

from hashlib import sha256
import argparse
import json
from pathlib import Path
from typing import Any

from .cells import matched_controls, score
from .event_study import Policy
from .reconciliation import run_case_study

ROOT = Path(__file__).resolve().parents[2]


def analyse(root: Path = ROOT) -> dict[str, Any]:
    fixture_path = root / "fixtures/synthetic_panel.json"
    config_path = root / "config/study.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if fixture["evidence_kind"] != "synthetic_implementation_only":
        raise ValueError("This report accepts only explicitly synthetic inputs")
    policy = Policy(config["max_entry_age_ms"], config["max_exit_delay_ms"])
    cells = score(
        fixture["events"],
        fixture["snapshots"],
        config["horizons_min"],
        policy,
        config["benchmark_direction"],
        config["fee_bps_per_side"],
    )
    controls = {
        str(horizon): matched_controls(
            fixture["events"],
            fixture["snapshots"],
            horizon,
            policy,
            config["benchmark_direction"],
            config["fee_bps_per_side"],
        )
        for horizon in config["horizons_min"]
    }
    for cell in cells.values():
        cell.pop("rows")
    for matched in controls.values():
        matched.pop("pairs")
    reconciliation_path = root / "fixtures/reconciliation.json"
    return {
        "schema_version": 1,
        "evidence_kind": fixture["evidence_kind"],
        "limitation": "Invented prices and events test implementation only; no empirical market validation or profitability inference.",
        "framework_checks": cells,
        "synthetic_controls": controls,
        "reconciliation": run_case_study(reconciliation_path),
        "input_sha256": {
            path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in (fixture_path, config_path, reconciliation_path)
        },
    }


def render(result: dict[str, Any]) -> str:
    lines = [
        "# Synthetic implementation and reconciliation report",
        "",
        "**Every input in this report is invented. It does not reproduce or validate the private empirical market study.**",
        "",
        "The private retrospective finding is recorded separately in [RETROSPECTIVE_FINDING.md](../docs/RETROSPECTIVE_FINDING.md). Its market data and full empirical report are not distributed here.",
        "",
        "| Synthetic horizon (min) | Scored examples | Mean long markout (bps) | Less two-sided fee budget (bps) | Matched examples | Paired difference (bps) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for horizon, cell in result["framework_checks"].items():
        control = result["synthetic_controls"][horizon]
        lines.append(
            f"| {horizon} | {cell['n_scored']} | {cell['mean_signed_markout_bps']:.3f} | {cell['mean_markout_less_cost_budget_bps']:.3f} | {control['n_pairs']} | {control['paired_mean_difference_bps']:.3f} |"
        )
    lines += [
        "",
        "Hand check: two event paths move 100→101 and 100→99; their mean long markout is zero. The prior-day invented control moves 100→100.5. These values were chosen for arithmetic, not fitted to market data.",
        "",
        "## Synthetic reconciliation",
        "",
        "Failed/rejected exits retain the last reconciled position and block new risk. A confirmed full close permits a price/fee/funding cash bridge. Positive invented cash outcomes are not market performance.",
        "",
        "| Invented case | State result | New risk blocked | Close records |",
        "|---|---|---|---:|",
    ]
    for case in result["reconciliation"]["scenarios"]:
        lines.append(
            f"| {case['id']} | {case['event']} | {case['block_new_risk']} | {case['close_records']} |"
        )
    lines += [
        "",
        "No synthetic result measures market profitability. No empirical confidence interval, holdout performance or completed TWAP/funding result is supplied.",
        "",
        "## Reproduce",
        "",
        "`python demo.py` regenerates this synthetic report; `python demo.py --check` checks exact agreement.",
        "",
        "Input SHA-256:",
        "",
    ]
    for path, digest in result["input_sha256"].items():
        lines.append(f"- `{path}`: `{digest}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = analyse()
    outputs = {
        "results.json": json.dumps(result, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        "RESULTS.md": render(result),
    }
    folder = ROOT / "reports"
    if args.check:
        stale = [
            name
            for name, content in outputs.items()
            if not (folder / name).exists()
            or (folder / name).read_text(encoding="utf-8") != content
        ]
        if stale:
            raise SystemExit("Stale synthetic report: " + ", ".join(stale))
        print("Synthetic reports reproduce exactly; no empirical reproduction claimed.")
        return
    folder.mkdir(exist_ok=True)
    for name, content in outputs.items():
        (folder / name).write_text(content, encoding="utf-8", newline="\n")
    print(
        "Generated synthetic implementation report; no empirical reproduction claimed."
    )
