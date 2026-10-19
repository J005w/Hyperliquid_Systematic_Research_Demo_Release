# Synthetic reconciliation case study

This is an original, offline implementation exercise based on the author's personal work on execution-state integrity. It is separate from the market-research experiments. Every fixture value is invented: quantities, prices, cash amounts, identifiers and relative-second timestamps. It contains no account data, historical trades, signing, order submission or exchange connection.

The question is whether incomplete or contradictory execution evidence can create a fictitious fill or close, and whether a confirmed closed position reconciles exactly into price, fees and settled funding. The falsifiable implementation claim is: failed/rejected exits retain the last reconciled local position and block new risk; rejected entries create no position; mismatched or unavailable exchange evidence blocks new risk; only explicit full-fill and fresh post-fill evidence permit closure. A single counterexample fails this claim. This is a correctness claim on the implemented model, not a hypothesis about market returns.

## Provenance and scope

The demonstration code and fixture were written for this project. They model separation of exit attempts, confirmed fills, position snapshots and local close records, with independent price/fee/funding cash attribution. No live execution code, original operational logs, balances, account identifiers or source configuration is included. MIT covers the original implementation and invented fixture. Nothing here establishes live/replay equivalence or readiness to trade.

## Controls and results

The fixture defines six cases with independent expected outcomes; the test suite compares the executed output against them:

| Case | Expected result |
| --- | --- |
| Failed exit from long two units | Retain local two units, block new risk, zero close records |
| Rejected exit from short two units | Retain local minus two units, block new risk, zero close records |
| Accepted exit acknowledgement with a resting order | Retain exposure, block new risk, zero close records |
| Rejected entry containing price metadata | Stay flat, zero fill/close records; fresh matching flat evidence permits later risk assessment |
| Local flat, exchange one unit and an open order | Preserve local evidence, flag discrepancy and block new risk |
| Confirmed full exit, fresh flat snapshot and no open orders | One confirmed close and the cash bridge below |

The regression suite adds wrong-direction, partial and overfilled exits; pre-fill, stale, future and unavailable snapshots; unavailable fees; entry acknowledgement without a fill; conflicting reject/fill evidence; long/short symmetry; duplicate funding settlements; funding coverage and interval boundaries; visible cash residuals; exact decimal validation; and deterministic report output.

The positive controls matter: a confirmed full close and a matching fresh position can pass. Blocking everything would not satisfy the intended behavior.

## Hand-checkable cash bridge

The closed-position example holds **long two units from 100 to 110**. Entry fee is 0.10 and exit fee is 0.11. A confirmed settlement debits 0.04. Cash before entry is 1,000.00 and independently supplied closing cash is 1,019.75, in invented cash units.

| Component | Calculation | Amount |
| --- | --- | ---: |
| Price P&L | `2 × (110 − 100)` | +20.00 |
| Fees | `−0.10 − 0.11` | −0.21 |
| Settled funding | Signed confirmed cash amount | −0.04 |
| Net P&L | `20.00 − 0.21 − 0.04` | +19.75 |
| Expected closing cash | `1,000.00 + 19.75` | 1,019.75 |
| Unexplained residual | `observed cash − expected cash` | 0.00 |

Fees are debits and settled funding is signed cash. Funding receipts are positive; payments are negative. The model consumes explicit settled cash amounts and never treats historical settled funding as a predicted rate available before settlement. Missing coverage raises an error instead of inventing zero funding. A deliberately perturbed closing-cash control leaves a visible residual of −0.01.

The holding interval for attributed settlements is `(entry time, close time]`. This is an explicit synthetic convention, not a claim about any venue's precise settlement or execution ordering. Boundary ambiguity would need independently timestamped fills and settlements before applying this to external data.

## Reproduce

From the demo repository root, using the documented Python environment:

```text
python tests/run.py
python src/hl_demo/reconciliation.py --fixture fixtures/reconciliation.json
```

The fixture is read-only; the command prints deterministic JSON and makes no external requests. The report generator can import `run_case_study` for exactly the same evidence. All dependencies used by this module and its tests are in Python's standard library.

## Meaning and limits

The example answers the implementation question positively when all supplied controls pass: the tested failures do not fabricate closes, and the synthetic cash components reconcile exactly. This is evidence about these synthetic cases only. Positive invented P&L was chosen to make arithmetic easy and provides no evidence of profitability, execution quality or model calibration. There is no statistical market sample, confidence interval or performance estimate.

The model covers one linear-perpetual position and one full entry/exit, with exact contract quantities. It deliberately refuses to finalize partial or ambiguous fills, retaining the **last reconciled** local state while blocking new risk. That retained state can differ from current exposure; it is evidence for investigation, not an authoritative exchange position. All unresolved open orders block risk regardless of side or reduce-only flags. The exercise does not automatically cancel orders, flatten positions, change a journal or resume trading.

No margin flows, transfers, rebates, conversions, liquidation, fee tiers, contract multipliers, multiple venues, persistent recovery or idempotent external event ingestion are modeled. The cash bridge applies to a fully closed position and excludes unrealized P&L. Complete settlement coverage is asserted by the fixture; a real implementation would need independent coverage reconciliation.

Prioritized follow-up work is to add partial-fill journal accounting and event deduplication, then timestamped independent position/order/cash snapshots with a recovery state machine, and only then larger fault-injection tests covering reordered or duplicated events and interrupted persistence. These are engineering proposals; no live integration is included in this release.
