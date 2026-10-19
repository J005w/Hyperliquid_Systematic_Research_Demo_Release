# Hyperliquid Systematic Research Demo

A personal research project with one retrospective study, a tested evaluation framework, a separate synthetic reconciliation case and two specified future studies.

**Run:** as-of timing, long/short costs, missing data, overlap, matched-control and report-consistency checks; a synthetic position-reconciliation/cash-attribution case; and offline reconstruction of a forward LVN proxy from separately collected inputs. The included report and all 77 tests need no account, packages or credentials.

**Recorded, not reproduced here:** the retrospective market analysis gave negative sample estimates. Its [recorded finding](docs/RETROSPECTIVE_FINDING.md) explains the question, result and limitations. The market fixture and full empirical result arrays/tables are withheld because affirmative redistribution permission was not established. The invented examples in this checkout are not replacements for empirical evidence.

```text
python demo.py
python tests/run.py
python demo.py --check
python tools/verify_export.py
python tools/verify_release.py
```

Use CPython 3.12.14 with zero third-party Python dependencies. [Synthetic report](reports/RESULTS.md) · [Reconciliation case](docs/RECONCILIATION.md) · [Research design](docs/RESEARCH_DESIGN.md) · [Reproduction](docs/REPRODUCIBILITY.md).

**What I built:** bounded event-study observation selection, consistent signed returns and two-sided notional costs, conservative non-overlap filters, deterministic matched controls, explicit missingness and generated reports. The separate reconciliation case refuses fictitious closes after failed/rejected exits and reconciles exact price, fee and settled-funding cash. This demonstrates careful measurement and accounting; it does not establish profitable trading.

The retrospective LVN analysis uses sparse observations with assumed availability, unreconstructible old feature labels and no untouched holdout. TWAP × LVN continuation and funding forecast/carry are **future studies**, not completed empirical tests. The [forward protocol](docs/FORWARD_PROTOCOL.md) and bounded read-only collector prepare future evidence; a smoke collection validates plumbing only.

MIT covers original code, authored documentation and invented fixtures. Third-party papers, venue documentation and market observations are not relicensed. [Data rights and availability](docs/RIGHTS_REVIEW.md) · [Provenance](docs/PROVENANCE.md) · [Attributed background](docs/BACKGROUND.md) · [AI assistance](AI_ASSISTANCE.md).
