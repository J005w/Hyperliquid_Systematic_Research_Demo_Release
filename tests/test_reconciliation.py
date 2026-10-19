"""Independent synthetic controls; no exchange, credentials or market data."""

from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import unittest

from hl_demo.reconciliation import (
    FillEvidence,
    Position,
    Snapshot,
    cash_bridge,
    decimal,
    reconcile_entry,
    reconcile_exit,
    reconcile_position,
    run_case_study,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "reconciliation.json"


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.position = Position("2", "100", "0.10", 100)
        self.full_close = FillEvidence("filled", "-2", "110", "0.11", 200)
        self.flat = Snapshot("0", 0, 201)

    def assess_exit(self, fill=None, snapshot=None):
        return reconcile_exit(self.position, fill or self.full_close, snapshot or self.flat,
                              as_of=205, max_age=30)

    def assert_retained(self, result):
        self.assertIs(result.local_position, self.position)
        self.assertTrue(result.block_new_risk)
        self.assertNotEqual(result.event, "close_confirmed")

    def test_fixture_matches_independent_expected_states_and_cash(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        actual = run_case_study(FIXTURE)
        self.assertEqual(len(actual["scenarios"]), 6)
        for case, row in zip(fixture["scenarios"], actual["scenarios"]):
            with self.subTest(case=case["id"]):
                self.assertEqual(row["id"], case["id"])
                for key, expected in case["expected"].items():
                    observed = row.get(key, row.get("cash_bridge", {}).get(key))
                    self.assertEqual(observed, expected)
        # Independent hand calculation: two units gain ten, two fees, one funding debit.
        bridge = actual["scenarios"][-1]["cash_bridge"]
        self.assertEqual(Decimal(bridge["net_pnl"]), Decimal("20") - Decimal("0.21") - Decimal("0.04"))

    def test_failed_and_rejected_exits_keep_exposure_even_if_snapshot_flat(self):
        for status in ("error", "rejected", "accepted", "unknown"):
            with self.subTest(status=status):
                self.assert_retained(self.assess_exit(replace(self.full_close, status=status)))

    def test_full_fill_and_post_fill_flat_snapshot_allow_close(self):
        result = self.assess_exit()
        self.assertIsNone(result.local_position)
        self.assertFalse(result.block_new_risk)
        self.assertEqual(result.event, "close_confirmed")

    def test_wrong_side_partial_and_overfilled_exit_are_not_full_closes(self):
        for size in ("2", "-1", "-3", "0"):
            with self.subTest(size=size):
                self.assert_retained(self.assess_exit(replace(self.full_close, signed_fill=size)))

    def test_full_fill_with_residual_exchange_exposure_is_unresolved(self):
        self.assert_retained(self.assess_exit(snapshot=replace(self.flat, signed_size="0.5")))

    def test_missing_fill_price_or_fee_does_not_become_zero(self):
        for field in ("price", "fee"):
            with self.subTest(field=field):
                self.assert_retained(self.assess_exit(replace(self.full_close, **{field: None})))

    def test_stale_future_and_missing_snapshots_block_close(self):
        for snapshot in (
            Snapshot("0", 0, 174), Snapshot("0", 0, 206),
            Snapshot(None, 0, 201), Snapshot("0", None, 201), Snapshot("0", 1, 201),
        ):
            with self.subTest(snapshot=snapshot):
                self.assert_retained(self.assess_exit(snapshot=snapshot))

    def test_fresh_snapshot_before_fill_cannot_confirm_exit(self):
        result = self.assess_exit(snapshot=Snapshot("0", 0, 199))
        self.assert_retained(result)
        self.assertIn("snapshot_precedes_fill", result.reasons)

    def test_snapshot_age_boundary_is_explicit(self):
        # Exit at 200, post-fill snapshot at 201, evaluated exactly 30 seconds later.
        result = reconcile_exit(self.position, self.full_close, self.flat, as_of=231, max_age=30)
        self.assertEqual(result.event, "close_confirmed")
        late = reconcile_exit(self.position, self.full_close, self.flat, as_of=232, max_age=30)
        self.assert_retained(late)

    def test_pre_entry_and_future_fill_times_block_close(self):
        for when in (99, 100, 206):
            with self.subTest(when=when):
                self.assert_retained(self.assess_exit(replace(self.full_close, filled_at=when)))

    def test_short_exit_has_same_evidence_requirements(self):
        short = replace(self.position, signed_size="-2")
        fill = replace(self.full_close, signed_fill="2", price="90")
        good = reconcile_exit(short, fill, self.flat, as_of=205)
        self.assertEqual(good.event, "close_confirmed")
        bad = reconcile_exit(short, replace(fill, status="rejected"), self.flat, as_of=205)
        self.assertIs(bad.local_position, short)
        self.assertTrue(bad.block_new_risk)

    def test_signed_drift_blocks_and_preserves_local_evidence(self):
        result = reconcile_position(self.position, Snapshot("-2", 0, 201), as_of=205)
        self.assertIs(result.local_position, self.position)
        self.assertTrue(result.block_new_risk)
        self.assertIn("position_drift", result.reasons)

    def test_matching_snapshot_and_empty_orders_are_control(self):
        result = reconcile_position(self.position, Snapshot("2", 0, 201), as_of=205)
        self.assertFalse(result.block_new_risk)
        self.assertEqual(result.reasons, ())

    def test_missing_exchange_data_is_not_evidence_flat(self):
        result = reconcile_position(None, Snapshot(None, None, 201), as_of=205)
        self.assertTrue(result.block_new_risk)
        self.assertIn("missing_position_snapshot", result.reasons)

    def test_rejected_entry_price_metadata_never_creates_position(self):
        reject = FillEvidence("rejected", "0", "999", "0", 200)
        result = reconcile_entry(reject, self.flat, requested_size="2", as_of=205)
        self.assertIsNone(result.local_position)
        self.assertEqual(result.event, "entry_rejected")
        self.assertFalse(result.block_new_risk)

    def test_reject_with_conflicting_fill_or_exchange_drift_blocks_new_risk(self):
        reject = FillEvidence("rejected", "1", "100", "0.05", 200)
        result = reconcile_entry(reject, self.flat, requested_size="2", as_of=205)
        self.assertTrue(result.block_new_risk)
        self.assertIsNone(result.local_position)
        result = reconcile_entry(replace(reject, signed_fill="0"), Snapshot("1", 0, 201),
                                 requested_size="2", as_of=205)
        self.assertTrue(result.block_new_risk)

    def test_entry_ack_or_partial_fill_is_not_booked_as_requested_position(self):
        for fill in (FillEvidence("accepted", "0", "100", "0", 200),
                     FillEvidence("filled", "1", "100", "0.05", 200)):
            result = reconcile_entry(fill, Snapshot("1", 0, 201), requested_size="2", as_of=205)
            self.assertIsNone(result.local_position)
            self.assertTrue(result.block_new_risk)

    def test_confirmed_entry_control(self):
        fill = FillEvidence("filled", "2", "100", "0.10", 200)
        result = reconcile_entry(fill, Snapshot("2", 0, 201), requested_size="2", as_of=205)
        self.assertEqual(result.local_position, Position("2", "100", "0.10", 200))
        self.assertFalse(result.block_new_risk)

    def test_output_is_deterministic_and_does_not_mutate_fixture(self):
        before = FIXTURE.read_bytes()
        self.assertEqual(run_case_study(FIXTURE), run_case_study(FIXTURE))
        self.assertEqual(FIXTURE.read_bytes(), before)


class CashBridgeTests(unittest.TestCase):
    def bridge(self, **overrides):
        kwargs = dict(
            position=Position("2", "100", "0.10", 100), exit_price="110", exit_fee="0.11",
            closed_at=200, funding_cashflows=[{"id": "invented", "settled_at": 150, "amount": "-0.04"}],
            funding_complete=True, cash_before_open="1000.00", cash_after_close="1019.75",
        )
        kwargs.update(overrides)
        return cash_bridge(**kwargs)

    def test_cash_reconciles_and_cost_signs_are_explicit(self):
        bridge = self.bridge()
        self.assertEqual(bridge["price_pnl"], "20")
        self.assertEqual(bridge["fee_pnl"], "-0.21")
        self.assertEqual(bridge["funding_pnl"], "-0.04")
        self.assertEqual(bridge["net_pnl"], "19.75")
        self.assertEqual(bridge["unexplained_residual"], "0.00")

    def test_equal_price_gain_long_short_symmetry_with_equal_fees_and_cashflows(self):
        long = self.bridge()
        short = self.bridge(position=Position("-2", "100", "0.10", 100), exit_price="90")
        self.assertEqual(long, short)

    def test_settled_funding_receipt_is_positive_and_distinct_from_price(self):
        bridge = self.bridge(funding_cashflows=[{"id": "invented", "settled_at": 150, "amount": "0.04"}],
                             cash_after_close="1019.83")
        self.assertEqual(bridge["funding_pnl"], "0.04")
        self.assertEqual(bridge["net_pnl"], "19.83")
        self.assertEqual(bridge["price_pnl"], "20")

    def test_cash_discrepancy_remains_visible(self):
        bridge = self.bridge(cash_after_close="1019.74")
        self.assertEqual(bridge["unexplained_residual"], "-0.01")

    def test_incomplete_funding_cannot_be_silently_zero(self):
        with self.assertRaises(ValueError):
            self.bridge(funding_complete=False, funding_cashflows=[])
        self.assertEqual(self.bridge(funding_cashflows=[], cash_after_close="1019.79")["funding_pnl"], "0")

    def test_funding_interval_and_duplicate_settlements_are_checked(self):
        for when in (99, 100, 201):
            with self.subTest(when=when), self.assertRaises(ValueError):
                self.bridge(funding_cashflows=[{"id": "invented", "settled_at": when, "amount": "0.04"}])
        at_close = self.bridge(funding_cashflows=[{"id": "invented", "settled_at": 200, "amount": "-0.04"}])
        self.assertEqual(at_close["unexplained_residual"], "0.00")
        flow = {"id": "invented", "settled_at": 150, "amount": "-0.04"}
        with self.assertRaises(ValueError):
            self.bridge(funding_cashflows=[flow, flow])

    def test_nonfinite_float_and_negative_cost_inputs_are_rejected(self):
        for value in (float("nan"), 0.1, "NaN", "Infinity", None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal(value)
        with self.assertRaises(ValueError):
            self.bridge(exit_fee="-0.01")
        with self.assertRaises(ValueError):
            Position("0", "100", "0", 100)
        with self.assertRaises(ValueError):
            Snapshot("0", True, 201)


if __name__ == "__main__":
    unittest.main()
