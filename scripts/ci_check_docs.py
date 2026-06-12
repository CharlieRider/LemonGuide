#!/usr/bin/env python3
"""
Advisory referential check for the PUBLISHED docs tree (CI-safe).

The canonical linter (lint_report.py) runs against the raw Obsidian workspace,
which is not present in the published GitHub repo — so it cannot run in CI.
This checker validates the referential subset (the part that *is* knowable from
the published tree alone):

  * every [ClaimID] cited in docs/guide/sections/*.md resolves to a row in
    docs/claim_table.md, and
  * every claim row's Source File exists in docs/studies/.

It reuses lint_report.py's parsers so there is one definition of how the claim
table and references are read. It is advisory: it prints a summary and exits
non-zero on broken refs, but the CI workflow runs it with continue-on-error so
it never blocks a deploy.

Usage:
    python scripts/ci_check_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import lint_report  # reuse the canonical parsers

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
CLAIM_TABLE = DOCS / "claim_table.md"
SECTIONS = DOCS / "guide" / "sections"
STUDIES = DOCS / "studies"


def main() -> int:
    if not CLAIM_TABLE.exists() or not SECTIONS.exists():
        print(f"ci_check_docs: expected published tree under {DOCS} "
              "(claim_table.md + guide/sections/). Nothing to check.")
        return 0

    claims, _ = lint_report.parse_claim_table(CLAIM_TABLE)
    studies = lint_report.available_studies(STUDIES)

    broken: list[tuple[str, str, int]] = []   # (cited_id, section, line)
    for sec in sorted(SECTIONS.glob("*.md")):
        if sec.name in {"index.md", "_index.md"}:
            continue
        for cid, line_no, _window in lint_report.extract_refs(sec):
            if cid not in claims:
                broken.append((cid, sec.name, line_no))

    missing_sources = sorted(
        (cid, info["source"])
        for cid, info in claims.items()
        if info["source"] and info["source"] not in studies
    )

    print("=== ci_check_docs (advisory, published tree) ===")
    print(f"  claims in table: {len(claims)} · study files: {len(studies)}")
    print(f"  broken references: {len(broken)} "
          f"({len({b[0] for b in broken})} unique)")
    print(f"  claim sources missing on disk: {len(missing_sources)}")
    for cid, sec, line_no in broken[:40]:
        print(f"    {sec}:{line_no}  [{cid}] not in claim_table.md")
    for cid, src in missing_sources[:40]:
        print(f"    {cid} -> study '{src}' not found in docs/studies/")

    hard = len(broken) + len(missing_sources)
    print(f"  result: {'CLEAN' if hard == 0 else f'{hard} issue(s) (advisory)'}")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
