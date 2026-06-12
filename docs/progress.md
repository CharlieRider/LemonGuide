---
layout: page
---

# Lisbon Lemon Guide — Build Progress

**Corpus:** `..\lisbon-lemon-studies\` — 165 study notes (11 topics × 15)
**Style target:** `..\wiki\fruiting_vegetables\tomato.md`

## Phase A — Source Catalog + Claim Table ✅ COMPLETE (2026-06-11)
- [x] `_source_catalog.md` — 165-row Source Inventory + Evidence Coverage Matrix (19 sections) + Top 25 + 9 Evidence Gaps
- [x] `_claim_table.md` — 693 claims (A001–E128) across 25 categories + 12-row Conflicts & Reconciliations table
- Built by fan-out: 5 agents × 33 studies → partials → assembled + deduped headers; partials removed.
- **Next: Phase B** — draft section 01 first. Every guide number must cite a Claim ID from `_claim_table.md`.

## Build decisions (locked 2026-06-11 — full text in `..\prompts\guide_creation\lemon_guide_loop_00.md`)
1. Nutrition = soil-pot granular/CRF/liquid program (not hydroponic fertigation); show conversions + state assumptions.
2. Fertilizer rates = cite field/per-tree numbers + "use labeled product"; downscaling only as an assumption-flagged illustration, never authoritative.
3. Specificity = general manual + the 19"×14" west-facing Brentwood pot as a recurring worked-example callout.
4. Labeling = per-section evidence callout; inline strength tags only on extrapolated/contested numbers.
5. Overlap = keep all 19 sections, single home + cross-reference, restate key numbers so each stands alone.

## Soil normalizer (built 2026-06-11 — Tooling\soil_normalizer.py + soil_rules.yaml)
- Normalizes soil pH/EC/AFP/porosity across field-soil / nursery / 19"×14" home-pot scenarios.
- EC & pH → pour-through basis; AFP/porosity → 14"-pot via perched-water height model.
- Artifacts here: `_normalized_soil_claims.md`, `soil_tags.csv`, `soil_normalization_report.md`.
- Re-run after the claim table changes: `python soil_normalizer.py <this folder>`.
- Sections 3/10/11/14 must prefer normalized values and note the conversion basis.

## Phase B — Section Drafts (one per loop iteration)
- [x] 01 Lisbon Lemon Variety Profile → `sections\01_variety_profile.md` (2026-06-11)
- [x] 02 Rootstock and Tree Selection → `sections\02_rootstock_tree_selection.md` (2026-06-11)
- [x] 03 Root-Zone and Media Engineering → `sections\03_root_zone_media_engineering.md` (2026-06-11)
- [x] 04 Phenology and Seasonal Growth Cycle → `sections\04_phenology_seasonal_growth.md` (2026-06-11)
- [x] 05 Transplanting and Establishment → `sections\05_transplanting_establishment.md` (2026-06-11)
- [x] 06 Container Media and Topdress Systems → `sections\06_container_media_topdress.md` (2026-06-11)
- [x] 07 Canopy Architecture and Pruning → `sections\07_canopy_pruning.md` (2026-06-11)
- [x] 08 Structural Support and Wind Management → `sections\08_structural_support_wind.md` (2026-06-11)
- [x] 09 Flowering, Pollination, and Fruit Set → `sections\09_flowering_pollination_fruit_set.md` (2026-06-11)
- [x] 10 Nutrition and Fertigation Program → `sections\10_nutrition_program.md` (2026-06-11)
- [x] 11 Irrigation Management → `sections\11_irrigation_management.md` (2026-06-11)
- [x] 12 Harvest Maturity and Fruit Quality → `sections\12_harvest_maturity_quality.md` (2026-06-11)
- [x] 13 Disease, Pest, and Physiological Disorder Diagnostics → `sections\13_disease_pest_disorder_diagnostics.md` (2026-06-11)
- [x] 14 Soil, Media, Water, and Leachate Testing → `sections\14_testing_soil_water_leachate.md` (2026-06-11)
- [x] 15 Heat, Wind, Cold, and Rain Protection → `sections\15_heat_wind_cold_rain_protection.md` (2026-06-11)
- [x] 16 Environmental and Pest Protection → `sections\16_environmental_pest_protection.md` (2026-06-11)
- [x] 17 Failure Modes and Corrective Actions → `sections\17_failure_modes_corrective_actions.md` (2026-06-11)
- [x] 18 Container Lisbon Lemon Production System → `sections\18_production_system_synthesis.md` (2026-06-11)
- [x] 19 Seasonal Irrigation Schedule + Annual Operating Calendar → `sections\19_seasonal_schedule_calendar.md` (2026-06-11)

**Phase B COMPLETE — all 19 sections drafted (2026-06-11). Next: Phase C assembly.**

## Phase C — Assemble ✅ COMPLETE (2026-06-11)
- [x] `lisbon_lemon_guide.md` assembled (front matter + linked TOC + all 19 sections + consolidated Evidence Gaps/Reconciliations appendix) — 3,376 lines / ~34k words
- [x] copied to `..\wiki\tree_fruits\lisbon_lemon.md` (folder created)

**🎉 BUILD COMPLETE — guide finished and published to wiki. Loop stopped.**
