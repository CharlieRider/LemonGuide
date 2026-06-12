#!/usr/bin/env python3
"""Ensure every docs page has Jekyll front matter.

Jekyll only wraps a page in the site layout (the minima theme) if the file
begins with YAML front matter. Content synced from the raw workspace (guide
sections, claim table, catalogs) has none, so without this step those pages
render as bare, unstyled HTML.

This injects a minimal `---\nlayout: page\n---` block at the top of any
docs/**/*.md that doesn't already start with front matter. Study notes that
already carry front matter are left untouched (the layout is supplied by the
`defaults` rule in docs/_config.yml). Idempotent.
"""

from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
BLOCK = "---\nlayout: page\n---\n\n"


def main() -> int:
    injected = 0
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.lstrip().startswith("---"):
            continue  # already has front matter
        path.write_text(BLOCK + text, encoding="utf-8")
        injected += 1
    print(f"apply_frontmatter: injected layout into {injected} page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
