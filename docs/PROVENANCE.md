# Code and data provenance

This repository contains original code, authored documentation and invented fixtures from a personal research project. No historical market fixture, acquisition output, empirical result arrays/tables, operational logs or account state is included.

Included code covers observation timing, signed notional accounting, horizon denominators, overlap/control selection, synthetic reconciliation and optional bounded public collection/feature reconstruction. Dependencies are Python's standard library only. The reconciliation design builds on the author's separate personal work on execution-state integrity; no live bot, signing SDK or operational configuration is included.

fixtures/synthetic_panel.json was invented from 100→101, 100→99 and 100→100.5 paths on relative artificial days. It was not sampled, perturbed, normalized or fitted from market data. fixtures/reconciliation.json is also entirely invented. reports/results.json and reports/RESULTS.md are generated only from those inputs and config/study.json. The report rejects non-synthetic fixtures. RETROSPECTIVE_FINDING.md is an authored record of the separate historical analysis, whose inputs are not distributed here.

manifests/export.json records exact file hashes, excluding itself. `python tools/verify_export.py` checks file integrity and privacy patterns. `python tools/verify_release.py` checks the synthetic-only data boundary; `--history` additionally checks all reachable Git refs. The CI workflow fetches full history and runs that check. ZIP archives have no Git history and use the default archive check.

MIT applies to original materials included here. External papers and documentation retain their own rights and are linked with attribution. The code license does not grant rights to redistribute separately acquired market observations.
