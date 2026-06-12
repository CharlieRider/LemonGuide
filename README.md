# Published Lemon Guide

The Lisbon lemon guide and evidence database, prepared for publication as a
GitHub Pages site. Content is **generated from the raw Obsidian workspace** —
do not hand-edit `docs/`; edit the raw sources and run the build.

## Contents

- `docs/` — static markdown site content (published to GitHub Pages).
  - `docs/guide/sections/` — the 19 guide section files.
  - `docs/claim_table.md` — evidence claims table (anchored for deep links).
  - `docs/source_catalog.md` — source catalog and credibility tiers.
  - `docs/soil_claims.md` — normalized soil evidence.
  - `docs/studies/` — source study note markdown files.
  - `docs/_config.yml` — Jekyll config (relative-link rewriting for Pages).
- `data/` — generated JSON index for search/navigation.
- `scripts/` — the publish pipeline (see below).
- `scripts/tooling/` — optional content tooling (PDF fetch, soil normalizer).

## Source of truth

The raw workspace at `../raw/industry reports/` is authoritative:

- `lisbon-lemon-guide/sections/*.md` → `docs/guide/sections/`
- `lisbon-lemon-guide/_claim_table.md` → `docs/claim_table.md` (and the other
  `_`-prefixed catalogs, de-underscored)
- `lisbon-lemon-studies/*.md` → `docs/studies/`

PDFs stay in the raw workspace and out of git; each study note links its
`pdf_url` in `data/studies_index.json`.

## Build

One command runs the whole pipeline (sync → index → nav → linkify → lint):

```powershell
.\build.ps1            # full build; fails if claim linting fails
.\build.ps1 -Check     # report raw->docs drift only, write nothing
```

or directly:

```bash
python scripts/build.py
```

Run the build before every commit. The final lint step is a hard gate: it
exits non-zero if any `[CLAIM_ID]` reference doesn't resolve to the claim
table and a study file. Fix unresolved references in the **raw** workspace,
then rebuild.

## Publishing (GitHub Pages)

This repo publishes from branch **`master`**, folder **`/docs`**:

1. Push `master` to `git@github.com:CharlieRider/LemonGuide.git`.
2. In the repo: **Settings → Pages → Build and deployment**, set
   *Source: Deploy from a branch*, *Branch: `master` / `/docs`*.
3. The `jekyll-relative-links` plugin (configured in `docs/_config.yml`)
   rewrites in-repo `.md` links to `.html` so cross-links and the
   `#claim-…` anchors resolve on the live site.

CI (`.github/workflows/lint-claims.yml`) runs the claim linter on every push
and pull request and now fails the check when references are unresolved.

## Tooling (optional, pre-publish)

`scripts/tooling/` holds content-prep utilities (mirrored from the workspace
`Tooling/` folder):

- `download_missing_pdfs.py <studies-folder>` — bulk PDF fetch sweep for study
  notes. Run the Chromium/captcha pass afterward for sources it can't fetch
  headless.
- `soil_normalizer.py` — normalize soil claims against `soil_rules.yaml`.
- `analyze_studies.py` — corpus/coverage analysis.

Install their deps with `pip install -r requirements.txt` (the core pipeline
itself needs only the Python standard library).

## Claim system

See `docs/CLAIM_SYSTEM_README.md` for the claim-reference format, the
three-layer evidence chain, and the linter's checks.
