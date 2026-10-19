# Forward extension of the LVN study

Status on 19 October 2026: frozen protocol and tested acquisition/feature plumbing. **No prospective performance result exists.** This extends the one retrospective LVN study; the TWAP and funding proposals remain the two separate future studies.

The exact settings are in config/forward_protocol.json. Start with BTC, a 24-hour window of completed one-minute candles, at least 720 usable candles, no gaps above two minutes and a most recent completed candle at most two minutes old. Assign each candle's volume to its typical-price bin. Bin width is five basis points of the last eligible close; the lowest 20th percentile of positive occupied-bin volume defines proxy nodes. Proximity is within 15 bps. This reconstructible forward definition is **not** claimed to recreate the old labels, whose original candles/profile versions are absent.

Each raw candle records venue open/close times; each response records request-send, response-receive and post-parse/persistence availability times, exact raw-byte SHA-256, source endpoint/request and collector-code hash. The book response also retains venue time. Wall-clock synchronization is assumed and checked for obvious inconsistencies; no certified exchange latency is claimed. A candle still open when fetched is excluded even when the saved response is later replayed. Data available today cannot be backdated into a past decision.

Optional bounded acquisition:

```text
python tools/collect_public.py --asset BTC --output work/NEW_RUN
python tools/rebuild_feature.py --run work/NEW_RUN --decision-ms DECISION_UTC_MILLISECONDS
```

Use a new output directory for each run. One invocation makes exactly two public read-only requests, with ten-second timeouts, response-size caps and no retries. There is no automatic loop, scheduler, account, wallet, funded position, signing or order API. A single smoke run cannot create adequate study coverage. Outputs stay in ignored private work/ and are not uploaded as fixtures.

The primary outcome is the assumed-long 60-minute markout difference versus prior-day, same-asset/hour controls, with controls' features reconstructed from their own available inputs. Preserve entry age, missingness and horizon-delay limits, non-overlapping windows and one-to-one controls. Cost scenarios charge both notionals. Quote snapshots permit conditional crossing calculations but do not establish fills or tradability.

Before prospective collection starts, record the protocol/code commit and the first eligible new UTC day. Require at least 20 new qualified UTC days and 30 matched pairs before an evaluation review; these are collection gates, not significance thresholds. Reserve the final ten qualified days without outcome inspection and purge 65 minutes at split boundaries. Validate input quality without repeatedly viewing held-out returns. Any inspected holdout becomes development data. Shared event/control days require dependence-aware inference review before an interval is published; the present exploratory bootstrap is not a confirmatory design.

A bounded 19 October smoke check obtained two responses without reported book-quality issues and reconstructed a proxy from 1,440 completed candles. Its raw data is private working material. This is acquisition evidence, not a return observation or a new successful study. 
