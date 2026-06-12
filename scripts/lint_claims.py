#!/usr/bin/env python3
"""
Lint script for claim references in the Lisbon Lemon Guide.

Validates:
1. All [CLAIM_ID] references in guide sections exist in claim_table.md
2. All claim IDs in claim_table.md have corresponding study files
3. Study file mappings point to valid .md files in docs/studies/
4. No orphaned claim IDs in the table
"""

import re
import os
import sys
from pathlib import Path
from collections import defaultdict

# Ensure UTF-8 output so the ✓/✗/⚠ glyphs don't crash on Windows cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Paths
REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"
GUIDE_DIR = DOCS_DIR / "guide" / "sections"
STUDIES_DIR = DOCS_DIR / "studies"
CLAIM_TABLE = DOCS_DIR / "claim_table.md"

# Color output
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def extract_claims_from_file(filepath):
    """Extract all [CLAIM_ID] references from a markdown file."""
    claims = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract every A001-style id inside any [...] bracket, including
            # multi-id cites like "[B055, A062]" and annotated ones like
            # "[A013, *extrapolated*]". The old single-id pattern
            # (\[([A-Z]\d{3})\]) silently skipped those and undercounted broken
            # refs. See scripts/lint_report.py for the richer, raw-side linter.
            for bracket in re.findall(r'\[([^\[\]]+)\]', content):
                claims.update(re.findall(r'\b([A-Z]\d{3})\b', bracket))
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    return claims

def extract_claim_table_rows():
    """Parse claim table and extract all claim IDs and their source files."""
    claims_info = {}  # {claim_id: source_file}
    
    try:
        with open(CLAIM_TABLE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"{Color.RED}✗ Error reading claim table: {e}{Color.RESET}")
        return claims_info
    
    in_table = False
    for line in lines:
        # Skip header separators
        if line.strip().startswith('|---'):
            in_table = True
            continue
        
        # Parse table rows
        if in_table and line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')[1:-1]]  # Skip first and last empty cells
            if len(parts) >= 5:
                claim_id = parts[0].strip()
                source_file = parts[4].strip()  # Column 5 = Source File

                # After linkify, the source cell is a markdown link
                # `[name](../studies/name.md)`. Unwrap it back to the bare
                # study stem so the existence check still works.
                link_match = re.match(r'^\[([^\]]+)\]\([^)]+\)$', source_file)
                if link_match:
                    source_file = link_match.group(1).strip()

                # Filter for valid claim IDs (A001 format)
                if re.match(r'^[A-Z]\d{3}', claim_id):
                    claims_info[claim_id] = source_file
    
    return claims_info

def get_available_studies():
    """Get set of available study files (without .md extension)."""
    studies = set()
    if STUDIES_DIR.exists():
        for f in STUDIES_DIR.glob("*.md"):
            # Remove .md extension
            studies.add(f.stem)
    return studies

def lint_all_claims():
    """Run all linting checks and return report."""
    print(f"\n{Color.BLUE}=== Lisbon Lemon Guide: Claim Reference Lint ==={Color.RESET}\n")
    
    # Step 1: Parse claim table
    print("Step 1: Parsing claim table...")
    claim_table_entries = extract_claim_table_rows()
    print(f"  Found {len(claim_table_entries)} claim IDs in table")
    
    # Step 2: Get available studies
    print("\nStep 2: Scanning available studies...")
    available_studies = get_available_studies()
    print(f"  Found {len(available_studies)} study files")
    
    # Step 3: Scan guide sections for references
    print("\nStep 3: Scanning guide sections for claim references...")
    all_referenced_claims = defaultdict(list)
    
    if GUIDE_DIR.exists():
        for guide_file in sorted(GUIDE_DIR.glob("*.md")):
            claims_in_file = extract_claims_from_file(guide_file)
            for claim_id in claims_in_file:
                all_referenced_claims[claim_id].append(guide_file.name)
    
    # Also check other sections
    for other_file in DOCS_DIR.glob("*.md"):
        if other_file.name != "claim_table.md":
            claims_in_file = extract_claims_from_file(other_file)
            for claim_id in claims_in_file:
                all_referenced_claims[claim_id].append(other_file.name)
    
    total_references = sum(len(files) for files in all_referenced_claims.values())
    print(f"  Found {len(all_referenced_claims)} unique claim IDs referenced {total_references} times")
    
    # Step 4: Validation
    print("\n" + "="*60)
    print(f"{Color.BLUE}VALIDATION RESULTS{Color.RESET}")
    print("="*60)
    
    errors = []
    warnings = []
    
    # Check 4a: Missing claims (referenced but not in table)
    print(f"\n{Color.BLUE}4a. Claims referenced but not in table:{Color.RESET}")
    missing_claims = set(all_referenced_claims.keys()) - set(claim_table_entries.keys())
    if missing_claims:
        for claim_id in sorted(missing_claims):
            msg = f"  {Color.RED}✗{Color.RESET} [{claim_id}] referenced in: {', '.join(all_referenced_claims[claim_id])}"
            print(msg)
            errors.append(f"Missing claim {claim_id}")
    else:
        print(f"  {Color.GREEN}✓ All referenced claims exist in table{Color.RESET}")
    
    # Check 4b: Source file validation
    print(f"\n{Color.BLUE}4b. Study file references in claim table:{Color.RESET}")
    missing_studies = []
    for claim_id, source_file in sorted(claim_table_entries.items()):
        if source_file and source_file not in available_studies:
            msg = f"  {Color.RED}✗{Color.RESET} [{claim_id}] → '{source_file}' not found"
            print(msg)
            missing_studies.append((claim_id, source_file))
            errors.append(f"Study file not found for {claim_id}: {source_file}")
    
    if not missing_studies:
        print(f"  {Color.GREEN}✓ All claim table source files exist{Color.RESET}")
    
    # Check 4c: Unused claims
    print(f"\n{Color.BLUE}4c. Claim table entries not referenced in guide:{Color.RESET}")
    unused_claims = set(claim_table_entries.keys()) - set(all_referenced_claims.keys())
    if unused_claims:
        for claim_id in sorted(unused_claims)[:10]:  # Show first 10
            print(f"  {Color.YELLOW}⚠{Color.RESET} [{claim_id}] defined but not used")
        if len(unused_claims) > 10:
            print(f"  {Color.YELLOW}⚠{Color.RESET} ... and {len(unused_claims) - 10} more")
        warnings.append(f"{len(unused_claims)} unused claims in table")
    else:
        print(f"  {Color.GREEN}✓ All claims in table are referenced{Color.RESET}")
    
    # Summary
    print("\n" + "="*60)
    print(f"{Color.BLUE}SUMMARY{Color.RESET}")
    print("="*60)
    print(f"Total claims in table: {len(claim_table_entries)}")
    print(f"Total unique references: {len(all_referenced_claims)}")
    print(f"Total reference instances: {total_references}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    
    if errors:
        print(f"\n{Color.RED}✗ Linting failed with {len(errors)} error(s){Color.RESET}")
        for err in errors:
            print(f"  - {err}")
    elif warnings:
        print(f"\n{Color.YELLOW}⚠ Linting passed with {len(warnings)} warning(s){Color.RESET}")
        for warn in warnings:
            print(f"  - {warn}")
    else:
        print(f"\n{Color.GREEN}✓ All linting checks passed!{Color.RESET}")
    
    return {
        'claim_table_entries': claim_table_entries,
        'referenced_claims': all_referenced_claims,
        'available_studies': available_studies,
        'errors': errors,
        'warnings': warnings,
    }

if __name__ == "__main__":
    result = lint_all_claims()
    sys.exit(1 if result["errors"] else 0)
