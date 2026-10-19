# Reproduce the included checks

Use CPython 3.12.14. No package installation, credentials or network is required:

```text
python demo.py
python tests/run.py
python demo.py --check
python tools/verify_export.py
python tools/verify_release.py
```

The report and all 77 tests use invented fixtures. Tests check timing rules and accounting under supplied inputs; they do not certify market-data receipt times or profitability. The recorded estimates in RETROSPECTIVE_FINDING.md cannot be recomputed here because their data is withheld.

Optional collection/replay commands and bounds are in FORWARD_PROTOCOL.md. They use the network only when explicitly invoked, write to a new ignored work/ directory and do not enter the offline report or CI. Collected data is not automatically redistributable under the code license.

`python tools/verify_release.py --history` requires a Git checkout and checks all reachable refs. ZIP archives contain no Git history; use the default check there. Inspect any report drift before regeneration and review file changes before updating the manifest with `--write`. CI never regenerates expected artifacts automatically.
