"""Offline synthetic position reconciliation and closed-trade cash attribution.

Concepts attributed in docs/RECONCILIATION.md. No exchange client is imported.
Money and quantities enter as decimal strings; floats are deliberately rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any, Mapping


def decimal(value: str | Decimal | int) -> Decimal:
    """Parse a finite exact value; never silently coerce a float or missing value."""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("expected a finite decimal string or integer")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("non-finite decimal")
    return result


def _time(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("timestamps and age limits must be non-negative integers")
    return value


@dataclass(frozen=True)
class Position:
    """Last reconciled single position; positive size is long, negative is short."""

    signed_size: Decimal
    entry_price: Decimal
    entry_fee: Decimal
    opened_at: int

    def __post_init__(self) -> None:
        for name in ("signed_size", "entry_price", "entry_fee"):
            object.__setattr__(self, name, decimal(getattr(self, name)))
        _time(self.opened_at)
        if self.signed_size == 0 or self.entry_price <= 0 or self.entry_fee < 0:
            raise ValueError("position requires nonzero size, positive price and nonnegative fee")


@dataclass(frozen=True)
class Snapshot:
    """Synthetic exchange evidence. None denotes unavailable evidence, not zero."""

    signed_size: Decimal | None
    open_orders: int | None
    observed_at: int

    def __post_init__(self) -> None:
        if self.signed_size is not None:
            object.__setattr__(self, "signed_size", decimal(self.signed_size))
        if self.open_orders is not None:
            _time(self.open_orders)
        _time(self.observed_at)


@dataclass(frozen=True)
class FillEvidence:
    """A response is not a fill: explicit full size, price and fee are required."""

    status: str
    signed_fill: Decimal
    price: Decimal | None
    fee: Decimal | None
    filled_at: int

    def __post_init__(self) -> None:
        if self.status not in {"error", "rejected", "accepted", "filled", "unknown"}:
            raise ValueError("unsupported evidence status")
        object.__setattr__(self, "signed_fill", decimal(self.signed_fill))
        for name in ("price", "fee"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, decimal(value))
        _time(self.filled_at)
        if self.price is not None and self.price <= 0:
            raise ValueError("fill price must be positive")
        if self.fee is not None and self.fee < 0:
            raise ValueError("fees are nonnegative costs in this demo")


@dataclass(frozen=True)
class Decision:
    local_position: Position | None
    block_new_risk: bool
    event: str
    reasons: tuple[str, ...]


def _snapshot_issues(snapshot: Snapshot, *, as_of: int, max_age: int) -> list[str]:
    _time(as_of)
    _time(max_age)
    issues: list[str] = []
    if snapshot.observed_at > as_of:
        issues.append("future_snapshot")
    elif as_of - snapshot.observed_at > max_age:
        issues.append("stale_snapshot")
    if snapshot.signed_size is None:
        issues.append("missing_position_snapshot")
    if snapshot.open_orders is None:
        issues.append("missing_order_snapshot")
    elif snapshot.open_orders:
        issues.append("unresolved_open_orders")
    return issues


def reconcile_position(
    position: Position | None, snapshot: Snapshot, *, as_of: int, max_age: int = 30
) -> Decision:
    """Detect discrepancies and block new risk without changing the local journal."""
    issues = _snapshot_issues(snapshot, as_of=as_of, max_age=max_age)
    local_size = position.signed_size if position else Decimal(0)
    if snapshot.signed_size is not None and snapshot.signed_size != local_size:
        issues.append("position_drift")
    return Decision(position, bool(issues), "reconciliation_block" if issues else "matched", tuple(issues))


def reconcile_exit(
    position: Position, fill: FillEvidence, snapshot: Snapshot, *, as_of: int, max_age: int = 30
) -> Decision:
    """Clear local exposure only for a full reducing fill and fresh post-fill flat evidence.

    Partial or ambiguous fills require investigation: the retained position is the
    last reconciled state, not a claim that its size still equals exchange exposure.
    """
    issues = _snapshot_issues(snapshot, as_of=as_of, max_age=max_age)
    if fill.status != "filled":
        issues.append("exit_not_confirmed_filled")
    if fill.signed_fill != -position.signed_size:
        issues.append("full_reducing_fill_missing")
    if fill.price is None or fill.fee is None:
        issues.append("fill_price_or_fee_missing")
    if not position.opened_at < fill.filled_at <= as_of:
        issues.append("invalid_fill_time")
    if snapshot.observed_at < fill.filled_at:
        issues.append("snapshot_precedes_fill")
    if snapshot.signed_size is not None and snapshot.signed_size != 0:
        issues.append("exchange_not_flat")
    if issues:
        return Decision(position, True, "exit_unresolved", tuple(issues))
    return Decision(None, False, "close_confirmed", ())


def reconcile_entry(
    fill: FillEvidence, snapshot: Snapshot, *, requested_size: Decimal, as_of: int, max_age: int = 30
) -> Decision:
    """Demonstrate a single entry from flat; rejects and acknowledgements cannot book fills."""
    requested_size = decimal(requested_size)
    if requested_size == 0:
        raise ValueError("requested entry size cannot be zero")
    if fill.status in {"rejected", "error"}:
        check = reconcile_position(None, snapshot, as_of=as_of, max_age=max_age)
        reasons = ("entry_rejected",) + check.reasons
        if fill.signed_fill != 0:
            reasons += ("conflicting_fill_evidence",)
        return Decision(None, check.block_new_risk or fill.signed_fill != 0, "entry_rejected", reasons)
    issues = _snapshot_issues(snapshot, as_of=as_of, max_age=max_age)
    if fill.status != "filled" or fill.signed_fill != requested_size:
        issues.append("full_entry_fill_missing")
    if fill.price is None or fill.fee is None:
        issues.append("fill_price_or_fee_missing")
    if fill.filled_at > as_of or snapshot.observed_at < fill.filled_at:
        issues.append("invalid_fill_time")
    if snapshot.signed_size is not None and snapshot.signed_size != requested_size:
        issues.append("position_drift")
    if issues:
        return Decision(None, True, "entry_unresolved", tuple(issues))
    position = Position(requested_size, fill.price, fill.fee, fill.filled_at)
    return Decision(position, False, "entry_confirmed", ())


def cash_bridge(
    position: Position,
    *,
    exit_price: Decimal,
    exit_fee: Decimal,
    closed_at: int,
    funding_cashflows: list[Mapping[str, Any]],
    funding_complete: bool,
    cash_before_open: Decimal,
    cash_after_close: Decimal,
) -> dict[str, str]:
    """Closed linear-perpetual P&L, using settled signed cash amounts, not predicted rates.

    Funding timestamps must lie in (opened_at, closed_at]. The independent observed
    closing cash yields a residual; fees are debits. No margin/notional cash flow,
    transfers, rebates, conversion or unrealized P&L is represented in this model.
    """
    if funding_complete is not True:
        raise ValueError("incomplete funding cannot be silently treated as zero")
    _time(closed_at)
    if closed_at <= position.opened_at:
        raise ValueError("close must follow entry")
    price, fee = decimal(exit_price), decimal(exit_fee)
    if price <= 0 or fee < 0:
        raise ValueError("invalid exit price or fee")
    funding = Decimal(0)
    seen: set[str] = set()
    for flow in funding_cashflows:
        flow_id = flow["id"]
        if not isinstance(flow_id, str) or not flow_id or flow_id in seen:
            raise ValueError("funding cashflow identifiers must be unique nonempty strings")
        seen.add(flow_id)
        settled_at = _time(flow["settled_at"])
        if not position.opened_at < settled_at <= closed_at:
            raise ValueError("funding cashflow outside holding interval")
        funding += decimal(flow["amount"])
    price_pnl = position.signed_size * (price - position.entry_price)
    fee_pnl = -position.entry_fee - fee
    net = price_pnl + fee_pnl + funding
    before, after = decimal(cash_before_open), decimal(cash_after_close)
    expected_after = before + net
    return {key: str(value) for key, value in {
        "price_pnl": price_pnl,
        "fee_pnl": fee_pnl,
        "funding_pnl": funding,
        "net_pnl": net,
        "cash_before_open": before,
        "expected_cash_after_close": expected_after,
        "observed_cash_after_close": after,
        "unexplained_residual": after - expected_after,
    }.items()}


def run_case_study(fixture_path: str | Path) -> dict[str, Any]:
    """Run explicitly synthetic scenarios and expose deterministic JSON-safe evidence."""
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or fixture.get("data_class") != "synthetic":
        raise ValueError("requires the version 1 synthetic fixture")
    rows = []
    for case in fixture["scenarios"]:
        position = Position(**case["position"]) if case.get("position") else None
        snapshot = Snapshot(**case["snapshot"])
        common = {"as_of": case["as_of"], "max_age": fixture["max_snapshot_age_seconds"]}
        if case["kind"] == "exit":
            if position is None:
                raise ValueError("exit case requires an existing position")
            fill = FillEvidence(**case["fill"])
            decision = reconcile_exit(position, fill, snapshot, **common)
        elif case["kind"] == "entry":
            if position is not None:
                raise ValueError("entry case must begin flat")
            decision = reconcile_entry(FillEvidence(**case["fill"]), snapshot,
                                       requested_size=case["requested_size"], **common)
        elif case["kind"] == "snapshot":
            decision = reconcile_position(position, snapshot, **common)
        else:
            raise ValueError("unsupported scenario kind")
        row: dict[str, Any] = {
            "id": case["id"], "event": decision.event,
            "local_signed_size": str(decision.local_position.signed_size) if decision.local_position else "0",
            "block_new_risk": decision.block_new_risk,
            "close_records": int(decision.event == "close_confirmed"),
            "reasons": list(decision.reasons),
        }
        if "cash" in case:
            if decision.event != "close_confirmed":
                raise ValueError("cash bridge requires a confirmed full close")
            row["cash_bridge"] = cash_bridge(position, exit_price=fill.price, exit_fee=fill.fee,
                                             closed_at=fill.filled_at, **case["cash"])
        rows.append(row)
    return {"data_class": "synthetic_implementation_test", "scenarios": rows,
            "limitation": "Demonstrates accounting and state invariants; no market profitability or live equivalence evidence."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default="fixtures/reconciliation.json")
    args = parser.parse_args()
    print(json.dumps(run_case_study(args.fixture), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
