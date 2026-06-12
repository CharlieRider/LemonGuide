#!/usr/bin/env python3
"""
Linkify script for claim references in the Lisbon Lemon Guide.

Transforms:
1. [CLAIM_ID] → [CLAIM_ID](#claim-id) in guide sections
2. Handles comma-separated claims: [C001, C002] → [C001](#claim-c001), [C002](#claim-c002)
3. Adds HTML anchors to claim_table.md rows (doesn't break markdown table)
4. Links source files in claim_table.md to study files
"""

import re
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"
GUIDE_DIR = DOCS_DIR / "guide" / "sections"
STUDIES_DIR = DOCS_DIR / "studies"
CLAIM_TABLE = DOCS_DIR / "claim_table.md"

class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def linkify_claims_in_text(text):
    """
    Convert claim references to links in markdown text.
    Handles both single [C001] and comma-separated [C001, C002, C003] formats.
    """
    def replace_claims(match):
        # Get the entire bracketed content
        content = match.group(1)
        
        # Split by comma if present
        if ',' in content:
            # Split and process each claim
            claim_ids = [c.strip() for c in content.split(',')]
            links = [f'[{cid}](#claim-{cid.lower()})' for cid in claim_ids if re.match(r'^[A-Z]\d{3}', cid)]
            return ', '.join(links)
        else:
            # Single claim
            cid = content.strip()
            if re.match(r'^[A-Z]\d{3}', cid):
                return f'[{cid}](#claim-{cid.lower()})'
            return match.group(0)  # Return unchanged if not valid
    
    # Match: [XXXXX] or [XXXXX, XXXXX, ...]
    # The trailing (?!\() makes this idempotent: a claim already followed by a
    # link target — [A018](#claim-a018) — is skipped instead of re-wrapped.
    pattern = r'\[([A-Z]\d{3}(?:\s*,\s*[A-Z]\d{3})*)\](?!\()'
    return re.sub(pattern, replace_claims, text)

def linkify_guide_sections():
    """Convert claim references to markdown links in all guide sections."""
    print(f"\n{Color.BLUE}Step 1: Linkifying guide sections...{Color.RESET}")
    
    if not GUIDE_DIR.exists():
        print(f"  {Color.RED}✗ Guide directory not found{Color.RESET}")
        return 0
    
    files_modified = 0
    for guide_file in sorted(GUIDE_DIR.glob("*.md")):
        try:
            with open(guide_file, 'r', encoding='utf-8') as f:
                original = f.read()
            
            modified = linkify_claims_in_text(original)
            
            if modified != original:
                with open(guide_file, 'w', encoding='utf-8') as f:
                    f.write(modified)
                
                # Count links added
                link_count = len(re.findall(r'#claim-[a-z]\d{3}', modified))
                print(f"  {Color.GREEN}✓{Color.RESET} {guide_file.name}: {link_count} links added")
                files_modified += 1
        except Exception as e:
            print(f"  {Color.RED}✗{Color.RESET} Error processing {guide_file.name}: {e}")
    
    return files_modified

def linkify_claim_table():
    """Add HTML anchors before table rows and linkify source files."""
    print(f"\n{Color.BLUE}Step 2: Linkifying claim table...{Color.RESET}")
    
    try:
        with open(CLAIM_TABLE, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  {Color.RED}✗ Error reading claim table: {e}{Color.RESET}")
        return
    
    # Get available studies
    available_studies = set()
    if STUDIES_DIR.exists():
        for f in STUDIES_DIR.glob("*.md"):
            available_studies.add(f.stem)
    
    lines = content.split('\n')
    modified_lines = []
    in_table = False
    rows_processed = 0
    anchors_added = 0
    links_added = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect table header/separator
        if '| Claim ID | Claim | Category' in line or line.strip().startswith('|---'):
            in_table = True
            modified_lines.append(line)
            i += 1
            continue
        
        # Process table rows
        if in_table and line.strip().startswith('|') and not line.strip().startswith('|---'):
            # Parse the row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove outer empty cells
            
            if len(cells) >= 5:
                claim_id = cells[0]
                
                # Check if it's a valid claim ID
                if re.match(r'^[A-Z]\d{3}', claim_id):
                    anchor = f'<a id="claim-{claim_id.lower()}"></a>'
                    # Idempotent: only add the anchor if the previous emitted
                    # line isn't already this anchor (avoids accumulating
                    # duplicates on repeated runs).
                    if not (modified_lines and modified_lines[-1].strip() == anchor):
                        modified_lines.append(anchor)
                        anchors_added += 1

                    # Process source file cell (index 4). Skip if already a
                    # markdown link from a prior run.
                    source_file = cells[4]
                    if source_file and source_file in available_studies:
                        # Convert to markdown link
                        cells[4] = f'[{source_file}](../studies/{source_file}.md)'
                        links_added += 1
                    
                    # Rebuild row preserving format
                    modified_line = '| ' + ' | '.join(cells) + ' |'
                    modified_lines.append(modified_line)
                    rows_processed += 1
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(line)
        else:
            modified_lines.append(line)
        
        i += 1
    
    # Write modified claim table
    try:
        modified_content = '\n'.join(modified_lines)
        with open(CLAIM_TABLE, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"  {Color.GREEN}✓{Color.RESET} Added {anchors_added} HTML anchors")
        print(f"  {Color.GREEN}✓{Color.RESET} Added {links_added} study file links")
        print(f"  {Color.GREEN}✓{Color.RESET} Processed {rows_processed} claim rows")
    except Exception as e:
        print(f"  {Color.RED}✗{Color.RESET} Error writing claim table: {e}")

def linkify_other_documents():
    """Linkify claims in other markdown documents in docs/ directory."""
    print(f"\n{Color.BLUE}Step 3: Linkifying other documents...{Color.RESET}")
    
    files_modified = 0
    
    for doc_file in DOCS_DIR.glob("*.md"):
        if doc_file.name == "claim_table.md":
            continue
        
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                original = f.read()
            
            modified = linkify_claims_in_text(original)
            
            if modified != original:
                with open(doc_file, 'w', encoding='utf-8') as f:
                    f.write(modified)
                
                link_count = len(re.findall(r'#claim-[a-z]\d{3}', modified))
                print(f"  {Color.GREEN}✓{Color.RESET} {doc_file.name}: {link_count} links added")
                files_modified += 1
        except Exception as e:
            print(f"  {Color.RED}✗{Color.RESET} Error processing {doc_file.name}: {e}")
    
    if files_modified == 0:
        print(f"  {Color.YELLOW}ℹ{Color.RESET} No additional documents to linkify")
    
    return files_modified

def main():
    print(f"\n{Color.BLUE}=== Linkifying Claim References ==={Color.RESET}")
    
    guide_count = linkify_guide_sections()
    linkify_claim_table()
    other_count = linkify_other_documents()
    
    print(f"\n{Color.BLUE}=== Summary ==={Color.RESET}")
    print(f"Guide sections modified: {guide_count}")
    print(f"Other documents modified: {other_count}")
    print(f"\n{Color.GREEN}✓ Linkification complete!{Color.RESET}")
    print(f"\n{Color.YELLOW}Next steps:{Color.RESET}")
    print(f"  1. Verify: git diff docs/ | head -100")
    print(f"  2. Commit: git add docs/ && git commit -m 'Add claim reference hyperlinks and anchors'")
    print(f"  3. Push: git push origin master")

if __name__ == "__main__":
    main()
