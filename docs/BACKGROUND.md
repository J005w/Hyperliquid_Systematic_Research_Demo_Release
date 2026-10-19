# Attributed research background

Background motivates the questions; it is separate from the demonstration's original observations. References were checked on 2026-10-18. Papers are third-party empirical work, and venue documentation describes mechanics that can change.

## Market transparency and TWAP

Davide Barone and Fabrizio Lillo, *Trading in the Sunshine or in the Shade: Market Impact and Adverse Selection on Hyperliquid* (2026), [arXiv:2606.15715](https://arxiv.org/abs/2606.15715), compare visible native TWAP executions with reconstructed hidden metaorders. They report lower impact for visible executions and liquidity supplied on the absorbing side. This motivates a controlled TWAP study while cautioning against assuming that announced direction guarantees continuation. Their data, identification and results have not been replicated in this demonstration.

The venue's [order-type documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types) explains that native TWAP suborders may not fully fill or catch up to the parent target. A parent schedule is therefore insufficient evidence of an executed slice.

The original source's H011 proposes an additional LVN interaction. That interaction is an original hypothesis, not a conclusion of the Barone–Lillo paper.

## Persistent identity and adverse selection

Daojing Zhai, *Public Trader Identity: Adverse Selection and Return Predictability* (2026), [arXiv:2608.04373v3](https://arxiv.org/abs/2608.04373v3), studies persistent pseudonymous identity and incremental short-horizon price information. It provides a named primary reference for the source's wallet-toxicity discussion. This demonstration does not reproduce its data reconstruction, forecast metrics or wallet classification. Wallet identifiers are unnecessary for the selected release questions and are excluded.

Identity-aware quoting, rejected-order imbalance and subsecond lead-lag remain future research requiring certified event clocks and suitable order-book/order-status data. The source's numerical literature summaries must not be presented as the author's own results.

## Funding information and costs

The official [funding description](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) distinguishes the premium-based calculation from payments at hourly settlement and uses oracle price to value the payment. This motivates separating a forecast observed before a target settlement from its realized rate.

The official [perpetuals info API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals) documents current asset contexts, historical funding and predicted funding as separate requests. Querying history later cannot prove which prediction a researcher had before settlement. The retrospective context-funding field lacks certified prediction-availability lineage.

The official [fee schedule](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) lists a base perpetual taker rate of 0.045% and maker rate of 0.015%, with tier, staking and market-specific modifiers. The demonstration freezes a two-sided taker-fee scenario for comparability; it does not infer an actual account's fees or maker fills. Documentation and account schedules should be rechecked before any new study.

## Data-quality and negative-result context

10d Research's [*Why Liquidation and OI Signals Don't Work: The Data Is Broken*](https://www.10d.io/research/exchange-data-quality.html) (2026-02-13) describes its own unsuccessful liquidation/open-interest signal searches and small-sample failures. This is an industry research report with its own methodology, not an independently replicated finding here and not a universal impossibility result.

The source negative-results registry mixes third-party findings, documented fee facts and untested economic inferences. This release preserves their role as background and future research cautions while withdrawing any suggestion that all were locally tested.

## What the local evidence adds

The personal project includes a private re-analysis of a short recorded panel. This repository reproduces only synthetic implementation/reconciliation checks; it does not distribute the empirical data or claim empirical reproduction. Candle-bin profiles are labelled proxies. Missing TWAP directions/fills and missing funding prediction/settlement lineage are reported as identification failures. Synthetic correctness examples establish neither the empirical literature's results nor market profitability.
