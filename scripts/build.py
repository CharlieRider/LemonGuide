#!/usr/bin/env python3
"""
Single build entrypoint for the published Lisbon Lemon Guide.

Runs the publish pipeline in the correct, dependency-respecting order:

    1. sync_from_raw     - pull latest content from the raw Obsidian workspace
    2. generate_index    - build data/studies_index.json from study frontmatter
    3. generate_nav      - build guide/studies index pages from that data
    4. apply_frontmatter - ensure every page has front matter so minima themes it
    5. linkify_claims    - turn [CLAIM_ID] into anchored links + table anchors
    6. lint_claims       - validate every reference resolves (the gate)

The pipeline fails fast: if lint reports errors, build exits non-zero so it
can be used in CI and as a pre-commit check. Run this before every commit.

Usage:
    python scripts/build.py            # full build, fails on lint errors
    python scripts/build.py --check    # report sync drift only, write nothing
    python scripts/build.py --skip-sync
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable


def run(name: str, *args: str) -> int:
    script = SCRIPTS / name
    print(f"\n{'=' * 60}\n>>> {name} {' '.join(args)}\n{'=' * 60}")
    proc = subprocess.run([PY, str(script), *args])
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Only check sync drift; write nothing, run no other steps.")
    parser.add_argument("--skip-sync", action="store_true",
                        help="Skip the raw->docs sync step (use current docs/).")
    args = parser.parse_args()

    if args.check:
        return run("sync_from_raw.py", "--check")

    if not args.skip_sync:
        if run("sync_from_raw.py") != 0:
            print("\nBUILD FAILED: sync_from_raw reported a problem.")
            return 1

    for step in ("generate_index.py", "generate_nav.py",
                 "apply_frontmatter.py", "linkify_claims.py"):
        if run(step) != 0:
            print(f"\nBUILD FAILED at {step}.")
            return 1

    # The gate (single canonical integrity checker, run against RAW source of
    # truth). Non-zero = unresolved claim refs, missing sources, bad cross-refs,
    # or a new (F+) claim without a verbatim quote receipt found in its source.
    lint_rc = run("lint_report.py")
    if lint_rc != 0:
        print("\nBUILD FAILED: integrity lint found errors (see above and "
              "_lint_report.md). Fix them in the RAW workspace, then rebuild.")
        return lint_rc

    print("\nBUILD OK: content synced, indexed, linkified, and lint-clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
