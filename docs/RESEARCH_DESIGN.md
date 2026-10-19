# Study design and evidence classes

The project has one completed **private retrospective study**, a tested framework, a separate synthetic reconciliation case and two future-study specifications. This repository distributes original code/docs and invented fixtures.

| Evidence class | Present work | Reproducible in this checkout? |
|---|---|---|
| Original retrospective market analysis | Recorded negative LVN diagnostic; see RETROSPECTIVE_FINDING.md | No: empirical fixture and full empirical report withheld |
| Synthetic implementation checks | Timing, direction, costs, overlap, controls, reporting and reconciliation | Yes; invented values only |
| Third-party literature | Attributed motivation and venue mechanics in BACKGROUND.md | Links/paraphrases only; no replication claim |
| Forward LVN extension | Frozen reconstructible proxy, bounded collector and replay utility | Code/tests included; new observations and outcomes absent |
| Two future studies | TWAP interaction and funding forecasts/carry | Specifications only; no completed empirical test |

## Retrospective LVN question

Hypothesis: the mean 60-minute forward long markout after recorded standing/entry labels exceeds eligible non-event controls. Null uplift is nonpositive. Proximity has no recorded direction; +1 is an explicit descriptive benchmark, not an inferred flow signal.

The original implementation assigns candle volume to typical-price bins: a proxy, not traded volume at every price or resting liquidity. Use latest as-of entry at most 60 seconds old, first horizon observation no more than four minutes late, signed returns and fees on both notionals. Preserve input, unique, overlap, attempted, missing and scored denominators per horizon. Reserve entry age plus horizon plus delay to limit per-asset overlap. Match prior-day same-asset/hour controls without reuse and outside event windows. Such retrospective matching does not establish a causal counterfactual.

The negative sample findings and timing/label/holdout limitations are recorded separately. All source periods were development data, so a new split would not create an untouched holdout. The exact historical trial count is unknown. No significance, multiplicity-adjusted discovery or general edge claim is made. Future confirmatory inference must address shared event/control days and declared hypothesis families; count/day gates are not proof.

## Future study 1 — TWAP × LVN continuation

Falsifiable hypothesis: direction-known executed TWAP slices near a causally available proxy have larger flow-signed short-horizon markouts than matched TWAP-only and LVN-only observations. Freeze a primary horizon/contrast before new data, cluster by parent and asset/day, and account for overlap and absorbing-side liquidity. A subsequent execution study must also exceed full costs. Required inputs include executed slice direction/time/receipt, anonymous parent linkage, profile versions and executable books. Existing private parent-state observations supply neither executed slices nor direction-known intersections. No empirical continuation test is completed.

## Future study 2 — funding forecast before carry

Falsifiable hypothesis: a frozen pre-settlement forecast improves realized settlement prediction over persistence. Required inputs are immutable prediction issue/receipt/availability times, target settlements and realized records. Settled funding cannot be backdated into a forecast. Use chronological evaluation with settlement-horizon purging. Only then consider a separate hedged-carry test including both venues' executions, basis movement, fees, funding cash, capital and borrow costs. Existing context/settled observations do not identify those outcomes; no empirical forecasting or carry test is completed.

The forward extension of the existing LVN study is specified in FORWARD_PROTOCOL.md and config/forward_protocol.json. It is not an additional completed study and does not recreate absent legacy feature inputs. Synthetic examples demonstrate correctness under their inputs, never market validation.
