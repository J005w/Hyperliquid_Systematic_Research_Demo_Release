"""Corrected timing and accounting primitives. No trading or network access.

Markouts describe prices. Only quote_pnl models bid/ask crossing; neither
function establishes that an order actually filled or that liquidity sufficed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Policy:
    max_entry_age_ms: int = 60_000
    max_exit_delay_ms: int = 240_000

    def __post_init__(self) -> None:
        if not all(
            valid_timestamp(value)
            for value in (self.max_entry_age_ms, self.max_exit_delay_ms)
        ):
            raise ValueError(
                "timing tolerances must be nonnegative integer milliseconds"
            )


def valid_timestamp(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def positive(value: Any) -> bool:
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and isfinite(value)
        and value > 0
    )


def direction(value: Any) -> int:
    if value in (1, -1) and not isinstance(value, bool):
        return int(value)
    raise ValueError("direction must be explicitly +1 or -1")


def valid_rows(
    rows: list[dict[str, Any]], asset: str, field: str
) -> list[dict[str, Any]]:
    return sorted(
        (
            r
            for r in rows
            if r.get("asset") == asset
            and positive(r.get(field))
            and valid_timestamp(r.get("t_ms"))
            and valid_timestamp(r.get("available_ms"))
            and r["available_ms"] >= r["t_ms"]
        ),
        key=lambda r: (r["t_ms"], r["available_ms"]),
    )


def observations(
    rows: list[dict[str, Any]],
    asset: str,
    decision_ms: int,
    horizon_min: int,
    policy: Policy = Policy(),
    field: str = "mark",
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Entry strictly as-of decision; exit bounded after the intended horizon.

    available_ms is mandatory. Empirical legacy adapters label their timestamp
    assumption separately; they cannot establish genuine receipt timestamps.
    """
    if (
        not valid_timestamp(decision_ms)
        or not valid_timestamp(horizon_min)
        or horizon_min == 0
    ):
        raise ValueError(
            "decision time and positive horizon must be integer timestamps/minutes"
        )
    candidates = valid_rows(rows, asset, field)
    before = [
        r
        for r in candidates
        if r["t_ms"] <= decision_ms
        and r["available_ms"] <= decision_ms
        and decision_ms - r["t_ms"] <= policy.max_entry_age_ms
    ]
    if not before:
        return None, None, "missing_or_stale_entry"
    entry = before[-1]
    target = decision_ms + horizon_min * 60_000
    after = [
        r
        for r in candidates
        if target <= r["t_ms"] <= target + policy.max_exit_delay_ms
        and r["available_ms"] <= target + policy.max_exit_delay_ms
    ]
    if not after:
        return entry, None, "missing_or_delayed_exit"
    return entry, after[0], None


def markout(
    rows: list[dict[str, Any]],
    asset: str,
    decision_ms: int,
    horizon_min: int,
    side: int,
    policy: Policy = Policy(),
    fee_bps: float = 4.5,
    slip_bps: float = 0.0,
) -> dict[str, Any]:
    side = direction(side)
    if fee_bps < 0 or slip_bps < 0 or not isfinite(fee_bps + slip_bps):
        raise ValueError("invalid cost")
    entry, exit_observation, reason = observations(
        rows, asset, decision_ms, horizon_min, policy
    )
    if reason:
        return {"reason": reason}
    price_ratio = exit_observation["mark"] / entry["mark"]
    asset_return_bps = (price_ratio - 1) * 10_000
    # Entry and exit fees apply to their respective notionals. Slippage is a
    # sensitivity budget on both notionals, not a reconstructed execution price.
    cost = (fee_bps + slip_bps) * (1 + price_ratio)
    return {
        "reason": None,
        "asset_bps": asset_return_bps,
        "signed_bps": side * asset_return_bps,
        "cost_budget_bps": cost,
        "markout_less_cost_budget_bps": side * asset_return_bps - cost,
        "entry_ms": entry["t_ms"],
        "exit_ms": exit_observation["t_ms"],
        "entry_age_ms": decision_ms - entry["t_ms"],
        "elapsed_ms": exit_observation["t_ms"] - entry["t_ms"],
        "entry_availability_delay_ms": entry["available_ms"] - entry["t_ms"],
        "exit_availability_delay_ms": exit_observation["available_ms"]
        - exit_observation["t_ms"],
        "exit_delay_ms": exit_observation["t_ms"]
        - (decision_ms + horizon_min * 60_000),
    }


def quote_pnl(
    entry_bid: float,
    entry_ask: float,
    exit_bid: float,
    exit_ask: float,
    side: int,
    fee_bps: float = 4.5,
    funding_cash: float = 0.0,
) -> dict[str, float]:
    """Conditional one-unit round trip; funding_cash positive means received.

    Actual settled cash is an outcome, never a pre-settlement signal. Prices
    must already satisfy freshness/availability checks upstream.
    """
    side = direction(side)
    if not all(positive(x) for x in (entry_bid, entry_ask, exit_bid, exit_ask)):
        raise ValueError("invalid quote")
    if entry_bid > entry_ask or exit_bid > exit_ask:
        raise ValueError("crossed quote")
    if fee_bps < 0 or not isfinite(fee_bps) or not isfinite(funding_cash):
        raise ValueError("invalid cost")
    entry = entry_ask if side == 1 else entry_bid
    exit_price = exit_bid if side == 1 else exit_ask
    price_pnl = side * (exit_price - entry)
    fee_cash = (entry + exit_price) * fee_bps / 10_000
    return {
        "price_cash": price_pnl,
        "fee_cash": -fee_cash,
        "funding_cash": funding_cash,
        "net_cash": price_pnl - fee_cash + funding_cash,
        "net_bps": (price_pnl - fee_cash + funding_cash) / entry * 10_000,
    }


def funding_prediction(
    record: dict[str, Any], decision_ms: int, max_age_ms: int = 300_000
) -> float | None:
    """Reject settled prints, future receipts, unknown availability and old data."""
    if record.get("kind") != "predicted":
        return None
    observed = record.get("observed_ms")
    available = record.get("available_ms")
    settle = record.get("settlement_ms")
    rate = record.get("rate")
    if not all(
        valid_timestamp(t)
        for t in (observed, available, settle, decision_ms, max_age_ms)
    ):
        return None
    if not observed <= available <= decision_ms < settle:
        return None
    if decision_ms - observed > max_age_ms:
        return None
    if (
        not isinstance(rate, (int, float))
        or isinstance(rate, bool)
        or not isfinite(rate)
    ):
        return None
    return rate


def candle_volume_proxy(
    candles: list[dict[str, Any]], decision_ms: int, width: float = 1.0
) -> dict[str, Any]:
    """Typical-price bins of completed candles; NOT traded volume by price."""
    if not positive(width):
        raise ValueError("invalid bin width")
    bins = {}
    for candle in candles:
        if not all(
            valid_timestamp(candle.get(key)) for key in ("close_ms", "available_ms")
        ):
            continue
        if candle["available_ms"] < candle["close_ms"]:
            continue
        if candle["close_ms"] >= decision_ms or candle["available_ms"] > decision_ms:
            continue
        if not all(positive(candle.get(k)) for k in ("high", "low", "close")):
            continue
        if not candle["low"] <= candle["close"] <= candle["high"]:
            continue
        if (
            not isinstance(candle.get("volume"), (int, float))
            or isinstance(candle["volume"], bool)
            or not isfinite(candle["volume"])
            or candle["volume"] < 0
        ):
            continue
        typical_price = (candle["high"] + candle["low"] + candle["close"]) / 3
        # Decimal boundaries avoid moving an exact 99.00/.05 value one bin
        # lower because binary floating-point division is slightly imprecise.
        key = int(Decimal(str(typical_price)) // Decimal(str(width)))
        bins[key] = bins.get(key, 0) + candle["volume"]
    return {"kind": "candle_typical_price_volume_proxy", "bins": bins}
