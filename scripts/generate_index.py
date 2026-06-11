#!/usr/bin/env python3
"""Generate a simple JSON index of study metadata for the published lemon guide."""

from pathlib import Path
import re
import json

ROOT = Path(__file__).parent.parent
STUDIES_DIR = ROOT / "docs" / "studies"
OUT_PATH = ROOT / "data" / "studies_index.json"

FRONTMATTER_RE = re.compile(r"^---\s*$(.*?)^---\s*$", re.S | re.M)
KV_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.search(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kv = KV_RE.match(line)
        if kv:
            key = kv.group(1).strip()
            val = kv.group(2).strip().strip('"').strip("'")
            fm[key] = val
    return fm


def main() -> None:
    entries = []
    for path in sorted(STUDIES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        entry = {
            "filename": path.name,
            "title": fm.get("title", ""),
            "year": fm.get("year", ""),
            "source": fm.get("source", ""),
            "url": fm.get("url", ""),
            "pdf_url": fm.get("pdf_url", ""),
            "topic": fm.get("topic", ""),
            "authors": fm.get("authors", ""),
            "tags": fm.get("tags", ""),
        }
        entries.append(entry)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(entries)} study records to {OUT_PATH}")


if __name__ == "__main__":
    main()
