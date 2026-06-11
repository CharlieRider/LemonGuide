# Claim Reference System Documentation

## Overview

This guide documents the **claim reference and evidence linking system** for the Lisbon Lemon Guide. This system ensures that all quantitative targets, recommendations, and evidence traces back to source studies.

## Architecture

### Three-Layer Evidence Chain

```
Guide Section (e.g., §1)
    ↓
    References claim via [CLAIM_ID](#claim-id)
    ↓
Claim Table (docs/claim_table.md)
    ↓
    Lists source file and evidence strength
    ↓
Study Note (docs/studies/*.md)
    ↓
    Original peer-reviewed or expert source
```

## Claim ID Format

- **Pattern:** `[A-Z]\d{3}` (e.g., `A001`, `B049`, `C030`, `D019`, `E117`)
- **Groups:** IDs are organized A–E by extraction batch (no semantic meaning to the letter grouping)
- **Total:** 693 claims across all categories
- **References:** 279 claim references across guide sections

## Using Claims in Markdown

### Single Claim Reference

```markdown
Target root temperature is optimum 26°C [A018](#claim-a018).
```

**Rendered as:** Target root temperature is optimum 26°C [A018](#claim-a018).

### Comma-Separated Claims

```markdown
Lisbon is most vigorous lemon [D023](#claim-d023), [E026](#claim-e026), and most resistant.
```

**Rendered as:** Lisbon is most vigorous lemon [D023](#claim-d023), [E026](#claim-e026), and most resistant.

### In Markdown Tables

```markdown
| Strain | Claim | Evidence |
|--------|-------|----------|
| Frost nucellar (CRC 3176) | [D019](#claim-d019) | Strong |
| Yen Ben (CRC 4067) | [D020](#claim-d020) | Strong |
```

## Claim Table Structure

File: `docs/claim_table.md`

**Columns:**
1. **Claim ID** — unique identifier (A001–E695+)
2. **Claim** — the assertion or quantitative target
3. **Category** — topical categorization (1–25)
4. **Numeric Target** — specific value or range if applicable
5. **Source File** — filename of study note without `.md` extension
6. **Evidence Strength** — Strong | Moderate | Weak | Extrapolated
7. **Applicability** — citrus general | Citrus limon | container citrus | other
8. **Citation Detail** — author, year, publication, and access detail
9. **Notes** — context or caveats

**Example Row:**

| A018 | Optimum root-growth soil temperature; most active growth range | 23 Heat/wind/cold protection | optimum ~26°C (79°F); 25–30°C (77–86°F) | [1991_calag_soil-temperature-citrus](../studies/1991_calag_soil-temperature-citrus.md) | Strong | citrus general | Calif. Agriculture 1991, 45:13 | Core target numbers |

## Tools

### Linting Tool: `scripts/lint_claims.py`

Validates all claim references and reports issues.

**Usage:**
```bash
python scripts/lint_claims.py
```

**Checks:**
- ✓ All referenced claims exist in claim_table.md
- ✓ All source files in claim table point to valid study notes
- ✓ Reports orphaned claims (defined but unreferenced)
- ⚠ Reports missing study files (for data quality auditing)

**Output:**
```
=== Lisbon Lemon Guide: Claim Reference Lint ===

Step 1: Parsing claim table...
  Found 693 claim IDs in table

Step 2: Scanning available studies...
  Found 167 study files

Step 3: Scanning guide sections for claim references...
  Found 250 unique claim IDs referenced 279 times

============================================================
VALIDATION RESULTS
============================================================

4a. Claims referenced but not in table:
  ✗ [C329] referenced in: 07_canopy_pruning.md
  ✗ [D489] referenced in: 06_container_media_topdress.md
  ...

4b. Study file references in claim table:
  ✓ All claim table source files exist

4c. Claim table entries not referenced in guide:
  ⚠ [A002] defined but not used
  ... and 441 more

============================================================
SUMMARY
============================================================
Total claims in table: 693
Total unique references: 250
Total reference instances: 279
Errors: 8
Warnings: 1

✗ Linting failed with 8 error(s)
```

### Linkification Tool: `scripts/linkify_claims.py`

Automatically transforms claim references into markdown links and adds anchors.

**Usage:**
```bash
python scripts/linkify_claims.py
```

**Actions:**
1. Converts `[CLAIM_ID]` to markdown link `[CLAIM_ID](#claim-id)` in guide sections
2. Handles comma-separated claims: `[C001, C002]` → `[C001](#claim-c001), [C002](#claim-c002)`
3. Adds HTML anchors before each claim table row for deep linking
4. Linkifies source file references: `1985_cfcs_...` → `[1985_cfcs_...](../studies/1985_cfcs_....md)`

**Output:**
```
=== Linkifying Claim References ===

Step 1: Linkifying guide sections...
  ✓ 01_variety_profile.md: 46 links added
  ✓ 02_rootstock_tree_selection.md: 68 links added
  ...

Step 2: Linkifying claim table...
  ✓ Added 693 HTML anchors
  ✓ Added 693 study file links
  ✓ Processed 693 claim rows

=== Summary ===
Guide sections modified: 14
```

## Categories Reference

The claim table uses 25 categories:

| # | Category | Examples |
|---|----------|----------|
| 1 | Variety traits | Size, flavor, hardiness |
| 2 | Rootstock/dwarfing | Vigor, size reduction |
| 3 | Container size | Pot diameter, depth targets |
| 4 | Media physical properties | Porosity, drainage, particle size |
| 5 | Drainage/perched water | Container capacity, air space |
| 6 | pH targets | Optimal range, adjustment |
| 7 | EC/salinity | Salt concentration, leaching |
| 8 | Nitrogen | N rates, timing, ratios |
| 9 | Potassium | K targets, balance |
| 10 | Ca/Mg | Calcium, magnesium deficiency |
| 11 | Micronutrients | Fe, Zn, Mn, B, Cu chelates |
| 12 | Fertilizer timing | Application schedule |
| 13 | Irrigation timing | Watering frequency, dry-down |
| 14 | Leaching/salt mgmt | Salt removal, LF targets |
| 15 | Transplanting | Repotting intervals, rootboundness |
| 16 | Pruning | Structure, height, thinning |
| 17 | Staking/support | Trellis, ties, wind protection |
| 18 | Flowering/pollination | Bloom timing, fruit set |
| 19 | Fruit maturity/harvest | Color break, TSS, acidity |
| 20 | Pests | Identification, thresholds |
| 21 | Diseases | Symptoms, management |
| 22 | Physiological disorders | Chlorosis, drop, sunburn |
| 23 | Heat/wind/cold protection | Temperature thresholds, shading |
| 24 | Container-specific risks | Pot degradation, waterlogging |
| 25 | Common grower errors | Mistakes to avoid |

## Workflow

### Adding a New Claim

1. **Add to Claim Table** (`docs/claim_table.md`):
   - Generate a new Claim ID (e.g., `E696` if E is the latest batch)
   - Fill in all columns with the evidence
   - Ensure Source File maps to an existing study file

2. **Reference in Guide Sections**:
   - Use format `[CLAIMID](#claim-id)` inline
   - Example: `Recommended soil pH is 6.0–7.0 [A040](#claim-a040).`

3. **Verify**:
   ```bash
   python scripts/lint_claims.py  # Should show no errors for this claim
   ```

### Fixing Broken Links

1. **Run linter to identify issues**:
   ```bash
   python scripts/lint_claims.py
   ```

2. **Repair missing claims**: Either remove the reference or add to claim table

3. **Repair missing studies**: Download/add the study file or correct the filename

4. **Re-run linter**:
   ```bash
   python scripts/lint_claims.py  # Verify fix
   ```

### Automated CI/CD

GitHub Actions workflow (`.github/workflows/lint-claims.yml`) runs on every push and PR:

- **Trigger:** Any changes to `docs/**` or `scripts/lint_claims.py`
- **Action:** Runs `python scripts/lint_claims.py`
- **Failure:** Comments on PR with error message
- **Success:** Silent (no feedback needed)

## Evidence Strength Levels

- **Strong** — University extension, peer-reviewed, or government agricultural source with direct experimental support for Lisbon lemon
- **Moderate** — Commercial/nursery production guide; repeated across multiple credible sources; or strong evidence for similar citrus cultivars
- **Weak** — Consumer horticulture sources; indirect inference; limited specificity to Lisbon or containers
- **Extrapolated** — Supported by broader citrus or container-crop science, but not directly tested on Lisbon

## Study Note Naming Convention

Files in `docs/studies/` follow the pattern:
```
YEAR_SOURCE_SLUG.md
```

**Examples:**
- `1985_cfcs_supraoptimal-root-temperature-citrus.md`
- `2014_ifas_hs1208_chelate-selection-by-ph.md`
- `2022_frontiers_advances-in-citrus-flowering-review.md`
- `2023_fourwinds_flying-dragon-dwarfing-rootstock.md`

**Components:**
- `YEAR` — Publication year (4 digits)
- `SOURCE` — Publisher/organization abbreviation (e.g., CFCS, IFAS, UC, TSU, Frontiers)
- `SLUG` — Hyphenated title slug (lowercase, no special chars)

## Common Issues & Solutions

### Issue: Linter reports "Missing claim C329"

**Cause:** Claim is referenced in guide but not in claim_table.md

**Solution:** Either:
1. Add the claim to `docs/claim_table.md`, or
2. Remove/correct the reference in the guide section

### Issue: Linter reports "Study file not found for B065"

**Cause:** Claim table references a study file that doesn't exist

**Solution:** Either:
1. Add the missing study file to `docs/studies/`, or
2. Update the source file name in claim_table.md

### Issue: Links aren't working on GitHub Pages

**Cause:** Anchor format incorrect or claim table not properly formatted

**Solution:** Re-run linkification script:
```bash
git checkout docs/  # Revert changes
python scripts/linkify_claims.py
git diff docs/ | less  # Verify changes
git add docs/ && git commit -m "Re-linkify claims"
```

## Performance Notes

- **Linting:** ~0.5 seconds (scans 14 guide files + claim table + 167 study files)
- **Linkification:** ~0.3 seconds (regex transformations on 14 guide files + claim table)
- **Claim table size:** ~700 KB with 693 rows + anchors + links

## Future Enhancements

- [ ] JSON schema validation for claim table structure
- [ ] Automated claim ID collision detection
- [ ] Study file coverageanalysis (identify unreferenced study files)
- [ ] Claim usage heatmap (visualization of which claims are most cited)
- [ ] Bulk linkification in markdown tables (current: manual or regex-based)
- [ ] Interactive claim explorer (web UI to search and filter claims)
- [ ] Export claim lineage as RDF/knowledge graph

## Contributing

When adding content to the guide:

1. **Use claim IDs liberally** — every quantitative target should trace to a claim
2. **Run linting before committing** — `python scripts/lint_claims.py`
3. **Link studies in claim table** — source filenames enable deep navigation
4. **Maintain consistency** — use `[CLAIMID](#claim-id)` format uniformly

For questions or bug reports, open an issue in the repository.
