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

By default the lint step is **advisory**: it always runs and prints a summary
(and lint_report.py always writes _lint_report.{md,json}), but unresolved
references do not fail the build, so you can regenerate and publish freely.
Pass --strict to turn lint back into a hard gate (used for a clean pre-publish
check). Earlier pipeline steps (sync/index/nav/etc.) always fail fast.

Usage:
    python scripts/build.py            # advisory: logs lint issues, exits 0
    python scripts/build.py --strict   # hard gate: exits non-zero on lint errors
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
    parser.add_argument("--strict", action="store_true",
                        help="Make lint a hard gate: fail the build on lint errors.")
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

    # Integrity check (single canonical checker, run against RAW source of
    # truth). Non-zero = unresolved claim refs, missing sources, bad cross-refs,
    # or a new (F+) claim without a verbatim quote receipt found in its source.
    # lint_report.py always writes _lint_report.{md,json}, so issues are recorded
    # regardless of whether we gate on them.
    lint_rc = run("lint_report.py")
    if lint_rc != 0:
        if args.strict:
            print("\nBUILD FAILED (--strict): integrity lint found errors (see "
                  "above and _lint_report.md). Fix them in the RAW workspace, "
                  "then rebuild.")
            return lint_rc
        print("\nBUILD OK (advisory): content synced, indexed, and linkified. "
              "Integrity lint found unresolved references — logged, not blocking "
              "(see _lint_report.md). Run with --strict to gate on them.")
        return 0

    print("\nBUILD OK: content synced, indexed, linkified, and lint-clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
