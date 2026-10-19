# Synthetic implementation and reconciliation report

**Every input in this report is invented. It does not reproduce or validate the private empirical market study.**

The private retrospective finding is recorded separately in [RETROSPECTIVE_FINDING.md](../docs/RETROSPECTIVE_FINDING.md). Its market data and full empirical report are not distributed here.

| Synthetic horizon (min) | Scored examples | Mean long markout (bps) | Less two-sided fee budget (bps) | Matched examples | Paired difference (bps) |
|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 0.000 | -9.000 | 1 | 50.000 |
| 60 | 2 | 0.000 | -9.000 | 1 | 50.000 |

Hand check: two event paths move 100→101 and 100→99; their mean long markout is zero. The prior-day invented control moves 100→100.5. These values were chosen for arithmetic, not fitted to market data.

## Synthetic reconciliation

Failed/rejected exits retain the last reconciled position and block new risk. A confirmed full close permits a price/fee/funding cash bridge. Positive invented cash outcomes are not market performance.

| Invented case | State result | New risk blocked | Close records |
|---|---|---|---:|
| failed_exit | exit_unresolved | True | 0 |
| rejected_exit | exit_unresolved | True | 0 |
| acknowledged_exit_is_not_a_fill | exit_unresolved | True | 0 |
| rejected_entry_with_price_metadata | entry_rejected | False | 0 |
| exchange_local_drift | reconciliation_block | True | 0 |
| confirmed_close_cash_bridge | close_confirmed | False | 1 |

No synthetic result measures market profitability. No empirical confidence interval, holdout performance or completed TWAP/funding result is supplied.

## Reproduce

`python demo.py` regenerates this synthetic report; `python demo.py --check` checks exact agreement.

Input SHA-256:

- `fixtures/synthetic_panel.json`: `344e216d084474af159ccccf2a0a57ac96b11a186a5be31e81f46b46ac3a8837`
- `config/study.json`: `30217221ae051e46079f5b6eab2e8b34ab7f1862dd4ddb64eace410f437477bc`
- `fixtures/reconciliation.json`: `fad8614aece28e58c61463678a33d0517a76f3554d7686ae5e4fe7ec5d2283cd`
