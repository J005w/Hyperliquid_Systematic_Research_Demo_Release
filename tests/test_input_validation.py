import unittest

from hl_demo.cells import day_interval
from hl_demo.event_study import Policy, candle_volume_proxy, funding_prediction, markout


class BoundaryValidationTests(unittest.TestCase):
    def test_boolean_timestamps_are_not_clock_evidence(self):
        with self.assertRaises(ValueError):
            Policy(True, 0)
        with self.assertRaises(ValueError):
            markout([], "A", True, 1, 1)
        prediction = {
            "kind": "predicted",
            "observed_ms": True,
            "available_ms": 1,
            "settlement_ms": 10,
            "rate": 0.001,
        }
        self.assertIsNone(funding_prediction(prediction, 2))

    def test_bad_candle_fields_are_excluded_without_fake_volume(self):
        base = {
            "close_ms": 99,
            "available_ms": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 5,
        }
        invalid = [
            {},
            {**base, "volume": True},
            {**base, "available_ms": 98},
            {**base, "low": 102},
        ]
        self.assertEqual(candle_volume_proxy(invalid, 101)["bins"], {})

    def test_bootstrap_rejects_invalid_design_parameters(self):
        with self.assertRaises(ValueError):
            day_interval([], min_days=1)
        with self.assertRaises(ValueError):
            day_interval([], draws=0)
