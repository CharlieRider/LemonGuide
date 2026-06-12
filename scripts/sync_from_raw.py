#!/usr/bin/env python3
"""
Sync content from the raw Obsidian workspace into the published docs/ tree.

The raw workspace is the single source of truth. This script copies the guide
sections, the claim table / catalogs / soil evidence, and the study notes into
``docs/``, normalizing the leading-underscore working filenames to their
published names. It is idempotent: re-running it simply re-copies.

Usage:
    python scripts/sync_from_raw.py [--raw-root PATH] [--check]

--check  Report what would change (drift) and exit non-zero if out of date,
         without writing anything. Useful in CI / pre-commit.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

# Default location of the raw Obsidian workspace, relative to this repo.
# repo:  .../Karpathy Method/published_lemon_guide
# raw:   .../Karpathy Method/raw/industry reports/...
DEFAULT_RAW_ROOT = REPO_ROOT.parent / "raw" / "industry reports"

# Single-file mappings: raw relative path -> docs relative path.
FILE_MAP = {
    "lisbon-lemon-guide/_claim_table.md": "claim_table.md",
    "lisbon-lemon-guide/_source_catalog.md": "source_catalog.md",
    "lisbon-lemon-guide/_normalized_soil_claims.md": "soil_claims.md",
    "lisbon-lemon-guide/_progress.md": "progress.md",
    "lisbon-lemon-guide/_appendix_evidence_gaps.md": "evidence_gaps.md",
}

# Directory mappings: (raw dir, docs dir, glob). Every matching file is copied;
# the docs side is treated as a mirror of raw (raw is authoritative).
DIR_MAP = [
    ("lisbon-lemon-guide/sections", "guide/sections", "*.md"),
    ("lisbon-lemon-studies", "studies", "*.md"),
]

# Generated files that live in docs/ but are NOT sourced from raw. The mirror
# logic must not flag or delete these as "orphans".
GENERATED_KEEP = {
    "guide/sections/index.md",
    "studies/index.md",
    "studies/_index.md",
}


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def sync_file(raw_root: Path, raw_rel: str, docs_rel: str, check: bool,
              changes: list[str]) -> None:
    src = raw_root / raw_rel
    dst = DOCS / docs_rel
    if not src.exists():
        changes.append(f"MISSING source: {raw_rel} (expected for {docs_rel})")
        return
    src_text = _read(src)
    if _read(dst) == src_text:
        return
    changes.append(f"UPDATE {docs_rel}  <-  {raw_rel}")
    if not check:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src_text, encoding="utf-8")


def sync_dir(raw_root: Path, raw_rel: str, docs_rel: str, glob: str,
             check: bool, changes: list[str]) -> None:
    src_dir = raw_root / raw_rel
    dst_dir = DOCS / docs_rel
    if not src_dir.exists():
        changes.append(f"MISSING source dir: {raw_rel}")
        return

    src_files = {p.name for p in src_dir.glob(glob)}
    for name in sorted(src_files):
        src = src_dir / name
        dst = dst_dir / name
        src_text = _read(src)
        if _read(dst) == src_text:
            continue
        changes.append(f"UPDATE {docs_rel}/{name}")
        if not check:
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst.write_text(src_text, encoding="utf-8")

    # Report (but never silently delete) docs-only files that raw no longer has.
    if dst_dir.exists():
        for p in dst_dir.glob(glob):
            rel = f"{docs_rel}/{p.name}"
            if p.name not in src_files and rel not in GENERATED_KEEP:
                changes.append(f"ORPHAN (in docs, not in raw): {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT,
                        help="Path to 'raw/industry reports' workspace root.")
    parser.add_argument("--check", action="store_true",
                        help="Report drift and exit non-zero; write nothing.")
    args = parser.parse_args()

    raw_root: Path = args.raw_root
    if not raw_root.exists():
        print(f"ERROR: raw root not found: {raw_root}", file=sys.stderr)
        return 2

    changes: list[str] = []
    for raw_rel, docs_rel in FILE_MAP.items():
        sync_file(raw_root, raw_rel, docs_rel, args.check, changes)
    for raw_rel, docs_rel, glob in DIR_MAP:
        sync_dir(raw_root, raw_rel, docs_rel, glob, args.check, changes)

    orphans = [c for c in changes if c.startswith("ORPHAN")]
    missing = [c for c in changes if c.startswith("MISSING")]
    updates = [c for c in changes if c.startswith("UPDATE")]

    print(f"=== sync_from_raw ({'check' if args.check else 'write'}) ===")
    print(f"raw root: {raw_root}")
    for c in changes:
        print(f"  {c}")
    print(f"  {len(updates)} file(s) {'out of date' if args.check else 'synced'}, "
          f"{len(orphans)} orphan(s), {len(missing)} missing source(s)")

    if args.check and (updates or missing):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
