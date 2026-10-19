"""Bounded public market-data acquisition and reproducible candle-LVN features.

Only candleSnapshot and l2Book are permitted. This module has no account,
credential, signing, order, scheduler or unbounded collection interface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import time
from typing import Any, Callable
from urllib.request import Request, urlopen

from .event_study import candle_volume_proxy, positive

INFO_URL = "https://api.hyperliquid.xyz/info"
MAX_RESPONSE_BYTES = 2_000_000


def request_public(payload: dict[str, Any]) -> bytes:
    """Two fixed request schemas; never accept a caller-supplied URL or account."""
    kind = payload.get("type")
    if kind == "l2Book":
        valid = set(payload) == {"type", "coin"} and payload["coin"] in {"BTC", "ETH"}
    elif kind == "candleSnapshot":
        query = payload.get("req", {})
        valid = (
            set(payload) == {"type", "req"}
            and set(query) == {"coin", "interval", "startTime", "endTime"}
            and query["coin"] in {"BTC", "ETH"}
            and query["interval"] == "1m"
            and isinstance(query["startTime"], int)
            and isinstance(query["endTime"], int)
            and 0 < query["endTime"] - query["startTime"] <= 86_400_000
        )
    else:
        valid = False
    if not valid:
        raise ValueError("Only bounded public candle and book requests are supported")
    request = Request(
        INFO_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds size limit")
    return body


def book_quality(response: Any, received_ms: int) -> list[str]:
    """Record quality failures; a quote snapshot is never evidence of a fill."""
    if not isinstance(response, dict):
        return ["malformed_book"]
    exchange_ms = response.get("time")
    issues = []
    if not isinstance(exchange_ms, int):
        issues.append("missing_exchange_time")
    elif not -1000 <= received_ms - exchange_ms <= 10_000:
        issues.append("stale_or_clock_inconsistent_book")
    try:
        bid = float(response["levels"][0][0]["px"])
        ask = float(response["levels"][1][0]["px"])
        if not positive(bid) or not positive(ask) or bid > ask:
            issues.append("invalid_or_crossed_book")
    except (KeyError, IndexError, TypeError, ValueError):
        issues.append("missing_book_sides")
    return issues


def collect_once(
    destination: Path,
    asset: str = "BTC",
    transport: Callable[[dict[str, Any]], bytes] = request_public,
    clock_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
) -> dict[str, Any]:
    """One run, exactly two requests, no retries, new directory required.

    Exact response bytes and envelopes are written exclusively. Historic
    candle closes retain the current response availability time; receipt today
    does not prove the candle was available to a decision in the past.
    """
    if asset not in {"BTC", "ETH"}:
        raise ValueError("asset must be BTC or ETH")
    destination.mkdir(parents=True, exist_ok=False)
    end_ms = clock_ms()
    requests = [
        {
            "type": "candleSnapshot",
            "req": {
                "coin": asset,
                "interval": "1m",
                "startTime": end_ms - 86_400_000,
                "endTime": end_ms,
            },
        },
        {"type": "l2Book", "coin": asset},
    ]
    records = []
    for index, payload in enumerate(requests):
        sent_ms = clock_ms()
        started = time.monotonic_ns()
        record = {
            "schema_version": 1,
            "asset": asset,
            "request": payload,
            "endpoint": INFO_URL,
            "request_sent_ms": sent_ms,
        }
        try:
            body = transport(payload)
            received_ms = clock_ms()
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("response exceeds size limit")
            response = json.loads(body)
            filename = f"{index:02d}_response.json"
            with (destination / filename).open("xb") as output:
                output.write(body)
            issues = (
                book_quality(response, received_ms)
                if payload["type"] == "l2Book"
                else []
            )
            if payload["type"] == "candleSnapshot" and not isinstance(response, list):
                issues.append("malformed_candles")
            available_ms = clock_ms()
            if not sent_ms <= received_ms <= available_ms:
                issues.append("local_clock_regressed")
            record.update(
                response_received_ms=received_ms,
                available_ms=available_ms,
                exchange_ms=response.get("time")
                if isinstance(response, dict)
                else None,
                candle_time_basis="t=open and T=close; full raw values retained",
                elapsed_monotonic_ns=time.monotonic_ns() - started,
                response_file=filename,
                response_sha256=sha256(body).hexdigest(),
                quality_issues=issues,
                status="received",
            )
        except (OSError, ValueError, TypeError) as error:
            record.update(status="failed", error_type=type(error).__name__)
        records.append(record)
    manifest = {
        "schema_version": 1,
        "evidence_class": "public_collection_plumbing_only",
        "created_utc": datetime.fromtimestamp(end_ms / 1000, timezone.utc).isoformat(),
        "collector_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "clock_limit": "Wall clock assumed UTC-synchronized; no certified exchange latency or clock offset.",
        "requests": records,
    }
    with (destination / "manifest.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    return manifest


def reconstruct_lvn(
    response: list[dict[str, Any]],
    available_ms: int,
    decision_ms: int,
    *,
    bin_bps: float = 5.0,
    min_candles: int = 720,
) -> dict[str, Any]:
    """Frozen forward-study proxy, not a reconstruction of legacy labels.

    Equal-width bins use the most recent eligible close for scale; the lowest
    20th percentile of occupied candle-volume bins forms the LVN proxy set.
    """
    if not positive(bin_bps) or min_candles < 2:
        raise ValueError("invalid feature parameters")
    if available_ms > decision_ms:
        return {"status": "not_yet_available"}
    candles = []
    seen = set()
    for raw in response:
        try:
            opened_ms, closed_ms = int(raw["t"]), int(raw["T"])
            if closed_ms in seen:
                return {"status": "duplicate_candle"}
            if not decision_ms - 86_400_000 <= closed_ms < decision_ms:
                continue
            # A candle still open when fetched is never its final close, even
            # if this saved response is replayed at a later decision time.
            if closed_ms >= available_ms:
                continue
            if closed_ms < opened_ms or closed_ms - opened_ms != 59_999:
                return {"status": "invalid_candle_interval"}
            candle = {
                "close_ms": closed_ms,
                "available_ms": available_ms,
                "high": float(raw["h"]),
                "low": float(raw["l"]),
                "close": float(raw["c"]),
                "volume": float(raw["v"]),
            }
            if not all(positive(candle[key]) for key in ("high", "low", "close")):
                return {"status": "invalid_candle_price"}
            if (
                not candle["low"] <= candle["close"] <= candle["high"]
                or not isfinite(candle["volume"])
                or candle["volume"] < 0
            ):
                return {"status": "invalid_candle_values"}
            candles.append(candle)
            seen.add(closed_ms)
        except (KeyError, TypeError, ValueError):
            return {"status": "malformed_candle"}
    candles.sort(key=lambda candle: candle["close_ms"])
    if len(candles) < min_candles:
        return {"status": "insufficient_completed_candles", "n_candles": len(candles)}
    if any(
        right["close_ms"] - left["close_ms"] > 120_000
        for left, right in zip(candles, candles[1:])
    ):
        return {"status": "candle_gap"}
    if decision_ms - candles[-1]["close_ms"] > 120_000:
        return {"status": "stale_candle_window"}
    last_close = candles[-1]["close"]
    width = last_close * bin_bps / 10_000
    profile = candle_volume_proxy(candles, decision_ms, width)
    bins = profile["bins"]
    occupied = sorted(volume for volume in bins.values() if volume > 0)
    if not occupied:
        return {"status": "zero_volume"}
    threshold = occupied[int(0.2 * (len(occupied) - 1))]
    nodes = [
        (index + 0.5) * width
        for index, volume in bins.items()
        if 0 < volume <= threshold
    ]
    nearest = min(nodes, key=lambda price: abs(price - last_close))
    distance_bps = abs(nearest - last_close) / last_close * 10_000
    return {
        "status": "ok",
        "kind": profile["kind"],
        "n_candles": len(candles),
        "available_ms": available_ms,
        "decision_ms": decision_ms,
        "bin_width": width,
        "lvn_nodes": sorted(nodes),
        "nearest_lvn": nearest,
        "distance_bps": distance_bps,
        "standing_within_15bps": distance_bps <= 15,
        "profile_sha256": sha256(json.dumps(bins, sort_keys=True).encode()).hexdigest(),
    }
