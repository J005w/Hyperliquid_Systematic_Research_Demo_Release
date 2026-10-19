import json
from pathlib import Path
import tempfile
import unittest

from hl_demo.public_data import (
    book_quality,
    collect_once,
    reconstruct_lvn,
    request_public,
)


def candle(index, price=100, volume=1):
    return {
        "t": index * 60_000,
        "T": (index + 1) * 60_000 - 1,
        "h": str(price),
        "l": str(price),
        "c": str(price),
        "v": str(volume),
    }


class PublicCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(__file__).resolve().parents[1] / "work" / "tests"
        cls.scratch.mkdir(parents=True, exist_ok=True)

    def test_unsafe_requests_rejected_before_network(self):
        for payload in [
            {"type": "order"},
            {"type": "userFills", "user": "SYNTHETIC"},
            {"type": "l2Book", "coin": "BTC", "user": "SYNTHETIC"},
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": "BTC",
                    "interval": "1m",
                    "startTime": 0,
                    "endTime": 86_400_001,
                },
            },
        ]:
            with self.assertRaises(ValueError):
                request_public(payload)

    def test_exactly_two_requests_with_exclusive_hashed_inputs(self):
        requests = []

        def transport(payload):
            requests.append(payload)
            if payload["type"] == "candleSnapshot":
                return json.dumps([candle(0)]).encode()
            return json.dumps(
                {"time": 100, "levels": [[{"px": "99"}], [{"px": "101"}]]}
            ).encode()

        times = iter(range(100, 120))
        with tempfile.TemporaryDirectory(dir=self.scratch) as folder:
            output = Path(folder) / "run"
            result = collect_once(
                output, transport=transport, clock_ms=lambda: next(times)
            )
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(r["status"] == "received" for r in result["requests"]))
            for record in result["requests"]:
                self.assertLessEqual(
                    record["request_sent_ms"], record["response_received_ms"]
                )
                self.assertLessEqual(
                    record["response_received_ms"], record["available_ms"]
                )
                self.assertEqual(len(record["response_sha256"]), 64)
            with self.assertRaises(FileExistsError):
                collect_once(output, transport=transport)

    def test_failures_persist_without_retry_or_fake_receipt(self):
        calls = []

        def fail(payload):
            calls.append(payload)
            raise OSError("synthetic failure")

        with tempfile.TemporaryDirectory(dir=self.scratch) as folder:
            result = collect_once(Path(folder) / "run", transport=fail)
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(r["status"] == "failed" for r in result["requests"]))
            self.assertTrue(
                all("response_received_ms" not in r for r in result["requests"])
            )

    def test_quote_quality_rejects_stale_crossed_missing_books(self):
        crossed = {"time": 100, "levels": [[{"px": "101"}], [{"px": "99"}]]}
        self.assertIn("invalid_or_crossed_book", book_quality(crossed, 100))
        self.assertIn("stale_or_clock_inconsistent_book", book_quality(crossed, 20_000))
        self.assertIn("missing_book_sides", book_quality({"time": 100}, 100))


class ForwardFeatureTests(unittest.TestCase):
    def test_feature_has_hand_checkable_bin_scale_and_distance(self):
        rows = [candle(0, 99, 1), candle(1, 100, 10), candle(2, 100, 10)]
        feature = reconstruct_lvn(rows, 180_000, 180_001, min_candles=3)
        self.assertEqual(feature["status"], "ok")
        self.assertAlmostEqual(feature["bin_width"], 0.05)
        self.assertAlmostEqual(feature["nearest_lvn"], 99.025)
        self.assertFalse(feature["standing_within_15bps"])

    def test_future_data_and_unfinished_saved_candle_do_not_change_feature(self):
        rows = [candle(0), candle(1)]
        baseline = reconstruct_lvn(rows, 120_000, 120_001, min_candles=2)
        future = candle(2, 50000, 10000000)
        self.assertEqual(
            baseline, reconstruct_lvn(rows + [future], 120_000, 120_001, min_candles=2)
        )
        later = reconstruct_lvn(rows + [future], 120_000, 180_001, min_candles=2)
        self.assertEqual(later["n_candles"], 2)

    def test_unreceived_response_and_bad_quality_cannot_form_features(self):
        self.assertEqual(reconstruct_lvn([], 200, 100)["status"], "not_yet_available")
        rows = [candle(0), candle(1)]
        self.assertEqual(
            reconstruct_lvn(rows, 120_000, 120_001)["status"],
            "insufficient_completed_candles",
        )
        self.assertEqual(
            reconstruct_lvn(rows + [candle(0)], 120_000, 120_001, min_candles=2)[
                "status"
            ],
            "duplicate_candle",
        )
        self.assertEqual(
            reconstruct_lvn([candle(0), candle(4)], 300_000, 300_001, min_candles=2)[
                "status"
            ],
            "candle_gap",
        )
        self.assertEqual(
            reconstruct_lvn([candle(0), candle(1)], 120_000, 300_001, min_candles=2)[
                "status"
            ],
            "stale_candle_window",
        )
