"""Explicit file allowlist, integrity and privacy checks; no third-party packages."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests/export.json"


def files():
    return {
        p.relative_to(ROOT).as_posix(): p
        for p in ROOT.rglob("*")
        if p.is_file()
        and not any(
            x in p.relative_to(ROOT).parts
            for x in (".git", ".venv", "__pycache__", "work", ".ruff_cache")
        )
        and p != MANIFEST
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    observed = files()
    findings = []
    patterns = [
        r"0x[0-9a-fA-F]{40}\b",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"[A-Za-z]:\\Users\\",
        r"gh[pousr]_[A-Za-z0-9]{30,}",
    ]
    for name, p in observed.items():
        txt = p.read_text(encoding="utf-8")
        if any(re.search(pattern, txt) for pattern in patterns):
            findings.append(name)
    if findings:
        raise SystemExit(
            "Privacy/token pattern matched in files (values withheld): "
            + ", ".join(findings)
        )
    entries = {
        n: {
            "sha256": sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
            "role": n.split("/")[0] if "/" in n else "repository_metadata",
        }
        for n, p in sorted(observed.items())
    }
    if args.write:
        MANIFEST.parent.mkdir(exist_ok=True)
        MANIFEST.write_text(
            json.dumps(
                {"schema_version": 1, "files": entries}, sort_keys=True, indent=2
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    else:
        expected = json.loads(MANIFEST.read_text())["files"]
        if expected != entries:
            raise SystemExit(
                "Export differs from the frozen allowlist or hashes. Review changes before regenerating manifest."
            )
    print(
        f"Export integrity and privacy checks passed: {len(entries)} allowlisted files."
    )


if __name__ == "__main__":
    main()
