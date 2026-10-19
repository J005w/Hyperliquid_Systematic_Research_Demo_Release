from hashlib import sha256
import json
import unittest

from hl_demo.synthetic_report import ROOT, analyse, render


class SyntheticReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = analyse()

    def test_committed_reports_reproduce(self):
        self.assertEqual(
            (ROOT / "reports/RESULTS.md").read_text(encoding="utf-8"),
            render(self.result),
        )
        self.assertEqual(
            json.loads((ROOT / "reports/results.json").read_text()), self.result
        )

    def test_synthetic_scope_is_explicit(self):
        self.assertEqual(self.result["evidence_kind"], "synthetic_implementation_only")
        self.assertIn(
            "It does not reproduce or validate the private empirical market study",
            render(self.result),
        )
        self.assertIn(
            "No synthetic result measures market profitability", render(self.result)
        )

    def test_hand_calculated_examples(self):
        for horizon in ("1", "60"):
            cell = self.result["framework_checks"][horizon]
            self.assertEqual(cell["n_scored"], 2)
            self.assertAlmostEqual(cell["mean_signed_markout_bps"], 0)
            self.assertAlmostEqual(cell["mean_markout_less_cost_budget_bps"], -9)
            control = self.result["synthetic_controls"][horizon]
            self.assertEqual(control["n_pairs"], 1)
            self.assertAlmostEqual(control["paired_mean_difference_bps"], 50)

    def test_denominators_reconcile(self):
        for cell in self.result["framework_checks"].values():
            self.assertEqual(
                cell["n_attempted"], cell["n_scored"] + sum(cell["missing"].values())
            )
            self.assertEqual(
                cell["n_unique"], cell["n_attempted"] + cell["n_overlap_removed"]
            )

    def test_inputs_are_hashed_and_market_fixture_is_absent(self):
        self.assertFalse((ROOT / "fixtures/market_panel.json").exists())
        for path, digest in self.result["input_sha256"].items():
            self.assertEqual(sha256((ROOT / path).read_bytes()).hexdigest(), digest)

    def test_fixture_is_explicitly_invented_not_transformed_market_data(self):
        fixture = json.loads((ROOT / "fixtures/synthetic_panel.json").read_text())
        self.assertIn(
            "no source panel sampled, perturbed or fitted", fixture["construction"]
        )
        self.assertTrue(
            all(row["asset"] == "INVENTED_A" for row in fixture["snapshots"])
        )
