#!/usr/bin/env python3
"""
Canonical claim-integrity linter for the Lisbon Lemon Guide (RAW workspace).

This is the **single** checker used by both the maintenance loops and the build
gate (build.py calls it; lint_claims.py delegates to it) so there is one
implementation of "what integrity means" and the loop and gate can never drift.

It runs against the **raw source of truth** — guide sections and
``_claim_table.md`` in ``raw/industry reports/lisbon-lemon-guide/`` — and emits a
machine-readable report the maintenance loop consumes.

Integrity model (closed under every operation):
  * REFERENTIAL — every ``[ClaimID]`` cited in prose resolves to a table row,
    and every row's Source File exists on disk.
  * SEMANTIC (new claims) — every claim in batch **F or later** (i.e. added
    "going forward") must carry a verbatim **quote receipt** that is found in its
    source note. This makes "no fabrication" a deterministic check rather than a
    matter of trust. Legacy batches A–E are exempt (referential only).

Checks
------
  L1  Referenced-but-not-in-table         (HARD)  + ranked did-you-mean
  L2  Claim-table Source File missing      (HARD)
  L3  Cross-ref "(§N)" outside 1..19    (HARD)
  L9  New claim (F+) missing/invalid quote receipt  (HARD)
  L5  Section missing evidence callout / a required closer  (WARN)
  L7  Orphan claims, de-polluted of broken-ref fix-targets  (WARN)
  L8  Numeric-consistency: a claim's Numeric Target never appears near any of
      its citations (possible content drift)            (WARN, advisory)

Receipt format (in a new claim's Citation Detail or Notes cell):
  Receipt: "an exact substring copied from the source note"

Outputs (into the raw guide dir): _lint_report.json, _lint_report.md
Exit code: 1 if any HARD errors (L1/L2/L3/L9), else 0.

Usage:
  python scripts/lint_report.py
  python scripts/lint_report.py --raw "D:/.../lisbon-lemon-guide"
  python scripts/lint_report.py --no-historical   # disable line-number heuristic
  python scripts/lint_report.py --quiet
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from itertools import permutations
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
DEFAULT_RAW_GUIDE = REPO_ROOT.parent / "raw" / "industry reports" / "lisbon-lemon-guide"

ID_RE = re.compile(r"\b([A-Z]\d{3})\b")
BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
SECTION_REF_RE = re.compile(r"§\s*(\d{1,2})")
RECEIPT_RE = re.compile(r'Receipt:\s*["“]([^"”]+)["”]')
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
STRENGTHS = {"Strong", "Moderate", "Weak", "Extrapolated"}
MAX_SECTION = 19
FIRST_NEW_BATCH = "F"   # batches >= F are "new, going forward" and need receipts
REQUIRED_CLOSERS = ("Key takeaways", "Things not to do", "Evidence gaps")

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "by", "at", "as", "be", "not", "no", "than", "that", "this", "it",
    "its", "from", "per", "vs", "via", "into", "over", "under", "more", "less",
    "can", "may", "but", "if", "then", "so", "do", "does",
}


def tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _STOP}


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# --------------------------------------------------------------------------- #
# Parsing                                                                      #
# --------------------------------------------------------------------------- #
def parse_claim_table(path: Path):
    """{id: {source,line,text,strength,category,citation,notes}}, {file_line: id}"""
    claims: dict[str, dict] = {}
    by_line: dict[int, str] = {}
    if not path.exists():
        return claims, by_line
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if s.startswith("|---"):
            continue
        if not s.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 5 or not re.match(r"^[A-Z]\d{3}$", parts[0]):
            continue
        source = parts[4]
        m = re.match(r"^\[([^\]]+)\]\([^)]+\)$", source)  # unwrap linkified cell
        if m:
            source = m.group(1).strip()
        claims[parts[0]] = {
            "source": source,
            "line": n,
            "text": parts[1] if len(parts) > 1 else "",
            "category": parts[2] if len(parts) > 2 else "",
            "numeric": parts[3] if len(parts) > 3 else "",
            "strength": parts[5] if len(parts) > 5 else "",
            "citation": parts[7] if len(parts) > 7 else "",
            "notes": parts[8] if len(parts) > 8 else "",
        }
        by_line[n] = parts[0]
    return claims, by_line


def extract_refs(path: Path):
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for b in BRACKET_RE.finditer(line):
            for cm in ID_RE.finditer(b.group(1)):
                yield cm.group(1), n, line.strip()


def available_studies(d: Path) -> set[str]:
    return {f.stem for f in d.glob("*.md")} if d.exists() else set()


# --------------------------------------------------------------------------- #
# Did-you-mean                                                                 #
# --------------------------------------------------------------------------- #
def suggest(bad_id, window, claims, by_line, historical=True, k=3):
    """Rank candidate corrections. Content overlap dominates so a strong text
    match overrides a misleading structural guess. The line-number hypothesis
    is a one-time *historical* heuristic for the original "grep line-number as
    id" bug; it self-corrupts as the table grows, so it is content-validated and
    can be disabled with --no-historical once the initial cleanup is done."""
    letter, num = bad_id[0], int(bad_id[1:])
    win = tokens(window)
    scored: dict[str, tuple[int, str]] = {}

    def ov(cid):
        return len(win & tokens(claims[cid]["text"])) if cid in claims else 0

    def bump(cid, score, why):
        if cid in claims and (cid not in scored or score > scored[cid][0]):
            scored[cid] = (score, why)

    if historical and num in by_line:
        cid = by_line[num]
        o = ov(cid)
        bump(cid, min(100, 55 + 12 * o),
             f"[historical] row at file-line {num}" +
             (f", {o} shared term(s)" if o else ", no text overlap"))

    for p in {"".join(t) for t in permutations(bad_id[1:])}:
        cid = f"{letter}{p}"
        if cid in claims:
            bump(cid, min(90, 45 + 10 * ov(cid)),
                 f"digit rearrangement, {ov(cid)} shared term(s)")

    if win:
        for cid in claims:
            o = ov(cid)
            if not o:
                continue
            base = (40 + 7 * o) if cid[0] == letter else (20 + 5 * o)
            bump(cid, min(96 if cid[0] == letter else 70, base),
                 f"text overlap: {', '.join(sorted(win & tokens(claims[cid]['text']))[:5])}")

    return [{"id": c, "score": s, "why": w, "claim": claims[c]["text"][:120]}
            for c, (s, w) in sorted(scored.items(), key=lambda kv: -kv[1][0])[:k]]


# --------------------------------------------------------------------------- #
# Lint                                                                         #
# --------------------------------------------------------------------------- #
def lint(raw_guide: Path, historical=True):
    sections_dir = raw_guide / "sections"
    studies_dir = raw_guide.parent / "lisbon-lemon-studies"
    claims, by_line = parse_claim_table(raw_guide / "_claim_table.md")
    studies = available_studies(studies_dir)

    rep = {
        "raw_guide": str(raw_guide),
        "L1_broken_refs": [], "L2_missing_sources": [], "L3_bad_section_refs": [],
        "L9_receipt": [], "L5_structure": [], "L7_orphans": [], "L8_numeric": [],
    }
    referenced: dict[str, list[str]] = {}
    cite_lines: dict[str, list[str]] = {}

    for sec in sorted(sections_dir.glob("*.md")):
        text = sec.read_text(encoding="utf-8")
        for cid, ln, window in extract_refs(sec):
            referenced.setdefault(cid, []).append(sec.name)
            cite_lines.setdefault(cid, []).append(window)
            if cid not in claims:
                rep["L1_broken_refs"].append({
                    "section": sec.name, "line": ln, "cited": cid,
                    "context": window[:160],
                    "suggestions": suggest(cid, window, claims, by_line, historical),
                })
        for m in SECTION_REF_RE.finditer(text):
            n = int(m.group(1))
            if not (1 <= n <= MAX_SECTION):
                rep["L3_bad_section_refs"].append({"section": sec.name, "ref": f"§{n}"})
        missing = [c for c in REQUIRED_CLOSERS if c not in text]
        if "Evidence callout" not in text:
            missing.append("Evidence callout")
        if missing:
            rep["L5_structure"].append({"section": sec.name, "missing": missing})

    # L2 dangling sources
    for cid, info in sorted(claims.items()):
        if info["source"] and info["source"] not in studies:
            rep["L2_missing_sources"].append({"claim": cid, "source": info["source"]})

    # L9 quote receipts for new (F+) claims
    receipt_required = receipt_ok = 0
    for cid, info in sorted(claims.items()):
        if cid[0] < FIRST_NEW_BATCH:
            continue
        receipt_required += 1
        m = RECEIPT_RE.search(info["citation"] + " || " + info["notes"])
        if not m:
            rep["L9_receipt"].append({"claim": cid, "issue": "no Receipt: \"...\" quote"})
            continue
        quote = m.group(1)
        note = studies_dir / f"{info['source']}.md"
        if not note.exists():
            rep["L9_receipt"].append({"claim": cid, "issue": f"source note {info['source']} missing"})
            continue
        if norm_ws(quote) in norm_ws(note.read_text(encoding="utf-8")):
            receipt_ok += 1
        else:
            rep["L9_receipt"].append({
                "claim": cid, "issue": "receipt quote not found verbatim in source note",
                "quote": quote[:120]})

    # L7 orphans, de-polluted: a claim that is the top fix-target of a broken ref
    # is not really unused — it's cited under a wrong id. Exclude such targets.
    fix_targets = {b["suggestions"][0]["id"] for b in rep["L1_broken_refs"]
                   if b["suggestions"]}
    true_orphans = sorted(set(claims) - set(referenced) - fix_targets)
    rep["L7_orphans"] = true_orphans

    # L8 numeric drift (advisory): a claim with a numeric target whose number
    # never appears near any of its citations.
    for cid, info in claims.items():
        nums = NUM_RE.findall(info["numeric"])
        if not nums or cid not in cite_lines:
            continue
        joined = " ".join(cite_lines[cid])
        if not any(n in joined for n in nums):
            rep["L8_numeric"].append({"claim": cid, "numeric": info["numeric"][:40]})

    hard = (len(rep["L1_broken_refs"]) + len(rep["L2_missing_sources"])
            + len(rep["L3_bad_section_refs"]) + len(rep["L9_receipt"]))
    rep["metrics"] = {
        "claims_in_table": len(claims),
        "study_files": len(studies),
        "broken_ref_instances": len(rep["L1_broken_refs"]),
        "unique_broken_ids": len({b["cited"] for b in rep["L1_broken_refs"]}),
        "missing_sources": len(rep["L2_missing_sources"]),
        "true_orphans": len(true_orphans),
        "receipt_required": receipt_required,
        "receipt_ok": receipt_ok,
        "receipt_coverage": round(receipt_ok / receipt_required, 3) if receipt_required else 1.0,
        "numeric_warnings": len(rep["L8_numeric"]),
        "hard_errors": hard,
        "warnings": len(rep["L5_structure"]) + len(true_orphans) + len(rep["L8_numeric"]),
    }
    rep["clean"] = hard == 0
    return rep


# --------------------------------------------------------------------------- #
# Render                                                                       #
# --------------------------------------------------------------------------- #
def render_md(r):
    m = r["metrics"]
    o = ["# Lisbon Lemon Guide — Integrity Lint Report (raw workspace)", ""]
    o.append(f"- Claims: **{m['claims_in_table']}** · Studies: **{m['study_files']}**")
    o.append(f"- **Hard errors: {m['hard_errors']}** "
             f"(broken refs {m['broken_ref_instances']} / {m['unique_broken_ids']} unique · "
             f"missing sources {m['missing_sources']} · receipt fails {len(r['L9_receipt'])})")
    o.append(f"- Receipt coverage (new F+ claims): **{m['receipt_ok']}/{m['receipt_required']}** "
             f"({m['receipt_coverage']:.0%})")
    o.append(f"- Warnings: true orphans {m['true_orphans']} · numeric {m['numeric_warnings']} · "
             f"structure {len(r['L5_structure'])}")
    o.append(f"- Status: {'✅ CLEAN (gate passes)' if r['clean'] else '❌ ERRORS — fix in raw'}")
    o.append("")

    if r["L1_broken_refs"]:
        o += ["## L1 — Broken claim references (HARD) + did-you-mean", "",
              "| Section | Line | Cited | Top suggestion | Why | Other |",
              "|---|---|---|---|---|---|"]
        for b in r["L1_broken_refs"]:
            s = b["suggestions"]
            top = s[0] if s else {"id": "—", "why": "no candidate"}
            o.append(f"| {b['section']} | {b['line']} | `{b['cited']}` | "
                     f"**{top.get('id','—')}** | {top.get('why','')} | "
                     f"{', '.join(x['id'] for x in s[1:]) or '—'} |")
        o += ["", "<details><summary>Context per broken ref</summary>\n"]
        for b in r["L1_broken_refs"]:
            o.append(f"- **{b['cited']}** ({b['section']}:{b['line']}) — `{b['context']}`")
            for s in b["suggestions"]:
                o.append(f"    - → `{s['id']}` (score {s['score']}, {s['why']}): {s['claim']}")
        o += ["\n</details>", ""]

    if r["L2_missing_sources"]:
        o += ["## L2 — Claim-table source files not on disk (HARD)", ""]
        o += [f"- `{x['claim']}` → study `{x['source']}` not found" for x in r["L2_missing_sources"]]
        o.append("")
    if r["L9_receipt"]:
        o += ["## L9 — New (F+) claims with missing/invalid quote receipt (HARD)", ""]
        o += [f"- `{x['claim']}`: {x['issue']}" + (f" — “{x.get('quote','')}”" if x.get('quote') else "")
              for x in r["L9_receipt"]]
        o.append("")
    if r["L3_bad_section_refs"]:
        o += ["## L3 — Cross-refs out of range 1–19 (HARD)", ""]
        o += [f"- {x['section']}: {x['ref']}" for x in r["L3_bad_section_refs"]]
        o.append("")
    if r["L5_structure"]:
        o += ["## L5 — Section structure warnings", ""]
        o += [f"- {x['section']}: missing {', '.join(x['missing'])}" for x in r["L5_structure"]]
        o.append("")
    if r["L8_numeric"]:
        o += [f"## L8 — Numeric-drift warnings ({len(r['L8_numeric'])}, advisory)", ""]
        o += [f"- `{x['claim']}`: target `{x['numeric']}` not seen near its citations"
              for x in r["L8_numeric"][:30]]
        o.append("")
    if r["L7_orphans"]:
        o += [f"## L7 — True orphans ({len(r['L7_orphans'])}; broken-ref targets excluded)", "",
              ", ".join(f"`{x}`" for x in r["L7_orphans"][:60]) +
              (" …" if len(r["L7_orphans"]) > 60 else ""), ""]

    o += ["---", "*Single canonical checker (`scripts/lint_report.py`). Fix in RAW; "
          "L1/L2/L3/L9 must be 0 before publishing. Receipts enforced on batch F+ only.*"]
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=DEFAULT_RAW_GUIDE)
    ap.add_argument("--no-historical", action="store_true",
                    help="Disable the line-number did-you-mean heuristic.")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    raw = a.raw.resolve()
    if not (raw / "sections").exists():
        print(f"ERROR: no sections/ under {raw}", file=sys.stderr)
        return 2
    r = lint(raw, historical=not a.no_historical)
    (raw / "_lint_report.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    (raw / "_lint_report.md").write_text(render_md(r), encoding="utf-8")
    if not a.quiet:
        m = r["metrics"]
        print(f"Lint: {m['hard_errors']} hard error(s), {m['warnings']} warning(s). "
              f"{'CLEAN' if r['clean'] else 'ERRORS'}. "
              f"Receipts {m['receipt_ok']}/{m['receipt_required']}.")
        print(f"  -> {raw / '_lint_report.md'}")
        for b in r["L1_broken_refs"][:40]:
            top = b["suggestions"][0]["id"] if b["suggestions"] else "?"
            print(f"    {b['section']}:{b['line']}  {b['cited']} -> {top}")
    return 1 if r["metrics"]["hard_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
