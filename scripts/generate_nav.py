#!/usr/bin/env python3
"""Generate navigation index pages for the published lemon guide."""

from pathlib import Path
import json
import re

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
GUIDE_SECTIONS = DOCS / "guide" / "sections"
STUDIES_DIR = DOCS / "studies"
STUDIES_INDEX = ROOT / "data" / "studies_index.json"

HEADING_RE = re.compile(r"^#+\s*(.*)")


def extract_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        m = HEADING_RE.match(line)
        if m:
            return m.group(1).strip()
    return path.stem


def write_guide_index() -> None:
    lines = ["# Guide Sections", "", "The Lisbon lemon guide sections are below.", "", ""]
    for path in sorted(GUIDE_SECTIONS.glob("*.md")):
        title = extract_title(path)
        rel = path.relative_to(DOCS).as_posix()
        lines.append(f"- [{title}]({rel})")
    lines.append("")
    (DOCS / "guide" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def write_studies_index() -> None:
    records = []
    if STUDIES_INDEX.exists():
        records = json.loads(STUDIES_INDEX.read_text(encoding="utf-8"))
    else:
        for path in sorted(STUDIES_DIR.glob("*.md")):
            records.append({
                "filename": path.name,
                "title": extract_title(path),
                "url": path.name,
            })

    lines = ["# Study Notes", "", "The source study notes are below.", "", ""]
    for rec in sorted(records, key=lambda r: r.get("filename", "")):
        filename = rec.get("filename", "")
        title = rec.get("title") or filename
        rel = f"studies/{filename}"
        lines.append(f"- [{title}]({rel})")
    lines.append("")
    (DOCS / "studies" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    write_guide_index()
    write_studies_index()
    print("Generated guide and study index pages.")


if __name__ == "__main__":
    main()
