#!/usr/bin/env python3
"""
soil_normalizer.py

Near-deterministic normalizer for the Lisbon-lemon soil/substrate evidence.

Reads the master claim table (_claim_table.md), selects soil chemical/physical
claims (pH, EC/salinity, AFP/WHC/total porosity, CEC, water-salinity), classifies
HOW each was administered (medium + measurement method + container geometry),
scores relevance to the canonical scenarios (field soil / nursery container /
19x14 home pot), and TRANSLATES the value onto a common basis where a defensible
conversion exists:

  * EC : soil/saturation-extract  <->  pour-through   (one generalizable factor set)
  * pH : soil/saturation-extract  <->  pour-through   (identity +/- documented drift)
  * AFP/porosity : container-height transfer            (perched-water-table model)

Everything else is tagged 'context-only'. No fertilizer-rate or thermal
conversions (out of scope by design).

Outputs (written into the claim-table's folder):
  soil_tags.csv                 reviewable per-claim classification (freeze this)
  _normalized_soil_claims.md    normalized table for the guide to cite
  soil_normalization_report.md  coverage + combos + review list

Rules live in soil_rules.yaml next to this script; if PyYAML or the file is
unavailable the identical embedded DEFAULT_RULES are used. Tune the YAML after
the Pass-1 analysis run.

Usage:
    python soil_normalizer.py "D:\\...\\lisbon-lemon-guide"
    python soil_normalizer.py <folder> --claim-table _claim_table.md -v
"""

import argparse
import csv
import io
import re
import sys
from pathlib import Path

# Force UTF-8 on Windows consoles that default to cp1252 (table has – × etc.)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Embedded default rules (kept in sync with soil_rules.yaml)
# ---------------------------------------------------------------------------
DEFAULT_RULES = {
    "medium_rules": {
        "irrigation_water": {
            "source_kw": ["water-quality", "irrigation-water"],
            "text_kw": ["irrigation water", "water quality", "tap water",
                        "water ec", "in the water", "water salinity"],
        },
        "solution": {
            "source_kw": ["hydroponic", "nutrient-solution"],
            "text_kw": ["nutrient solution", "hydroponic", "mmol/l", "fertigation solution"],
        },
        "lab_assay": {
            "source_kw": ["hypoxia-rnaseq", "root-zone-temperature", "supraoptimal", "critical-root"],
            "text_kw": ["excised", "electrolyte leakage", "membrane injury", "in vitro", "tissue culture"],
        },
        "tissue": {
            "source_kw": ["leaf-tissue", "critical-nutrient"],
            "text_kw": ["leaf tissue", "foliar tissue", "petiole", "leaf analysis",
                        "tissue test", "leaf sufficiency"],
        },
        "soilless_substrate": {
            "source_kw": ["substrate", "container-media", "potting", "coir", "cococoir",
                          "biochar", "pine-bark", "rice-hulls", "pumice", "perlite",
                          "turface", "air-porosity", "container-substrate", "soil-mixes",
                          "diy-citrus", "potting-soil"],
            "text_kw": ["container media", "potting", "substrate", "soilless", "peat",
                        "coir", "coco", "pine bark", "bark mix", "pumice", "perlite",
                        "pour-through", "pour through", "saturated media", "container capacity",
                        "potting mix", "the pot", "in a pot", "container"],
        },
        "mineral_soil": {
            "source_kw": ["drought-salinity", "irrigation-scheduling", "fertilizing-citrus",
                          "soil-temperature", "citrus-fertilization"],
            "text_kw": ["field soil", "orchard", "in-ground", "in the ground", "native soil",
                        "saturated paste", "ece", "per acre", "grove", "soil ph", "soil ec",
                        "soil test", "mineral soil"],
        },
    },
    "method_rules": {
        "saturated_paste": ["saturated paste", "ece", "saturation extract"],
        "pour_through": ["pour-through", "pour through", "pourthru", "leachate"],
        "sme": ["saturated media", "sme", "2:1"],
        "dilution_1_2": ["1:2"],
        "dilution_1_5": ["1:5"],
        "dilution_1_1": ["1:1 ", "1:1,", "1:1)"],
        "water_ec": ["water ec", "ec of the water", "irrigation water"],
    },
    "method_default_by_medium": {
        "mineral_soil": "saturated_paste",
        "soilless_substrate": "sme",
        "irrigation_water": "water_ec",
        "solution": "solution_ec",
        "unspecified": "unspecified",
    },
    "ec_to_pourthrough": {
        "pour_through":    {"factor": 1.00, "confidence": "direct",   "source": "definitional (target basis)"},
        "sme":             {"factor": 1.00, "confidence": "high",     "source": "Cavins et al. 2000, NCSU PourThru: PourThru ~= SME"},
        "saturated_paste": {"factor": 1.00, "confidence": "moderate", "source": "saturation-extract family; ECe(soil)~SME(media), cross-medium caveat"},
        "dilution_1_2":    {"factor": 2.50, "confidence": "moderate", "source": "Warncke 1986 / NCSU: 1:2 v/v x ~2.5 -> SME basis"},
        "dilution_1_5":    {"factor": 5.00, "confidence": "low",      "source": "approx 1:5 -> saturation basis, texture-dependent"},
        "dilution_1_1":    {"factor": 1.80, "confidence": "low",      "source": "approx 1:1 -> saturation basis"},
        "water_ec":        {"factor": None, "confidence": "na",       "source": "water EC stays on its own basis"},
        "solution_ec":     {"factor": None, "confidence": "na",       "source": "nutrient-solution EC not comparable to media pour-through"},
        "unspecified":     {"factor": 1.00, "confidence": "assumed",  "source": "no method stated; assume saturation/pour-through basis"},
    },
    "ph_rules": {
        "method_drift_units": 0.3,
        "drift_source": "Extraction-method pH drift across 1:1/1:2/SME/PourThru is <= ~0.3 unit (NCSU PourThru)",
        "mineral_to_soilless_target_offset": -0.5,
        "offset_source": "Soilless-media optimum pH runs ~0.5 unit below mineral-soil optimum (Purdue HO-substrate)",
    },
    "afp_model": {
        "total_porosity_pct": 38.2,
        "perched_water_cm": 5.45,
        "source": "UC ANR Tjosvold 2019, Soil Mixes Part 2: AFP vs container height (peat:vermiculite anchors)",
        "caveat": "Anchored on one peat:vermiculite mix; use as a relative geometry shift, not an absolute AFP for a bark mix.",
        "anchors_in_to_afp": {3.25: 13.0, 4.5: 20.0},
    },
    "scenarios": {
        "field_soil": {"height_in": None},
        "nursery_container": {"height_in": 6.0},
        "home_pot": {"height_in": 14.0},
    },
    "container_heights_in": {
        "648 tray": 1.0, "288 cell": 1.5, "tray": 1.0, "cell": 1.5,
        "4-inch": 3.25, "4 inch": 3.25, "6-inch": 4.5, "6 inch": 4.5,
        "1-gallon": 6.5, "5-gallon": 12.0, "14-inch": 14.0, "14 inch": 14.0,
    },
}

IN_TO_CM = 2.54


def load_rules(path: Path) -> dict:
    if path and path.exists():
        try:
            import yaml  # type: ignore
            with path.open(encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                print(f"Loaded rules from {path.name}")
                return loaded
        except ImportError:
            print("PyYAML not installed — using embedded default rules "
                  "(pip install pyyaml to edit soil_rules.yaml).")
        except Exception as e:
            print(f"Could not parse {path.name} ({e}) — using embedded defaults.")
    else:
        print("soil_rules.yaml not found — using embedded default rules.")
    return DEFAULT_RULES


# ---------------------------------------------------------------------------
# Claim-table parsing
# ---------------------------------------------------------------------------
CLAIM_ROW = re.compile(r"^\|\s*([A-E]\d{3})\s*\|")
COLS = ["claim_id", "claim", "category", "numeric", "source_file",
        "evidence", "applicability", "citation", "notes"]


def parse_claim_table(path: Path) -> list:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not CLAIM_ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        rows.append(dict(zip(COLS, cells[:9])))
    return rows


# ---------------------------------------------------------------------------
# Measure detection + value parsing
# ---------------------------------------------------------------------------
EC_UNITS = {"ds/m": 1.0, "mmho/cm": 1.0, "ms/cm": 1.0, "µs/cm": 0.001,
            "us/cm": 0.001, "umho/cm": 0.001}

NUM = r"(\d+(?:\.\d+)?)"
RANGE = re.compile(NUM + r"\s*(?:–|—|-|to)\s*" + NUM)


def _blob(row: dict) -> str:
    return f"{row['claim']} {row['numeric']} {row['notes']}".lower()


def detect_measure(row: dict) -> str:
    """Return the primary soil measure for the claim, or '' if not soil-relevant."""
    b = _blob(row)
    cat = row["category"].split()[0] if row["category"] else ""
    has_ph = bool(re.search(r"\bph\b", b))
    has_ec = ("ds/m" in b or "mmho" in b or "ms/cm" in b or "µs/cm" in b
              or "us/cm" in b or "ece" in b or "soluble salt" in b
              or "salinity" in b or "electrical conductivity" in b)
    has_afp = "air-filled poros" in b or "air filled poros" in b or re.search(r"\bafp\b", b)
    has_whc = ("water-holding" in b or "water holding" in b or "container capacity" in b
               or "water-retention" in b or "water retention" in b)
    has_tp = "total porosity" in b
    has_cec = "cec" in b or "meq/100" in b or "cation exchange" in b
    has_watersalt = (("mg/l" in b or "meq/l" in b)
                     and ("cl" in b or "na" in b or "sodium" in b or "chloride" in b
                          or "boron" in b or " b " in b))
    # priority order
    if has_ph:
        return "pH"
    if has_afp:
        return "AFP"
    if has_whc:
        return "WHC"
    if has_tp:
        return "total_porosity"
    if has_cec:
        return "CEC"
    if has_ec:
        return "water_salinity" if has_watersalt and "water" in b else "EC"
    if has_watersalt:
        return "water_salinity"
    # category fallback: soil-relevant categories with no parsed measure
    if cat in {"4", "5"}:
        return "physical_other"
    if cat in {"6"}:
        return "pH"
    if cat in {"7", "14"}:
        return "EC"
    return ""


def parse_ec(text: str):
    """Return (low, high, unit_display) in dS/m, or None."""
    t = text.lower()
    # find a unit token and a nearby number/range
    for unit, mult in EC_UNITS.items():
        if unit in t:
            seg = t
            m = RANGE.search(seg)
            if m:
                lo, hi = float(m.group(1)) * mult, float(m.group(2)) * mult
                return (lo, hi, "dS/m")
            m = re.search(NUM + r"\s*" + re.escape(unit), seg)
            if m:
                v = float(m.group(1)) * mult
                return (v, v, "dS/m")
    # ECe value without explicit unit token (assume dS/m)
    m = re.search(r"ece[^0-9]*~?\s*" + NUM, t)
    if m:
        v = float(m.group(1))
        return (v, v, "dS/m")
    return None


def _plausible_ph(*vals):
    return all(3.0 <= v <= 9.5 for v in vals)


def parse_ph(text: str):
    """Accept a pH only when 'pH' sits adjacent to the number and the value is a
    plausible soil/substrate pH (3.0–9.5). This rejects pH-*change* phrasings like
    'drops pH ~1 unit' and amendment rates sitting near the word pH."""
    t = text.lower()
    # range form: pH [~<>] N–N
    for m in re.finditer(r"ph[\s~<>≈]{0,3}" + NUM + r"\s*(?:–|—|-|to)\s*" + NUM, t):
        lo, hi = float(m.group(1)), float(m.group(2))
        if _plausible_ph(lo, hi):
            return (lo, hi, "pH")
    # single value: pH [~<>] N
    for m in re.finditer(r"ph[\s~<>≈]{0,3}" + NUM, t):
        v = float(m.group(1))
        if _plausible_ph(v):
            return (v, v, "pH")
    return None


def parse_pct(text: str):
    """First percentage (range) found."""
    m = RANGE.search(text)
    if m and "%" in text:
        return (float(m.group(1)), float(m.group(2)), "%")
    m = re.search(NUM + r"\s*%", text)
    if m:
        v = float(m.group(1))
        return (v, v, "%")
    return None


def parse_value(measure: str, row: dict):
    text = f"{row['numeric']} ; {row['claim']}"
    if measure == "EC" or measure == "water_salinity":
        return parse_ec(text)
    if measure == "pH":
        return parse_ph(text)
    if measure in ("AFP", "WHC", "total_porosity"):
        return parse_pct(text)
    if measure == "CEC":
        m = RANGE.search(text)
        if m and "meq" in text.lower():
            return (float(m.group(1)), float(m.group(2)), "meq/100cc")
        m = re.search(NUM + r"\s*meq", text.lower())
        if m:
            v = float(m.group(1))
            return (v, v, "meq/100cc")
    return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify_medium(row: dict, rules: dict) -> str:
    src = row["source_file"].lower()
    blob = _blob(row) + " " + row["applicability"].lower()
    for medium, kw in rules["medium_rules"].items():
        for s in kw.get("source_kw", []):
            if s in src:
                return medium
    for medium, kw in rules["medium_rules"].items():
        for t in kw.get("text_kw", []):
            if t in blob:
                return medium
    return "unspecified"


def classify_method(row: dict, medium: str, rules: dict) -> tuple:
    """Return (method, inferred: bool)."""
    b = _blob(row)
    for method, kws in rules["method_rules"].items():
        for kw in kws:
            if kw in b:
                return method, False
    return rules["method_default_by_medium"].get(medium, "unspecified"), True


def detect_geometry(row: dict, rules: dict):
    """Return (height_in, multi_bool). height_in None if unknown."""
    b = _blob(row)
    found = []
    for token, h in rules["container_heights_in"].items():
        if token in b:
            found.append(h)
    found = sorted(set(found))
    if not found:
        return None, False
    if len(found) > 1:
        return found[0], True       # multi-height claim (e.g., the AFP-vs-height anchor study)
    return found[0], False


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------
def afp_at_height(h_in, model):
    if h_in is None:
        return None
    h_cm = h_in * IN_TO_CM
    pwt = model["perched_water_cm"]
    if h_cm <= pwt:
        return 0.0
    return model["total_porosity_pct"] * (1 - pwt / h_cm)


def convert_ec(val, method, medium, rules):
    tbl = rules["ec_to_pourthrough"].get(method, rules["ec_to_pourthrough"]["unspecified"])
    factor = tbl["factor"]
    if factor is None or val is None:
        return None, tbl["confidence"], tbl["source"]
    lo, hi, _ = val
    out = (round(lo * factor, 2), round(hi * factor, 2), "dS/m (pour-through)")
    caveat = ""
    if medium == "mineral_soil" and method == "saturated_paste":
        caveat = "cross-medium: soil ECe treated as ~ media saturation basis (approx)"
    return out, tbl["confidence"], (tbl["source"] + ("; " + caveat if caveat else ""))


def convert_ph(val, medium, rules):
    if val is None:
        return None, "na", ""
    ph = rules["ph_rules"]
    lo, hi, _ = val
    note = f"identity +/- {ph['method_drift_units']} unit method drift"
    if medium == "mineral_soil":
        note += (f"; mineral->soilless target offset {ph['mineral_to_soilless_target_offset']} "
                 f"(optimum runs lower in soilless media)")
    return (lo, hi, "pH (pour-through ~ extract)"), "high", note


def convert_afp(val, h_src, target_h, model):
    if val is None or h_src is None:
        return None, "na", ""
    src_afp = afp_at_height(h_src, model)
    tgt_afp = afp_at_height(target_h, model)
    if not src_afp or src_afp <= 0:
        return None, "na", ""
    ratio = tgt_afp / src_afp
    lo, hi, _ = val
    out = (round(lo * ratio, 1), round(hi * ratio, 1), f"% AFP @ {target_h:g}in")
    return out, "moderate", (f"geometry transfer x{ratio:.2f} from {h_src:g}in; {model['caveat']}")


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------
def score_relevance(measure, medium, method, geometry, multi):
    if measure in ("EC",):
        if medium in ("solution",):
            return "not-applicable"
        if medium == "irrigation_water":
            return "context-only"
        if medium == "soilless_substrate" and method == "pour_through":
            return "direct"
        return "convertible"
    if measure == "pH":
        if medium in ("solution", "tissue", "lab_assay"):
            return "context-only"
        if medium == "soilless_substrate" and method == "pour_through":
            return "direct"
        return "convertible"
    if measure in ("AFP", "WHC", "total_porosity"):
        if multi:
            return "context-only"       # the anchor study itself / multi-height
        return "convertible" if geometry else "context-only"
    if measure == "water_salinity":
        return "direct"                 # applies to the irrigation scenario as-is
    if measure == "CEC":
        return "context-only"
    return "context-only"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def fmt(val):
    if not val:
        return ""
    lo, hi, unit = val
    body = f"{lo:g}" if lo == hi else f"{lo:g}–{hi:g}"
    return f"{body} {unit}".strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Normalize soil/substrate claims to the container scenarios.")
    ap.add_argument("folder", help="folder containing the claim table (outputs written here)")
    ap.add_argument("--claim-table", default="_claim_table.md")
    ap.add_argument("--rules", default=None, help="rules YAML (default: soil_rules.yaml next to script)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    folder = Path(args.folder).resolve()
    ctab = folder / args.claim_table
    if not ctab.exists():
        sys.exit(f"Claim table not found: {ctab}")
    rules_path = Path(args.rules) if args.rules else Path(__file__).with_name("soil_rules.yaml")
    rules = load_rules(rules_path)

    target_h = rules["scenarios"]["home_pot"]["height_in"]
    nursery_h = rules["scenarios"]["nursery_container"]["height_in"]
    model = rules["afp_model"]

    rows = parse_claim_table(ctab)
    print(f"Parsed {len(rows)} claims from {ctab.name}")

    SOIL_CATS = {"4", "5", "6", "7", "14"}
    NUMERIC = {"EC", "pH", "AFP", "WHC", "total_porosity", "CEC", "water_salinity"}

    records = []
    review = []
    for row in rows:
        measure = detect_measure(row)
        if not measure:
            continue
        cat = row["category"].split()[0] if row["category"] else ""
        val = parse_value(measure, row)
        # Soil-relevance gate: always take the soil categories; from any other
        # category, take a claim only if it actually carries a soil number.
        if cat not in SOIL_CATS and not val:
            continue
        medium = classify_medium(row, rules)
        # Extraction method only matters for EC/pH; leave it n/a elsewhere so a mix
        # ratio like "1:1 peat:vermiculite" can't masquerade as an EC dilution method.
        if measure in ("EC", "pH"):
            method, method_inferred = classify_method(row, medium, rules)
        else:
            method, method_inferred = "n/a", False
        geometry, multi = detect_geometry(row, rules)
        relevance = score_relevance(measure, medium, method, geometry, multi)
        # A numeric measure with no parsed value is a qualitative mention — nothing
        # to translate, so it is context-only regardless of medium/method.
        if measure in NUMERIC and not val and measure != "water_salinity":
            relevance = "context-only"

        normalized = None
        confidence = ""
        rule = ""
        if measure == "EC" and relevance in ("convertible", "direct"):
            normalized, confidence, rule = convert_ec(val, method, medium, rules)
        elif measure == "pH" and relevance in ("convertible", "direct"):
            normalized, confidence, rule = convert_ph(val, medium, rules)
        elif measure in ("AFP", "WHC", "total_porosity") and relevance == "convertible":
            normalized, confidence, rule = convert_afp(val, geometry, target_h, model)

        if method_inferred and measure in ("EC", "pH") and confidence and confidence != "na":
            confidence = f"{confidence} (method inferred)"

        # review flags: only value-bearing claims worth a human glance
        if val and measure in ("AFP", "WHC", "total_porosity") and not geometry and not multi:
            review.append((row["claim_id"], measure,
                           "porosity value not tied to a container height — treated as target range"))
        if val and measure in ("EC", "pH") and medium == "unspecified":
            review.append((row["claim_id"], measure, "medium unspecified — pour-through basis assumed"))

        records.append({
            "claim_id": row["claim_id"], "measure": measure,
            "raw": fmt(val), "raw_low": val[0] if val else "", "raw_high": val[1] if val else "",
            "unit": val[2] if val else "",
            "medium": medium, "method": method,
            "geometry_in": geometry if geometry else "",
            "relevance": relevance,
            "normalized": fmt(normalized),
            "confidence": confidence, "rule": rule,
            "source_file": row["source_file"], "category": row["category"],
            "evidence": row["evidence"], "applicability": row["applicability"],
        })

    # ---- soil_tags.csv ----
    csv_path = folder / "soil_tags.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    # ---- _normalized_soil_claims.md ----
    md = ["# Normalized Soil Claims — Lisbon Lemon Container Guide", "",
          "Auto-generated by `soil_normalizer.py`. Soil chemical/physical claims only.",
          "**Normalized basis:** EC & pH → pour-through (home-pot); AFP/porosity → 14\"-deep pot.",
          "See `soil_normalization_report.md` for coverage and `soil_tags.csv` for the full row data.",
          "Every conversion factor is sourced in `soil_rules.yaml`.", "",
          "| Claim | Measure | Raw (as administered) | Medium | Method | Geom (in) | Relevance | Normalized (home-pot) | Confidence | Rule / source | Source file |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda x: (x["measure"], x["claim_id"])):
        md.append("| {claim_id} | {measure} | {raw} | {medium} | {method} | {geometry_in} | "
                  "{relevance} | {normalized} | {confidence} | {rule} | {source_file} |".format(**r))
    (folder / "_normalized_soil_claims.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ---- soil_normalization_report.md ----
    from collections import Counter
    by_measure = Counter(r["measure"] for r in records)
    by_relev = Counter(r["relevance"] for r in records)
    by_medium = Counter(r["medium"] for r in records)
    combos = Counter((r["medium"], r["method"]) for r in records if r["measure"] in ("EC", "pH"))
    n_conv = sum(1 for r in records if r["normalized"])
    n_quant = sum(1 for r in records if r["raw"])
    n_target = sum(1 for r in records if r["raw"] and r["relevance"] in ("convertible", "direct"))

    rep = ["# Soil Normalization Report", "",
           f"- Soil claims processed: **{len(records)}** "
           f"({n_quant} carry a quantitative value; the rest are qualitative/context)",
           f"- Convertible & value-bearing: **{n_target}**",
           f"- Converted to a target basis: **{n_conv}** "
           f"({100*n_conv/max(n_target,1):.0f}% of convertible)",
           "", "## By measure"]
    rep += [f"- {m}: {n}" for m, n in by_measure.most_common()]
    rep += ["", "## By relevance class"]
    rep += [f"- {m}: {n}" for m, n in by_relev.most_common()]
    rep += ["", "## By medium"]
    rep += [f"- {m}: {n}" for m, n in by_medium.most_common()]
    rep += ["", "## EC/pH (medium, method) combos found"]
    rep += [f"- {med} / {meth}: {n}" for (med, meth), n in combos.most_common()]
    rep += ["", f"## Review list ({len(review)}) — claims needing a human glance or a rule"]
    if review:
        rep += [f"- {cid} [{meas}]: {why}" for cid, meas, why in review]
    else:
        rep += ["- (none)"]
    (folder / "soil_normalization_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    print(f"Wrote: soil_tags.csv ({len(records)} rows), _normalized_soil_claims.md, "
          f"soil_normalization_report.md")
    print(f"Converted {n_conv}/{len(records)} | review list: {len(review)}")
    if args.verbose:
        for (med, meth), n in combos.most_common():
            print(f"  combo {med}/{meth}: {n}")


if __name__ == "__main__":
    main()
