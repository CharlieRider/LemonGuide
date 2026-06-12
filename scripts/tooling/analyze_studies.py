#!/usr/bin/env python3
"""
analyze_studies.py — Plant Brain: study indexer and wiki guide generator.

Usage:
  python analyze_studies.py generate --studies <folder> [--plan <plan.md>] [--out <output.md>]
  python analyze_studies.py search <query> --studies <folder>
  python analyze_studies.py topic <slug> --studies <folder>
  python analyze_studies.py topics --studies <folder>
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

TOPIC_MAP = {
    "container-pot-growing":   "Container & Media Selection",
    "fertilization-nutrition": "Fertilization & Nutrition",
    "blossom-end-rot-calcium": "Calcium Management (BER Prevention)",
    "watering-irrigation":     "Irrigation & Watering",
    "heat-temperature-stress": "Heat Stress Management",
    "pruning-training":        "Pruning & Training",
    "pollination-fruit-set":   "Pollination & Fruit Set",
    "soil-amendments":         "Growing Media & Soil Amendments",
    "disease-pest-management": "Disease & Pest Management",
    "organic-growing-methods": "Organic Approaches",
    "fruit-quality-flavor":    "Fruit Quality & Flavor",
    "san-marzano-variety":     "San Marzano Variety Notes",
    "indeterminate-varieties": "Indeterminate Growth Habit",
    "root-biology":            "Root Biology",
    "seed-to-harvest-timing":  "Seed-to-Harvest Timing",
}

# Guide section order — most operationally relevant first
GUIDE_ORDER = [
    "container-pot-growing",
    "fertilization-nutrition",
    "blossom-end-rot-calcium",
    "watering-irrigation",
    "heat-temperature-stress",
    "pruning-training",
    "pollination-fruit-set",
    "soil-amendments",
    "disease-pest-management",
    "organic-growing-methods",
    "fruit-quality-flavor",
    "san-marzano-variety",
    "indeterminate-varieties",
    "root-biology",
    "seed-to-harvest-timing",
]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _extract_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading = None
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections


def parse_study(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    meta["_sections"] = _extract_sections(parts[2].strip())
    meta["_filename"] = path.name
    return meta


def load_studies(folder: str) -> list[dict]:
    results = []
    for p in sorted(Path(folder).glob("*.md")):
        if p.name.startswith("_"):
            continue
        s = parse_study(p)
        if s:
            results.append(s)
    return results


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_citation(s: dict) -> str:
    authors = s.get("authors", "Unknown")
    year = s.get("year", "n.d.")
    title = s.get("title", "Untitled")
    journal = s.get("journal", "")
    url = s.get("url") or s.get("pmc") or s.get("doi") or ""
    stem = Path(s.get("_filename", "")).stem

    parts = [f"**{authors} ({year})**. {title}."]
    if journal:
        parts.append(f"*{journal}.*")
    if url:
        parts.append(f"[Link]({url})")
    if stem:
        parts.append(f"[Notes]({stem}.md)")
    return " ".join(parts)


def _first_bullet(findings: str) -> str:
    for line in findings.splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            return stripped
    return ""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_search(args):
    studies = load_studies(args.studies)
    query = " ".join(args.query).lower()
    # Normalize both query and haystack: collapse hyphens/underscores to spaces
    def normalize(text: str) -> str:
        return text.lower().replace("-", " ").replace("_", " ")

    query_n = normalize(query)
    matches = []
    for s in studies:
        haystack = normalize(" ".join([
            str(s.get("title", "")),
            str(s.get("authors", "")),
            str(s.get("tags", "")),
            s["_sections"].get("Key Findings", ""),
            s["_sections"].get("Relevance to San Marzano Container Growing", ""),
        ]))
        if query_n in haystack:
            matches.append(s)

    if not matches:
        print(f"No studies matched '{query}'.")
        return

    print(f"\n{len(matches)} stud{'y' if len(matches) == 1 else 'ies'} matched '{query}':\n")
    for s in matches:
        tags = ", ".join(s.get("tags", []))
        print(f"  [{s.get('year')}] {s.get('title')}")
        print(f"         Topic: {s.get('topic')}  |  Tags: {tags}")
        bullet = _first_bullet(s["_sections"].get("Key Findings", ""))
        if bullet:
            print(f"         {bullet}")
        print()


def cmd_topic(args):
    studies = load_studies(args.studies)
    matches = [s for s in studies if s.get("topic") == args.slug]
    if not matches:
        available = sorted({s.get("topic") for s in studies if s.get("topic")})
        print(f"No studies for topic '{args.slug}'.\nAvailable: {', '.join(available)}")
        return
    label = TOPIC_MAP.get(args.slug, args.slug)
    print(f"\n=== {label} ({len(matches)} studies) ===\n")
    for s in sorted(matches, key=lambda s: s.get("year", 0)):
        print(f"  [{s.get('year')}] {s.get('title')}  —  {s.get('authors')}")
    print()


def cmd_topics(args):
    studies = load_studies(args.studies)
    counts = Counter(s.get("topic") for s in studies if s.get("topic"))
    print(f"\nTopics across {len(studies)} studies:\n")
    for slug in GUIDE_ORDER:
        if slug in counts:
            print(f"  {slug:42s} {counts[slug]:3d}  ({TOPIC_MAP.get(slug, slug)})")
    # Any topics not in the ordered list
    extras = {k: v for k, v in counts.items() if k not in GUIDE_ORDER}
    for slug, count in sorted(extras.items()):
        print(f"  {slug:42s} {count:3d}  ({TOPIC_MAP.get(slug, slug)})")
    print()


def _build_section(heading: str, studies: list[dict], max_per_section: int) -> list[str]:
    lines = [f"## {heading}", ""]
    sorted_studies = sorted(studies, key=lambda s: s.get("year", 0), reverse=True)
    for s in sorted_studies[:max_per_section]:
        findings = s["_sections"].get("Key Findings", "")
        bullets = [l.strip() for l in findings.splitlines() if l.strip().startswith("-")]
        relevance = s["_sections"].get("Relevance to San Marzano Container Growing", "")

        lines.append(f"### {s.get('authors', 'Unknown')} ({s.get('year', 'n.d.')})")
        lines.append(f"*{s.get('title', 'Untitled')}*  ")
        lines.append(f"Journal: {s.get('journal', 'Unknown')}")
        lines.append("")
        if bullets:
            for b in bullets[:4]:
                lines.append(b)
        if relevance:
            lines.append("")
            lines.append(f"> **Relevance:** {relevance}")
        lines.append("")
        lines.append(f"> {format_citation(s)}")
        lines.append("")
    return lines


def cmd_generate(args):
    studies = load_studies(args.studies)
    if not studies:
        sys.exit(f"No study files found in {args.studies}")

    plan_text = ""
    if args.plan:
        plan_path = Path(args.plan)
        if plan_path.exists():
            plan_text = plan_path.read_text(encoding="utf-8").strip()
        else:
            print(f"Warning: plan file not found at {args.plan}")

    by_topic: dict[str, list] = {}
    for s in studies:
        t = s.get("topic")
        if t:
            by_topic.setdefault(t, []).append(s)

    years = [s.get("year") for s in studies if s.get("year")]
    year_range = f"{min(years)}–{max(years)}" if years else "n.d."

    lines: list[str] = [
        "# My Tomato Growing Guide",
        "",
        f"> Auto-generated from personal research database. "
        f"Covers {len(studies)} studies ({year_range}).",
        "",
        "---",
        "",
        "## My Current Plan",
        "",
    ]

    if plan_text:
        lines.append(plan_text)
    else:
        lines.append("*Fill in `plans/my_grow_plan.md` to populate this section.*")
    lines += ["", "---", ""]

    max_per_section = getattr(args, "max", 5)

    for slug in GUIDE_ORDER:
        topic_studies = by_topic.get(slug)
        if not topic_studies:
            continue
        heading = TOPIC_MAP.get(slug, slug)
        count = len(topic_studies)
        lines.append(f"<!-- {slug}: {count} studies total, showing {min(count, max_per_section)} -->")
        lines += _build_section(heading, topic_studies, max_per_section)
        lines += ["---", ""]

    lines += ["## References", ""]
    for s in sorted(studies, key=lambda s: (s.get("year", 0), s.get("authors", ""))):
        lines.append(f"- {format_citation(s)}")
    lines.append("")

    output = "\n".join(lines)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Guide written: {out_path}")
        print(f"  {len(studies)} studies  |  {len(lines)} lines  |  {len(output):,} bytes")
    else:
        print(output)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Reconfigure stdout to UTF-8 so special chars in study text don't crash on Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(
        description="Plant Brain — tomato study indexer and wiki guide generator"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate wiki guide from studies + plan")
    gen.add_argument("--studies", required=True, help="Path to tomato-studies folder")
    gen.add_argument("--plan", help="Path to my_grow_plan.md (optional)")
    gen.add_argument("--out", help="Output .md file (default: stdout)")
    gen.add_argument("--max", type=int, default=5,
                     help="Max studies shown per guide section (default: 5)")

    srch = sub.add_parser("search", help="Keyword search across all studies")
    srch.add_argument("query", nargs="+")
    srch.add_argument("--studies", required=True)

    tp = sub.add_parser("topic", help="List all studies for a topic slug")
    tp.add_argument("slug")
    tp.add_argument("--studies", required=True)

    tps = sub.add_parser("topics", help="List all topics and their study counts")
    tps.add_argument("--studies", required=True)

    args = parser.parse_args()
    {
        "generate": cmd_generate,
        "search":   cmd_search,
        "topic":    cmd_topic,
        "topics":   cmd_topics,
    }[args.command](args)


if __name__ == "__main__":
    main()
