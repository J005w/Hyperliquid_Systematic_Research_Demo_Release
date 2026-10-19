import math
import unittest
from hl_demo.event_study import (
    Policy,
    candle_volume_proxy,
    funding_prediction,
    markout,
    observations,
    quote_pnl,
)


def row(t, mark=100, available=None, asset="A"):
    return {
        "asset": asset,
        "t_ms": t,
        "available_ms": t if available is None else available,
        "mark": mark,
    }


class TimingTests(unittest.TestCase):
    def test_no_fall_forward_entry(self):
        self.assertEqual(
            markout([row(1), row(60_000, 110)], "A", 0, 1, 1)["reason"],
            "missing_or_stale_entry",
        )

    def test_stale_entry_rejected(self):
        self.assertEqual(
            markout([row(0), row(120_001)], "A", 60_001, 1, 1)["reason"],
            "missing_or_stale_entry",
        )

    def test_future_received_entry_rejected(self):
        self.assertEqual(
            markout([row(0, available=1), row(60_000)], "A", 0, 1, 1)["reason"],
            "missing_or_stale_entry",
        )

    def test_missing_availability_is_rejected(self):
        r = row(0)
        del r["available_ms"]
        self.assertEqual(
            markout([r, row(60_000)], "A", 0, 1, 1)["reason"], "missing_or_stale_entry"
        )

    def test_negative_latency_is_rejected(self):
        self.assertEqual(
            markout([row(10, available=0), row(60_010)], "A", 10, 1, 1)["reason"],
            "missing_or_stale_entry",
        )

    def test_unbounded_exit_delay_rejected(self):
        self.assertEqual(
            markout([row(0), row(300_001)], "A", 0, 1, 1)["reason"],
            "missing_or_delayed_exit",
        )

    def test_exit_not_before_target(self):
        r = markout([row(0), row(59_999, 200), row(60_000, 101)], "A", 0, 1, 1)
        self.assertAlmostEqual(r["signed_bps"], 100)

    def test_exit_availability_must_be_bounded(self):
        self.assertEqual(
            markout([row(0), row(60_000, available=300_001)], "A", 0, 1, 1)["reason"],
            "missing_or_delayed_exit",
        )

    def test_boundary_tolerances_are_inclusive(self):
        r = markout([row(0), row(360_000)], "A", 60_000, 1, 1)
        self.assertIsNone(r["reason"])
        self.assertEqual(r["exit_delay_ms"], 240_000)

    def test_future_data_perturbation_cannot_change_selected_markout(self):
        rows = [row(0), row(60_000, 101)]
        baseline = markout(rows, "A", 0, 1, 1)
        self.assertEqual(baseline, markout(rows + [row(600_000, 500000)], "A", 0, 1, 1))

    def test_nonfinite_and_zero_prices_rejected(self):
        for bad in [0, -1, math.nan, math.inf, True, None]:
            self.assertEqual(
                markout([row(0, bad), row(60_000)], "A", 0, 1, 1)["reason"],
                "missing_or_stale_entry",
            )

    def test_other_asset_cannot_fill_gap(self):
        self.assertEqual(
            markout([row(0), row(60_000, asset="B")], "A", 0, 1, 1)["reason"],
            "missing_or_delayed_exit",
        )


class CostTests(unittest.TestCase):
    def test_signed_long_short_symmetry_and_both_notional_fees(self):
        rows = [row(0, 100), row(60_000, 110)]
        long = markout(rows, "A", 0, 1, 1)
        short = markout(rows, "A", 0, 1, -1)
        self.assertAlmostEqual(long["signed_bps"], 1000)
        self.assertEqual(long["signed_bps"], -short["signed_bps"])
        self.assertAlmostEqual(long["cost_budget_bps"], 4.5 * (1 + 1.1))
        self.assertEqual(long["cost_budget_bps"], short["cost_budget_bps"])

    def test_unknown_direction_not_imputed(self):
        for bad in [0, None, True, "long"]:
            with self.assertRaises(ValueError):
                markout([row(0), row(60_000)], "A", 0, 1, bad)

    def test_flat_mark_loses_roundtrip_fees(self):
        self.assertAlmostEqual(
            markout([row(0), row(60_000)], "A", 0, 1, 1)[
                "markout_less_cost_budget_bps"
            ],
            -9,
        )

    def test_crossing_quote_spread_costs_both_directions(self):
        for side in [-1, 1]:
            r = quote_pnl(99, 101, 99, 101, side, fee_bps=0)
            self.assertEqual(r["net_cash"], -2)

    def test_quote_cash_hand_calculation_includes_funding(self):
        r = quote_pnl(99, 100, 110, 111, 1, fee_bps=10, funding_cash=-0.05)
        self.assertAlmostEqual(r["fee_cash"], -0.21)
        self.assertAlmostEqual(r["net_cash"], 9.74)

    def test_quote_short_uses_bid_then_ask(self):
        self.assertAlmostEqual(
            quote_pnl(100, 101, 89, 90, -1, fee_bps=0)["net_cash"], 10
        )

    def test_invalid_cost_quote_and_horizon_rejected(self):
        with self.assertRaises(ValueError):
            quote_pnl(101, 100, 100, 101, 1)
        with self.assertRaises(ValueError):
            quote_pnl(100, 101, 100, 101, 1, fee_bps=math.nan)
        with self.assertRaises(ValueError):
            markout([], "A", 0, 1, 1, fee_bps=-1)
        with self.assertRaises(ValueError):
            observations([], "A", 0, 0)
        with self.assertRaises(ValueError):
            Policy(-1, 0)


class AvailabilityTests(unittest.TestCase):
    def prediction(self, **kw):
        return {
            "kind": "predicted",
            "observed_ms": 100,
            "available_ms": 110,
            "settlement_ms": 1000,
            "rate": 0.0001,
            **kw,
        }

    def test_prediction_available_before_decision(self):
        self.assertEqual(funding_prediction(self.prediction(), 200), 0.0001)

    def test_settled_funding_is_not_prediction(self):
        self.assertIsNone(funding_prediction(self.prediction(kind="settled"), 200))

    def test_funding_future_availability_and_settlement_rejected(self):
        for r in [
            self.prediction(available_ms=201),
            self.prediction(settlement_ms=200),
            self.prediction(available_ms=None),
            self.prediction(rate=math.nan),
            self.prediction(observed_ms=120),
        ]:
            self.assertIsNone(funding_prediction(r, 200))

    def test_stale_prediction_rejected(self):
        self.assertIsNone(
            funding_prediction(self.prediction(settlement_ms=1_000_000), 400_000)
        )

    def test_candles_must_be_complete_and_received(self):
        base = {
            "close_ms": 99,
            "available_ms": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 5,
        }
        result = candle_volume_proxy(
            [
                base,
                {**base, "close_ms": 100, "volume": 900},
                {**base, "available_ms": 101, "volume": 800},
            ],
            100,
        )
        self.assertEqual(
            result, {"kind": "candle_typical_price_volume_proxy", "bins": {100: 5}}
        )

    def test_future_candle_values_cannot_change_proxy(self):
        c = {
            "close_ms": 101,
            "available_ms": 101,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 100,
        }
        self.assertEqual(
            candle_volume_proxy([c], 100),
            candle_volume_proxy([{**c, "volume": 1000000}], 100),
        )
