"""Per-horizon denominators, de-duplication and non-overlapping samples."""

from __future__ import annotations
from collections import Counter, defaultdict
from statistics import mean
from random import Random
from typing import Any
from .event_study import Policy, markout


def unique_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduplicated = []
    for event in sorted(
        events, key=lambda row: (row["t_ms"], row["asset"], row["type"])
    ):
        key = (event["asset"], event["t_ms"], event["type"])
        if key not in seen:
            seen.add(key)
            deduplicated.append(event)
    return deduplicated


def independent_events(
    events: list[dict[str, Any]], horizon_min: int, delay_ms: int, entry_age_ms: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Greedy deterministic per-asset interval thinning, without looking at returns."""
    reserved_until = {}
    retained_events = []
    sample_count = 0
    for event in unique_events(events):
        if event["t_ms"] <= reserved_until.get(event["asset"], -1):
            sample_count += 1
            continue
        retained_events.append(event)
        reserved_until[event["asset"]] = (
            event["t_ms"] + horizon_min * 60_000 + delay_ms + entry_age_ms
        )
    return retained_events, sample_count


def score(
    events: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    horizons: list[int],
    policy: Policy = Policy(),
    side: int = 1,
    fee_bps: float = 4.5,
    slip_bps: float = 0,
) -> dict[str, Any]:
    result = {}
    deduplicated_events = unique_events(events)
    for horizon in horizons:
        retained_events, overlap_removed = independent_events(
            events, horizon, policy.max_exit_delay_ms, policy.max_entry_age_ms
        )
        reasons = Counter()
        scored_events = []
        for event in retained_events:
            row = markout(
                rows,
                event["asset"],
                event["t_ms"],
                horizon,
                side,
                policy,
                fee_bps,
                slip_bps,
            )
            if row["reason"]:
                reasons[row["reason"]] += 1
            else:
                scored_events.append((event, row))
        sample_count = len(scored_events)
        result[str(horizon)] = {
            "n_input": len(events),
            "n_unique": len(deduplicated_events),
            "n_duplicates_removed": len(events) - len(deduplicated_events),
            "n_overlap_removed": overlap_removed,
            "n_attempted": len(retained_events),
            "n_scored": sample_count,
            "missing": dict(sorted(reasons.items())),
            "mean_signed_markout_bps": mean(
                row["signed_bps"] for event, row in scored_events
            )
            if sample_count
            else None,
            "mean_markout_less_cost_budget_bps": mean(
                row["markout_less_cost_budget_bps"] for event, row in scored_events
            )
            if sample_count
            else None,
            "positive_signed_markout_fraction": sum(
                row["signed_bps"] > 0 for event, row in scored_events
            )
            / sample_count
            if sample_count
            else None,
            "n_utc_days": len(
                {event["t_ms"] // 86_400_000 for event, row in scored_events}
            ),
            "timing_ranges_ms": {
                key: {
                    "min": min(row[key] for event, row in scored_events),
                    "max": max(row[key] for event, row in scored_events),
                }
                if sample_count
                else None
                for key in (
                    "entry_age_ms",
                    "exit_delay_ms",
                    "elapsed_ms",
                    "entry_availability_delay_ms",
                    "exit_availability_delay_ms",
                )
            },
            "promotable": False,
            "rows": scored_events,
        }
    return result


def day_interval(
    pairs: list[dict[str, Any]], min_days: int = 8, draws: int = 2000, seed: int = 8341
) -> tuple[list[float] | None, str]:
    if min_days < 2 or draws < 100:
        raise ValueError(
            "interval estimation needs at least two day blocks and 100 draws"
        )
    blocks = defaultdict(list)
    for pair in pairs:
        blocks[pair["event_ms"] // 86_400_000].append(pair["difference_bps"])
    if len(blocks) < min_days:
        return (
            None,
            f"Fewer than {min_days} UTC day blocks; interval suppressed; asset/day observations remain dependent.",
        )
    rng = Random(seed)
    keys = sorted(blocks)
    samples = []
    for _ in range(draws):
        selected = [rng.choice(keys) for _ in keys]
        values = [v for k in selected for v in blocks[k]]
        samples.append(mean(values))
    samples.sort()
    return (
        [samples[int(0.025 * (draws - 1))], samples[int(0.975 * (draws - 1))]],
        "Exploratory UTC-day block bootstrap; no multiplicity correction or causal interpretation.",
    )


def matched_controls(
    events: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    horizon_min: int,
    policy: Policy = Policy(),
    side: int = 1,
    fee_bps: float = 4.5,
    slip_bps: float = 0,
    min_days: int = 8,
) -> dict[str, Any]:
    """Earlier-day same-asset/same-hour non-event controls, without reuse.

    All retained event labels count for exclusion. This retrospective matching
    does not claim a causal counterfactual. Common market/day shocks remain.
    """
    deduplicated_events = unique_events(events)
    retained_events, _ = independent_events(
        events, horizon_min, policy.max_exit_delay_ms, policy.max_entry_age_ms
    )
    used_controls = set()
    pairs = []
    exclusion_window_ms = (
        horizon_min * 60_000 + policy.max_exit_delay_ms + policy.max_entry_age_ms
    )
    for event in retained_events:
        event_result = markout(
            rows,
            event["asset"],
            event["t_ms"],
            horizon_min,
            side,
            policy,
            fee_bps,
            slip_bps,
        )
        if event_result["reason"]:
            continue
        candidates = []
        for row in rows:
            candidate_ms = row["t_ms"]
            if (
                row["asset"] != event["asset"]
                or (row["asset"], candidate_ms) in used_controls
            ):
                continue
            if (
                candidate_ms // 86_400_000 >= event["t_ms"] // 86_400_000
                or candidate_ms + exclusion_window_ms >= event["t_ms"]
            ):
                continue
            if (candidate_ms // 3_600_000) % 24 != (event["t_ms"] // 3_600_000) % 24:
                continue
            if any(
                v["asset"] == event["asset"]
                and abs(v["t_ms"] - candidate_ms) <= exclusion_window_ms
                for v in deduplicated_events
            ):
                continue
            # Prevent overlapping control intervals within an asset as well.
            if any(
                used_asset == event["asset"]
                and abs(candidate_ms - used_ms) <= exclusion_window_ms
                for used_asset, used_ms in used_controls
            ):
                continue
            control_result = markout(
                rows,
                event["asset"],
                candidate_ms,
                horizon_min,
                side,
                policy,
                fee_bps,
                slip_bps,
            )
            if not control_result["reason"]:
                candidates.append((candidate_ms, control_result))
        if candidates:
            candidate_ms, control_result = max(candidates, key=lambda x: x[0])
            used_controls.add((event["asset"], candidate_ms))
            pairs.append(
                {
                    "asset": event["asset"],
                    "event_ms": event["t_ms"],
                    "control_ms": candidate_ms,
                    "event_bps": event_result["signed_bps"],
                    "control_bps": control_result["signed_bps"],
                    "difference_bps": event_result["signed_bps"]
                    - control_result["signed_bps"],
                }
            )
    days = {pair["event_ms"] // 86_400_000 for pair in pairs}
    interval, reason = day_interval(pairs, min_days)
    return {
        "n_pairs": len(pairs),
        "n_utc_day_blocks": len(days),
        "matched_event_mean_bps": mean(pair["event_bps"] for pair in pairs)
        if pairs
        else None,
        "matched_control_mean_bps": mean(pair["control_bps"] for pair in pairs)
        if pairs
        else None,
        "paired_mean_difference_bps": mean(pair["difference_bps"] for pair in pairs)
        if pairs
        else None,
        "interval_95_bps": interval,
        "uncertainty_reason": reason,
        "pairs": pairs,
    }
