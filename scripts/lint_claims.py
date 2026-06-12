#!/usr/bin/env python3
"""
Claim-reference lint gate — compatibility shim.

There is now a single canonical integrity checker, ``lint_report.py``, used by
both the maintenance loops and the build gate so the two can never drift apart.
This file is kept only so existing callers / docs that invoke
``python scripts/lint_claims.py`` still work; it simply delegates to the
canonical checker (which runs against the RAW source of truth and writes
``_lint_report.{md,json}``).

Exit code: 1 on any hard integrity error, else 0.
"""

from __future__ import annotations

import sys

import lint_report

if __name__ == "__main__":
    # Delegate to the canonical linter. All flags (e.g. --raw, --no-historical,
    # --quiet) pass straight through.
    raise SystemExit(lint_report.main())
