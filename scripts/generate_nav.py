#!/usr/bin/env python3
"""Generate navigation index pages for the published lemon guide.

Writes two themed index pages:
  - docs/guide/sections/index.md  (the 19 guide sections)
  - docs/studies/index.md         (study notes, grouped by year)

Links are written relative to the index file's own directory (sibling files),
so they resolve correctly on GitHub Pages. Each page carries Jekyll front
matter so the minima theme lays it out.
"""

from pathlib import Path
import json
import re

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
GUIDE_SECTIONS = DOCS / "guide" / "sections"
STUDIES_DIR = DOCS / "studies"
STUDIES_INDEX = ROOT / "data" / "studies_index.json"

HEADING_RE = re.compile(r"^#+\s*(.*)")
# Index/nav files we generate — never list them as content entries.
SKIP_NAMES = {"index.md", "_index.md"}


def extract_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        m = HEADING_RE.match(line)
        if m:
            return m.group(1).strip()
    return path.stem


def front_matter(title: str) -> list[str]:
    return ["---", "layout: page", f"title: {title}", "---", ""]


def write_guide_index() -> None:
    lines = front_matter("Guide Sections")
    lines += ["# Guide Sections", "",
              "The Lisbon lemon guide, in 19 sections.", "", ""]
    for path in sorted(GUIDE_SECTIONS.glob("*.md")):
        if path.name in SKIP_NAMES:
            continue
        title = extract_title(path)
        # Sibling link: the index lives in the same folder as the sections.
        lines.append(f"- [{title}]({path.name})")
    lines.append("")
    (GUIDE_SECTIONS / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _year_of(filename: str, rec: dict) -> str:
    year = str(rec.get("year") or "").strip()
    if re.fullmatch(r"\d{4}", year):
        return year
    m = re.match(r"(\d{4})", filename)
    return m.group(1) if m else "Other"


def write_studies_index() -> None:
    records = []
    if STUDIES_INDEX.exists():
        records = json.loads(STUDIES_INDEX.read_text(encoding="utf-8"))
    else:
        for path in sorted(STUDIES_DIR.glob("*.md")):
            if path.name in SKIP_NAMES:
                continue
            records.append({"filename": path.name, "title": extract_title(path)})

    records = [r for r in records if r.get("filename") not in SKIP_NAMES]

    # Group by year so the list is scannable instead of one long wall.
    by_year: dict[str, list[dict]] = {}
    for rec in records:
        filename = rec.get("filename", "")
        by_year.setdefault(_year_of(filename, rec), []).append(rec)

    lines = front_matter("Study Notes")
    lines += ["# Study Notes", "",
              f"{len(records)} source study notes, newest first.", "", ""]
    for year in sorted(by_year, reverse=True):
        lines.append(f"## {year}")
        lines.append("")
        for rec in sorted(by_year[year], key=lambda r: r.get("filename", "")):
            filename = rec.get("filename", "")
            title = rec.get("title") or filename
            # Sibling link: the index lives in docs/studies/ with the notes.
            lines.append(f"- [{title}]({filename})")
        lines.append("")
    (STUDIES_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    write_guide_index()
    write_studies_index()
    # Remove the orphaned mislocated index from earlier versions, if present.
    orphan = DOCS / "guide" / "index.md"
    if orphan.exists():
        orphan.unlink()
    print("Generated guide and study index pages.")


if __name__ == "__main__":
    main()
