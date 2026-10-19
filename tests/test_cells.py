import unittest
from hl_demo.cells import day_interval, matched_controls, score
from hl_demo.event_study import Policy
from test_event_study import row


def event(t=0, asset="A", kind="lvn_standing"):
    return {"asset": asset, "t_ms": t, "type": kind}


class CellTests(unittest.TestCase):
    def test_empty_cells_have_null_metrics(self):
        c = score([], [], [1, 5])
        for r in c.values():
            self.assertEqual(r["n_scored"], 0)
            self.assertIsNone(r["mean_signed_markout_bps"])
            self.assertFalse(r["promotable"])

    def test_horizon_specific_denominators(self):
        r = score([event()], [row(0), row(60_000, 101)], [1, 5], Policy(0, 0))
        self.assertEqual(r["1"]["n_scored"], 1)
        self.assertEqual(r["5"]["n_scored"], 0)
        self.assertEqual(r["5"]["missing"], {"missing_or_delayed_exit": 1})

    def test_duplicates_and_overlap_not_independent(self):
        e = [event(), event(), event(30_000), event(400_000)]
        r = score(e, [row(0), row(60_000), row(400_000), row(460_000)], [1])["1"]
        self.assertEqual(
            (
                r["n_input"],
                r["n_unique"],
                r["n_duplicates_removed"],
                r["n_overlap_removed"],
                r["n_scored"],
            ),
            (4, 3, 1, 1, 2),
        )

    def test_denominator_partition(self):
        r = score([event(), event(400_000), event(800_000)], [row(400_000)], [1])["1"]
        self.assertEqual(r["n_unique"], r["n_overlap_removed"] + r["n_attempted"])
        self.assertEqual(r["n_attempted"], r["n_scored"] + sum(r["missing"].values()))

    def test_entry_age_reserved_to_prevent_hidden_overlap(self):
        e = [event(60_000), event(150_000)]
        rows = [row(0), row(120_000), row(210_000)]
        r = score(e, rows, [1], Policy(60_000, 0))["1"]
        self.assertEqual(r["n_overlap_removed"], 1)
        self.assertEqual(r["n_scored"], 1)

    def test_short_sign_affects_both_return_and_hit_fraction(self):
        rows = [row(0), row(60_000, 90)]
        long = score([event()], rows, [1], side=1)["1"]
        short = score([event()], rows, [1], side=-1)["1"]
        self.assertEqual(
            long["mean_signed_markout_bps"], -short["mean_signed_markout_bps"]
        )
        self.assertEqual(long["positive_signed_markout_fraction"], 0)
        self.assertEqual(short["positive_signed_markout_fraction"], 1)

    def test_prior_day_non_event_control_matched_once(self):
        day = 86_400_000
        rows = [
            row(0),
            row(60_000, 101),
            row(day),
            row(day + 60_000, 102),
            row(2 * day),
            row(2 * day + 60_000, 103),
        ]
        r = matched_controls([event(day), event(2 * day)], rows, 1, Policy(0, 0))
        self.assertEqual(r["n_pairs"], 1)
        pair = r["pairs"][0]
        self.assertLess(pair["control_ms"], pair["event_ms"])
        self.assertAlmostEqual(pair["difference_bps"], 100)

    def test_control_cannot_overlap_event(self):
        day = 86_400_000
        r = matched_controls(
            [event(), event(day)],
            [row(0), row(60_000), row(day), row(day + 60_000)],
            1,
            Policy(0, 0),
        )
        self.assertEqual(r["n_pairs"], 0)

    def test_block_count_not_event_count_controls_interval(self):
        pairs = [{"event_ms": 0, "difference_bps": 1} for _ in range(1000)]
        ci, why = day_interval(pairs)
        self.assertIsNone(ci)
        self.assertIn("8 UTC day blocks", why)

    def test_day_interval_reproducible(self):
        pairs = [{"event_ms": d * 86_400_000, "difference_bps": d} for d in range(10)]
        a = day_interval(pairs, draws=100)
        self.assertEqual(a, day_interval(pairs, draws=100))
        self.assertLessEqual(a[0][0], 4.5)
        self.assertGreaterEqual(a[0][1], 4.5)
