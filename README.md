# Published Lemon Guide

This repository contains the Lisbon lemon guide and evidence database prepared for publication.

## Contents

- `docs/` — static markdown site content.
- `docs/guide/sections/` — guide section markdown files.
- `docs/claim_table.md` — evidence claims table.
- `docs/source_catalog.md` — source catalog and credibility tiers.
- `docs/soil_claims.md` — normalized soil evidence.
- `docs/progress.md` — current progress notes.
- `docs/studies/` — source study note markdown files.
- `data/` — generated JSON/YAML indexes for search and site navigation.
- `scripts/` — content-generation scripts.

## Publishing strategy

This repo is intended to publish as a GitHub Pages site from the `main` branch using the `docs/` folder.

## Set up

```powershell
cd published_lemon_guide
git add .
git commit -m "Initial structure and content"
```

## Local preview

You can preview the site locally by opening `docs/index.md` in a markdown viewer, or by adding a static site generator such as MkDocs later.

## Recommended next steps

1. Create a GitHub repository named `published_lemon_guide`.
2. Add a remote: `git remote add origin <url>`.
3. Push `main`: `git push -u origin main`.
4. Enable GitHub Pages on the repo using `main` / `docs` as source.

## Notes

- This repo keeps published material separated from the raw workspace.
- It currently includes the lemon guide and study note corpus only.
